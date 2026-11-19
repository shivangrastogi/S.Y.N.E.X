"""Scoring for the brain's NLU and MEMORY heads (TURN uses brain/score.py).

    from brain.score_v2 import is_task_set, task_prompts, score_task
    if is_task_set(recs):
        preds = generate(task_prompts(recs, tok, TOOLS, **TEMPLATE_KW))
        rep = score_task(recs, preds)

NLU:    JSON-valid %, intent / act / sentiment / emotion / lang accuracy, slot F1 over
        (arg, value) pairs, keyword F1.
MEMORY: JSON-valid %, exact-set %, fact precision / recall / F1, and the false-memory
        rate — "remembering" something when the user said nothing lasting (the error
        that would make memory untrustworthy).
"""
from __future__ import annotations

import json
import re

from .nlu import chat_messages

_OBJ = re.compile(r"\{.*\}", re.S)


def is_task_set(records: list[dict]) -> bool:
    return bool(records) and records[0].get("task") in ("nlu", "memory")


def task_prompts(records, tokenizer, tools, **template_kwargs) -> list[str]:
    return [tokenizer.apply_chat_template(chat_messages(r, tools)[:2], tokenize=False,
                                          add_generation_prompt=True, **template_kwargs) for r in records]


def _parse(text: str):
    m = _OBJ.search(text or "")
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None


def _f1(gold: set, pred: set) -> tuple[float, float, float]:
    if not gold and not pred:
        return 1.0, 1.0, 1.0
    tp = len(gold & pred)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).lower().strip(" .!?,"))


def score_task(records: list[dict], preds: list[str]) -> dict:
    task = records[0]["task"]
    n = len(records)
    valid = 0
    if task == "nlu":
        hits = dict(intent=0, act=0, sentiment=0, emotion=0, lang=0)
        slot_f1 = kw_f1 = 0.0
        errors = []
        for r, out in zip(records, preds):
            g, p = r["nlu"], _parse(out)
            if not isinstance(p, dict):
                errors.append({"id": r["id"], "text": r["text"], "pred": out[:200]})
                continue
            valid += 1
            for k in hits:
                hits[k] += p.get(k) == g[k]
            gs = {(s["k"], _norm(s["v"])) for s in g["slots"]}
            ps = {(s.get("k"), _norm(s.get("v", ""))) for s in p.get("slots", []) if isinstance(s, dict)}
            slot_f1 += _f1(gs, ps)[2]
            kw_f1 += _f1({_norm(k) for k in g["keywords"]}, {_norm(k) for k in p.get("keywords", [])})[2]
            if p.get("intent") != g["intent"]:
                errors.append({"id": r["id"], "text": r["text"], "gold": g["intent"], "pred": p.get("intent")})
        rep = {f"{k}_pct": round(100 * v / n, 1) for k, v in hits.items()}
        rep.update(valid_pct=round(100 * valid / n, 1), slot_f1=round(slot_f1 / n, 3), keyword_f1=round(kw_f1 / n, 3))
    else:
        exact = 0
        tp_p = tp_r = f1 = 0.0
        false_mem = empty = 0
        errors = []
        for r, out in zip(records, preds):
            p = _parse(out)
            gold = {_norm(f) for f in r["facts"]}
            if not isinstance(p, dict) or not isinstance(p.get("facts"), list):
                errors.append({"id": r["id"], "pred": out[:200]})
                continue
            valid += 1
            pred = {_norm(f) for f in p["facts"] if isinstance(f, str)}
            exact += pred == gold
            pp, rr, ff = _f1(gold, pred)
            tp_p, tp_r, f1 = tp_p + pp, tp_r + rr, f1 + ff
            if not gold:
                empty += 1
                false_mem += bool(pred)
            if pred != gold:
                errors.append({"id": r["id"], "turns": r["turns"], "gold": sorted(gold), "pred": sorted(pred)})
        rep = dict(valid_pct=round(100 * valid / n, 1), exact_pct=round(100 * exact / n, 1),
                   precision=round(tp_p / n, 3), recall=round(tp_r / n, 3), f1=round(f1 / n, 3),
                   false_memory_pct=round(100 * false_mem / empty, 1) if empty else None)
    rep["task"], rep["n"], rep["errors"] = task, n, errors
    rep["markdown"] = f"**{task}** (n={n}): " + ", ".join(f"{k} {v}" for k, v in rep.items()
                                                       if k not in ("task", "n", "errors", "markdown"))
    return rep
