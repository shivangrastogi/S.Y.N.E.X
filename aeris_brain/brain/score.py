"""Score model outputs against gold — the metrics in the plan's §1 targets.

    py -m brain.score --gold eval/seed_real.jsonl --pred preds.jsonl [--md report.md]

preds.jsonl lines: {"id": <record id>, "turn": <n-th assistant turn, 0-based>,
                    "output": "<raw model text>"}

Metrics
  valid        output parses AND passes the contract validator
  type         predicted type == gold type (tool_call / ask / reply / plan / escalate)
  action       tool_call: same multiset of tool names
  exact        tool_call: same names AND same args (after light normalisation)
  arg_f1       F1 over (tool, arg, value) triples — partial credit
  decision     the call/ask/answer/escalate decision is right — the
               "no tool needed / ask a question" target in the plan
Per-tool rows report action + exact for every gold tool.
"""
from __future__ import annotations

import argparse
import collections
import json
import re

from .contract import load_tools, norm_text, parse, validate

_DIGITS = re.compile(r"\D")


def norm_value(v):
    if isinstance(v, str):
        d = _DIGITS.sub("", v)
        if len(d) >= 7 and len(d) >= len(v.replace(" ", "")) - 3:
            return d[-10:]  # phone numbers: compare the last 10 digits
        return norm_text(v)
    return v


def _triples(out: dict) -> set:
    t = set()
    for c in out.get("calls", []) or []:
        for k, v in (c.get("args") or {}).items():
            t.add((c.get("name"), k, json.dumps(norm_value(v))))
        t.add((c.get("name"), None, None))  # the call itself counts once
    return t


def score_pair(gold: dict, pred_text: str, tools: dict, allowed=None) -> dict:
    pred = parse(pred_text)
    r = {"gold_type": gold["type"], "valid": False, "type": False,
         "action": None, "exact": None, "tp": 0, "fp": 0, "fn": 0,
         "gold_tools": [c["name"] for c in gold.get("calls", [])]}
    if pred is None:
        if gold["type"] == "tool_call":
            r.update(action=False, exact=False, fn=len(_triples(gold)))
        return r
    r["valid"] = not validate(pred, tools, allowed=allowed)
    r["type"] = pred.get("type") == gold["type"]
    if gold["type"] == "tool_call":
        g_names = collections.Counter(c["name"] for c in gold["calls"])
        p_names = collections.Counter(c.get("name") for c in pred.get("calls", []) or [])
        r["action"] = r["type"] and g_names == p_names
        gt, pt = _triples(gold), _triples(pred) if r["type"] else set()
        r["tp"], r["fp"], r["fn"] = len(gt & pt), len(pt - gt), len(gt - pt)
        r["exact"] = bool(r["action"] and gt == pt)
    elif gold["type"] == "ask":
        r["pending_ok"] = r["type"] and pred.get("pending") == gold.get("pending")
    elif gold["type"] == "escalate":
        r["reason_ok"] = r["type"] and pred.get("reason") == gold.get("reason")
    return r


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    tc = [r for r in rows if r["gold_type"] == "tool_call"]
    tp = sum(r["tp"] for r in tc)
    fp = sum(r["fp"] for r in tc)
    fn = sum(r["fn"] for r in tc)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    per_tool = collections.defaultdict(lambda: {"n": 0, "action": 0, "exact": 0})
    for r in tc:
        for t in set(r["gold_tools"]):
            per_tool[t]["n"] += 1
            per_tool[t]["action"] += bool(r["action"])
            per_tool[t]["exact"] += bool(r["exact"])
    by_type = collections.defaultdict(lambda: {"n": 0, "type": 0})
    for r in rows:
        by_type[r["gold_type"]]["n"] += 1
        by_type[r["gold_type"]]["type"] += bool(r["type"])

    def pct(a, b):
        return round(100.0 * a / b, 2) if b else None
    return {
        "n": n,
        "valid_pct": pct(sum(r["valid"] for r in rows), n),
        "decision_pct": pct(sum(r["type"] for r in rows), n),
        "action_pct": pct(sum(bool(r["action"]) for r in tc), len(tc)),
        "exact_pct": pct(sum(bool(r["exact"]) for r in tc), len(tc)),
        "arg_f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
        "by_type": {k: {"n": v["n"], "type_pct": pct(v["type"], v["n"])} for k, v in sorted(by_type.items())},
        "per_tool": {k: {"n": v["n"], "action_pct": pct(v["action"], v["n"]),
                         "exact_pct": pct(v["exact"], v["n"])}
                     for k, v in sorted(per_tool.items(), key=lambda kv: -kv[1]["n"])},
    }


def gold_turns(record: dict):
    """Yield (turn_index, gold_contract) for every assistant turn."""
    i = 0
    for m in record["messages"]:
        if m["role"] == "assistant":
            yield i, m["content"]
            i += 1


def to_markdown(rep: dict, title: str = "AERIS brain eval") -> str:
    lines = [f"# {title}", "",
             f"| examples | valid | decision | action | exact | arg F1 |",
             "|---|---|---|---|---|---|",
             f"| {rep['n']} | {rep['valid_pct']}% | {rep['decision_pct']}% | "
             f"{rep['action_pct']}% | {rep['exact_pct']}% | {rep['arg_f1']} |", "",
             "## By gold type", "", "| type | n | correct type |", "|---|---|---|"]
    lines += [f"| {k} | {v['n']} | {v['type_pct']}% |" for k, v in rep["by_type"].items()]
    lines += ["", "## Per tool", "", "| tool | n | action | exact |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['n']} | {v['action_pct']}% | {v['exact_pct']}% |"
              for k, v in rep["per_tool"].items()]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score brain predictions.")
    ap.add_argument("--gold", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--json", help="write the report as JSON here")
    ap.add_argument("--md", help="write the report as Markdown here")
    a = ap.parse_args(argv)
    tools = load_tools()
    golds = {}
    with open(a.gold, encoding="utf-8") as f:
        for ln in f:
            rec = json.loads(ln)
            for i, g in gold_turns(rec):
                golds[(rec["id"], i)] = (g, set(rec.get("tools") or tools))
    rows, missing = [], 0
    with open(a.pred, encoding="utf-8") as f:
        preds = {(p["id"], p.get("turn", 0)): p["output"] for p in map(json.loads, f)}
    for key, (g, allowed) in golds.items():
        if key not in preds:
            missing += 1
            continue
        rows.append(score_pair(g, preds[key], tools, allowed))
    rep = aggregate(rows)
    rep["missing_predictions"] = missing
    print(to_markdown(rep))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=2)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(to_markdown(rep))


if __name__ == "__main__":
    main()
