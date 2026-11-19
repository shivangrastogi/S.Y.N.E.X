"""Hugging Face datasets → neutral JSONL (run in Colab; needs `datasets`).

    py -m brain.convert.hf_sets mobile_actions --out out/converted
    py -m brain.convert.hf_sets when2call      --out out/converted
    py -m brain.convert.hf_sets xlam           --out out/converted   # gated: accept terms + HF login
    py -m brain.convert.hf_sets smoltalk       --out out/converted

Field names checked against the dataset cards on 2026-10-17:
  google/mobile-actions        metadata, tools[7], messages[{role, content, tool_calls}]   CC-BY-4.0
  nvidia/When2Call train_sft   tools, messages                                          CC-BY-4.0
  Salesforce/xlam-function-calling-60k  query, tools (json str), answers (json str)     CC-BY-NC-4.0 (personal use)
  HuggingFaceTB/smoltalk everyday-conversations  messages[{role, content}]               Apache-2.0
The exact shape INSIDE a tool call isn't documented on the cards, so the
accessors below accept the common variants ({"function": {...}} or flat;
arguments as dict or JSON string) and every converter prints how many
records it could not map. Check those counts on the first run.

Converted foreign tools travel INSIDE the record (tool_specs) — they teach
general "read a schema, call it right / ask / decline" skill without being
added to the AERIS registry. Their arg values are not always spans of the
user text, so these records are flagged meta.ungrounded.
"""
from __future__ import annotations

import argparse
import json
import os
import random

from ..contract import norm_text
from .common import TOOLS, call, record, write


# ── shared accessors ───────────────────────────────────────────────────────
def _calls_of(msg: dict) -> list[tuple[str, dict]]:
    out = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", tc) if isinstance(tc, dict) else {}
        name = fn.get("name")
        args = fn.get("arguments", fn.get("args", {}))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = None
        if name and isinstance(args, dict):
            out.append((name, args))
    return out


_TYPE = {"string": "string", "str": "string", "integer": "integer", "int": "integer",
         "number": "number", "float": "number", "boolean": "boolean", "bool": "boolean"}


def spec_from_schema(fn: dict) -> dict | None:
    """OpenAI-style / xLAM-style function schema → our tool spec."""
    fn = fn.get("function", fn)
    name = fn.get("name")
    if not name:
        return None
    params = fn.get("parameters") or {}
    props = params.get("properties", params) if isinstance(params, dict) else {}
    required = list(params.get("required", [])) if isinstance(params, dict) else []
    out = {}
    for k, p in (props or {}).items():
        if not isinstance(p, dict) or k in ("type", "required", "properties"):
            continue
        raw = str(p.get("type", "")).lower()
        if p.get("enum"):
            out[k] = {"type": "enum", "values": [str(v) for v in p["enum"]], "description": p.get("description", "")}
        else:
            base = raw.split(",")[0].split("[")[0].strip()
            t = _TYPE.get(base, "any")
            spec = {"type": t, "description": str(p.get("description", ""))[:200]}
            if t == "any":
                spec["hint"] = base or "any"
            out[k] = spec  # xLAM writes "str, optional" — base type is "str"
    return {"name": name, "description": str(fn.get("description", ""))[:300],
            "params": out, "required": [r for r in required if r in out]}


def _load(name, config=None, split="train"):
    from datasets import load_dataset  # Colab dependency
    return load_dataset(name, config, split=split) if config else load_dataset(name, split=split)


# ── Google Mobile Actions → OUR registry tools ─────────────────────────────
MA_MAP = {
    "turn_on_flashlight": lambda a: ("flashlight", {"state": "on"}),
    "turn_off_flashlight": lambda a: ("flashlight", {"state": "off"}),
    "open_wifi_settings": lambda a: ("open_settings", {"page": "wifi"}),
    "show_map": lambda a: ("navigate_to", {"destination": a.get("query") or a.get("location") or a.get("destination")}),
    "send_email": lambda a: ("send_email", {"to": a.get("to") or a.get("recipient"),
                                            "subject": a.get("subject"), "body": a.get("body")}),
    "create_calendar_event": lambda a: ("create_calendar_event", {"title": a.get("title") or a.get("summary"),
                                                                  "when": a.get("datetime") or a.get("start_time")}),
}


def mobile_actions(out_dir, rng):
    ds = _load("google/mobile-actions")
    recs, miss = [], 0
    for i, ex in enumerate(ds):
        msgs = ex["messages"]
        user = next((m["content"] for m in msgs if m["role"] == "user"), None)
        asst = next((m for m in msgs if m["role"] == "assistant"), None)
        if not user or not asst:
            miss += 1
            continue
        calls = _calls_of(asst)
        mapped = []
        for name, args in calls:
            f = MA_MAP.get(name)
            if f is None:
                mapped = None
                break
            tool, a = f(args)
            a = {k: v for k, v in a.items() if v not in (None, "")}
            # Their values are often normalised ("2024-06-06T10:30:00"). Our
            # args are spans, so drop OPTIONAL args the user didn't literally
            # say; a missing REQUIRED one makes quality drop the record.
            req = set(TOOLS[tool].get("required", []))
            a = {k: v for k, v in a.items()
                 if k in req or not isinstance(v, str) or norm_text(v) in norm_text(user)}
            mapped.append((tool, a))
        if not mapped:
            miss += 1
            continue
        out = {"type": "tool_call", "calls": [{"name": t, "args": a} for t, a in mapped]}
        # Their values can be normalised (ISO dates) — quality drops any that
        # aren't spans of the user text, so this stays grounded.
        recs.append(record(f"ma-{i}", "mobile_actions", [{"role": "user", "content": user},
                                                         {"role": "assistant", "content": out}],
                           rng, lang="en", gold=[t for t, _ in mapped]))
    n = write(os.path.join(out_dir, "mobile_actions.train.jsonl"), recs)
    print(f"mobile_actions: {n} kept, {miss} unmapped (tool not in MA_MAP or no call)")


# ── NVIDIA When2Call → call / ask / decline with ITS tools ─────────────────
def when2call(out_dir, rng):
    ds = _load("nvidia/When2Call", "train_sft")
    recs, miss = [], 0
    for i, ex in enumerate(ds):
        tools = ex.get("tools") or []
        if isinstance(tools, str):
            tools = json.loads(tools)
        # verified 2026-10-17: a LIST of JSON strings, one per tool
        tools = [json.loads(t) if isinstance(t, str) else t for t in tools]
        specs = [s for s in (spec_from_schema(t) for t in tools) if s]
        msgs = ex.get("messages") or []
        user = next((m["content"] for m in msgs if m["role"] == "user"), None)
        asst = next((m for m in reversed(msgs) if m["role"] == "assistant"), None)
        if not user or not asst:
            miss += 1
            continue
        calls = _calls_of(asst)
        text = (asst.get("content") or "").strip()
        if calls:
            out = {"type": "tool_call", "calls": [{"name": n, "args": a} for n, a in calls]}
        elif text.endswith("?") and specs:
            out = {"type": "ask", "text": text[:300],
                   "pending": specs[0]["name"] if len(specs) == 1 else None}
            if out["pending"] is None:
                out.pop("pending")
        elif text:
            out = {"type": "escalate", "reason": "no_tool", "query": user}
        else:
            miss += 1
            continue
        recs.append(record(f"w2c-{i}", "when2call", [{"role": "user", "content": user},
                                                     {"role": "assistant", "content": out}],
                           rng, lang="en", tool_specs=specs or None, ungrounded=True))
    n = write(os.path.join(out_dir, "when2call.train.jsonl"), recs)
    print(f"when2call: {n} kept, {miss} unmapped")


# ── Salesforce xLAM 60k → general function calling (NC licence) ────────────
def xlam(out_dir, rng, limit=30000):
    ds = _load("Salesforce/xlam-function-calling-60k")
    recs, miss = [], 0
    idx = list(range(len(ds)))
    rng.shuffle(idx)
    for i in idx[:limit]:
        ex = ds[i]
        try:
            tools = json.loads(ex["tools"])
            answers = json.loads(ex["answers"])
        except (TypeError, json.JSONDecodeError):
            miss += 1
            continue
        specs = [s for s in (spec_from_schema(t) for t in tools) if s]
        calls = [{"name": a["name"], "args": a.get("arguments", {})} for a in answers
                 if isinstance(a, dict) and a.get("name")]
        if not calls or not specs:
            miss += 1
            continue
        out = {"type": "tool_call", "calls": calls}
        recs.append(record(f"xlam-{ex.get('id', i)}", "xlam", [{"role": "user", "content": ex["query"]},
                                                               {"role": "assistant", "content": out}],
                           rng, lang="en", tool_specs=specs, ungrounded=True,
                           meta={"license": "cc-by-nc-4.0"}))
    n = write(os.path.join(out_dir, "xlam.train.jsonl"), recs)
    print(f"xlam: {n} kept, {miss} unparsable  (CC-BY-NC: personal/non-commercial use only)")


# ── SmolTalk everyday conversations → small talk replies ───────────────────
def smoltalk(out_dir, rng, max_reply_chars=320):
    ds = _load("HuggingFaceTB/smoltalk", "everyday-conversations")
    recs, miss = [], 0
    for i, ex in enumerate(ds):
        msgs, ok = [], True
        for m in ex["messages"]:
            if m["role"] == "user":
                msgs.append({"role": "user", "content": m["content"].strip()})
            elif m["role"] == "assistant":
                t = m["content"].strip()
                if len(t) > max_reply_chars or "\n" in t or "*" in t:
                    ok = False  # replies are spoken: short, no lists/markdown
                    break
                msgs.append({"role": "assistant", "content": {"type": "reply", "text": t}})
        if not ok or len(msgs) < 2 or msgs[0]["role"] != "user":
            miss += 1
            continue
        recs.append(record(f"smol-{i}", "smoltalk/everyday", msgs, rng, lang="en", gold=[], ungrounded=True))
    n = write(os.path.join(out_dir, "smoltalk.train.jsonl"), recs)
    print(f"smoltalk: {n} kept, {miss} dropped (long/markdown replies)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("which", choices=["mobile_actions", "when2call", "xlam", "smoltalk", "all"])
    ap.add_argument("--out", default="out/converted")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    jobs = ["mobile_actions", "when2call", "xlam", "smoltalk"] if a.which == "all" else [a.which]
    for j in jobs:
        try:
            globals()[j](a.out, rng)
        except Exception as e:  # one gated/missing dataset shouldn't stop the rest
            print(f"{j}: FAILED — {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
