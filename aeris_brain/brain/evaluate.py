"""Run a model over an eval JSONL and score it. Backend-agnostic.

    preds = predict(records, generate, tokenizer, tools)   # → [{"id","turn","output"}]
    report = score_preds(records, preds, tools)

`generate(prompts: list[str]) -> list[str]` is supplied by the notebook
(vLLM, transformers or llama-cpp-python). Earlier turns of a multi-turn
record use the GOLD history (teacher forcing), so one early mistake doesn't
cascade and hide how good later turns are.
"""
from __future__ import annotations

import json
import time

from .contract import canonical, load_tools, tools_for
from .render import chat, end_marker
from .score import aggregate, gold_turns, score_pair, to_markdown


def prompts_for(records, tokenizer, tools, **template_kwargs):
    jobs = []
    for r in records:
        msgs = chat(r, tools_for(r, tools))
        turn = 0
        for i, m in enumerate(msgs):
            if m["role"] != "assistant":
                continue
            p = tokenizer.apply_chat_template(msgs[:i], tokenize=False,
                                              add_generation_prompt=True, **template_kwargs)
            jobs.append((r["id"], turn, p))
            turn += 1
    return jobs


def predict(records, generate, tokenizer, tools=None, batch: int = 64, **template_kwargs):
    tools = tools or load_tools()
    jobs = prompts_for(records, tokenizer, tools, **template_kwargs)
    end = end_marker(tokenizer, **template_kwargs)
    preds, t0 = [], time.time()
    for k in range(0, len(jobs), batch):
        chunk = jobs[k:k + batch]
        outs = generate([p for _, _, p in chunk])
        for (rid, turn, _), o in zip(chunk, outs):
            preds.append({"id": rid, "turn": turn, "output": o.split(end)[0].strip()})
    dt = time.time() - t0
    print(f"predicted {len(preds)} turns in {dt:.1f}s ({len(preds) / max(dt, 1e-9):.1f}/s)")
    return preds


def score_preds(records, preds, tools=None, title="eval"):
    tools = tools or load_tools()
    p = {(x["id"], x["turn"]): x["output"] for x in preds}
    rows, errors = [], []
    for r in records:
        rt = tools_for(r, tools)
        for i, g in gold_turns(r):
            out = p.get((r["id"], i))
            if out is None:
                continue
            s = score_pair(g, out, rt, set(r.get("tools") or rt))
            rows.append(s)
            if not s["type"] or s.get("exact") is False:
                errors.append({"id": r["id"], "turn": i, "user": [m["content"] for m in r["messages"]
                               if m["role"] == "user"][min(i, 99)], "gold": canonical(g), "pred": out})
    rep = aggregate(rows)
    rep["markdown"] = to_markdown(rep, title)
    rep["errors"] = errors
    return rep


def save(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
