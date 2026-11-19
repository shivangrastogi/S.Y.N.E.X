"""Shared helpers for dataset converters → neutral JSONL."""
from __future__ import annotations

import json
import os
import random

from ..contract import load_tools
from ..generate import FAMILIES, random_now

TOOLS = load_tools()


def offered(rng: random.Random, gold: list[str], tools=TOOLS) -> list[str]:
    """Same tool-offering policy as the template generator: gold tools +
    confusable family members + random distractors (15%: all tools)."""
    names = list(tools)
    if rng.random() < 0.15:
        return names
    pick = set(g for g in gold if g in tools)
    for g in gold:
        for fam in FAMILIES:
            if g in fam:
                extra = sorted(fam - pick)
                rng.shuffle(extra)
                pick.update(extra[:rng.randint(1, 3)])
    rest = sorted(set(names) - pick)
    rng.shuffle(rest)
    pick.update(rest[:rng.randint(3, 10)])
    return [n for n in names if n in pick]


def record(rid: str, source: str, messages: list[dict], rng: random.Random, *,
           lang: str | None = None, gold: list[str] | None = None,
           tool_specs: list[dict] | None = None, ungrounded: bool = False,
           split: str = "train", meta: dict | None = None) -> dict:
    if tool_specs:
        tools_list = [t["name"] for t in tool_specs]
    else:
        tools_list = offered(rng, gold or [])
    return {
        "id": rid, "split": split, "source": source,
        "family": next((m["content"]["type"] for m in messages if m["role"] == "assistant"), None),
        "lang": lang, "prompt_lang": rng.choice(["match"] * 6 + ["english"] * 2 + ["hinglish"] * 2)
        if lang != "en" else rng.choice(["match"] * 8 + ["english"] * 2),
        "tools": tools_list, "tool_specs": tool_specs or None,
        "now": random_now(rng) if rng.random() < 0.7 else None,
        "messages": messages,
        "meta": {**(meta or {}), **({"ungrounded": True} if ungrounded else {})},
    }


def write(path: str, recs) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            if r.get("tool_specs") is None:
                r.pop("tool_specs", None)
            # default=str: HF `datasets` returns datetime objects for some
            # fields (Mobile Actions); as strings they're checked like any
            # other value (ungrounded optional args get dropped).
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            n += 1
    return n


def call(name: str, **args) -> dict:
    return {"type": "tool_call", "calls": [{"name": name, "args": {k: v for k, v in args.items() if v not in (None, "")}}]}
