"""Brain v2 builders (docs/AERIS_BRAIN_V2.md).

    # NLU records from labelled TURN data, balanced per intent, with typed-Hinglish spelling spread
    py -m brain.build_v2 nlu --out out/nlu/commands.jsonl --per-intent 220 out/clean/template.jsonl out/clean/hinglish_top.jsonl ...

    # split the teacher's mixed output (turn / nlu / memory records) into one file per kind
    py -m brain.build_v2 split-teacher --out out/teacher_split data/teacher/chat_grid_*.jsonl

    # the free-Colab mix (~40k, chat ≈ 35 %) — prints the brain.mix command it runs
    py -m brain.build_v2 mix --total 40000 --clean out/clean --out out/final/train.jsonl
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import random

from .contract import load_tools
from .langmix import spell_vary
from .nlu import from_turn, keywords

# Shares for the free-T4 run. Chat (teacher) ≈ 30 % TURN + its NLU/MEMORY records.
MIX_V2 = {
    "template": 0.27,        # commands, multi-call, ask, plan, escalate
    "hinglish_top": 0.06,    # human-labelled Hinglish commands
    "massive": 0.03,
    "mobile_actions": 0.01,
    "when2call": 0.03,       # when NOT to call a tool
    "chat": 0.30,            # teacher grid conversations (reply + escalate)
    "memory_turn": 0.06,     # answers using remembered facts / honest "don't know"
    "nlu": 0.17,             # understanding head (commands + chat, intent-balanced)
    "memory_extract": 0.07,  # memory head
}


def _read(paths) -> list[dict]:
    out = []
    for p in paths:
        for path in sorted(glob.glob(p)) or [p]:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    out += [json.loads(ln) for ln in f if ln.strip()]
    return out


def _write(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def nlu_from_turns(records: list[dict], per_intent: int, rng: random.Random, vary: float = 0.25) -> list[dict]:
    """Intent-balanced NLU records: at most `per_intent` per intent (so frequent
    tools can't drown rare ones), and a share of Hinglish texts get real typed
    spelling variants — slots stay byte-exact, keywords are recomputed."""
    tools = load_tools()
    by_intent = collections.defaultdict(list)
    for r in records:
        for n in from_turn(r, tools):
            by_intent[n["nlu"]["intent"]].append(n)
    out = []
    for intent, rows in by_intent.items():
        rng.shuffle(rows)
        for n in rows[:per_intent]:
            if n["nlu"]["lang"] in ("hinglish", "hindi_roman") and rng.random() < vary:
                spans = [s["v"] for s in n["nlu"]["slots"]]
                n["text"] = spell_vary(n["text"], spans, rate=0.5, rng=rng)
                n["nlu"]["keywords"] = keywords(n["text"], spans)
                n["source"] += "+spell"
            out.append(n)
    rng.shuffle(out)
    return out


def split_teacher(records: list[dict]) -> dict[str, list[dict]]:
    out = {"chat": [], "nlu_chat": [], "memory_extract_chat": []}
    for r in records:
        t = r.get("task")
        (out["nlu_chat"] if t == "nlu" else out["memory_extract_chat"] if t == "memory" else out["chat"]).append(r)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("nlu")
    a1.add_argument("inputs", nargs="+")
    a1.add_argument("--out", required=True)
    a1.add_argument("--per-intent", type=int, default=220)
    a2 = sub.add_parser("split-teacher")
    a2.add_argument("inputs", nargs="+")
    a2.add_argument("--out", required=True)
    a3 = sub.add_parser("mix")
    a3.add_argument("--total", type=int, default=40000)
    a3.add_argument("--clean", required=True, help="folder with cleaned <source>.jsonl files")
    a3.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rng = random.Random(3)

    if a.cmd == "nlu":
        rows = nlu_from_turns(_read(a.inputs), a.per_intent, rng)
        _write(a.out, rows)
        c = collections.Counter(r["nlu"]["intent"] for r in rows)
        print(f"nlu: {len(rows)} records, {len(c)} intents, max {c.most_common(1)} min {c.most_common()[-1:]} -> {a.out}")
    elif a.cmd == "split-teacher":
        for name, rows in split_teacher(_read(a.inputs)).items():
            _write(os.path.join(a.out, f"{name}.jsonl"), rows)
            print(f"{name}: {len(rows)}")
    else:
        from . import mix
        args = [f"{k}={os.path.join(a.clean, k + '.jsonl')}:{w}" for k, w in MIX_V2.items()]
        print("brain.mix", " ".join(args))
        mix.main(args + ["--total", str(a.total), "--out", a.out])


if __name__ == "__main__":
    main()
