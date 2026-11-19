"""Template data generator → neutral JSONL (train / dev / test).

    py -m brain.generate --n 200000 --out out/templated

Neutral record (one per line):
    {"id": "tpl-000123", "split": "train", "source": "template",
     "family": "single", "lang": "hi", "prompt_lang": "match",
     "tools": ["send_message", "call", ...],        # offered in the prompt
     "now": "Friday 17 October 2026, 18:40",
     "messages": [{"role": "user", "content": "..."},
                  {"role": "assistant", "content": {...contract...}}],
     "meta": {...}}

The training notebook renders this with brain.prompt.system_prompt() and the
chosen model's chat template, so switching base model never means
regenerating data.

Splits are by TEMPLATE (unseen phrasings in test) and by slot VALUE
(unseen names/messages in test) — see templates.py and slots.py.
"""
from __future__ import annotations

import argparse
import collections
import datetime as _dt
import hashlib
import json
import os
import random

from . import dialogs as D
from .augment import augment
from .contract import load_tools, make_call, validate
from .expand import Template, join, slot_values
from .templates import TEMPLATES, arg_for

FAMILY_MIX = {"single": 0.62, "ask": 0.07, "pronoun": 0.03, "multi": 0.08,
              "plan": 0.05, "escalate": 0.10, "reply": 0.05}
TOOL_WEIGHT = {"send_message": 3.0, "call": 2.0, "set_alarm": 2.0, "open_app": 2.0,
               "set_timer": 1.5, "play_music": 1.5, "web_search": 1.5,
               "toggle_setting": 1.5, "laptop_command": 1.2}
# tools a model can confuse — offered together on purpose
FAMILIES = [
    {"send_message", "open_chat", "call", "send_email"},
    {"set_alarm", "set_timer", "set_reminder", "create_calendar_event", "date_time"},
    {"flashlight", "toggle_setting", "brightness", "open_settings"},
    {"open_app", "web_search", "play_music", "navigate_to"},
    {"read_screen", "summarize_screen", "tap_on", "take_screenshot", "scroll"},
    {"remember", "recall", "forget", "create_note", "set_reminder"},
    {"media_control", "play_music", "volume"},
    {"end_conversation", "cancel_task", "navigate_phone"},
]
PROMPT_LANG = (["match"] * 6) + (["english"] * 2) + (["hinglish"] * 2)
def random_now(rng: random.Random) -> str:
    """A real date+time in 2025-2027, formatted like the app sends it."""
    d = _dt.datetime(2025, 1, 1) + _dt.timedelta(minutes=rng.randrange(3 * 365 * 24 * 60))
    return f"{d:%A} {d.day} {d:%B %Y, %H:%M}"


def _h(s: str) -> int:
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16)


def assign_splits(templates) -> dict[str, list]:
    """Per (tool, lang) — enum variants pooled: sorted by hash, every 8th → test, every 8th+4 →
    dev (groups of 6+), rest train. Groups under 4 templates stay train-only (their test
    examples still use unseen slot VALUES)."""
    groups = collections.defaultdict(list)
    for t in templates:
        groups[(t.tool, t.lang)].append(t)
    out = {"train": [], "dev": [], "test": []}
    for items in groups.values():
        items.sort(key=lambda t: _h(t.src))
        for i, t in enumerate(items):
            if len(items) >= 4 and i % 8 == 0:
                out["test"].append(t)
            elif len(items) >= 6 and i % 8 == 4:
                out["dev"].append(t)
            else:
                out["train"].append(t)
    # Every enum variant (e.g. toggle_setting dnd/off) keeps ≥1 TRAIN
    # phrasing — the test may use unseen wording, never an unseen label.
    def key(t):
        return (t.tool, t.lang, json.dumps(t.const, sort_keys=True))
    have = {key(t) for t in out["train"]}
    for split in ("dev", "test"):
        for t in list(out[split]):
            if key(t) not in have:
                out[split].remove(t)
                out["train"].append(t)
                have.add(key(t))
    return out


class Generator:
    def __init__(self, seed: int = 1, tools_path: str | None = None):
        self.tools = load_tools(tools_path) if tools_path else load_tools()
        self.seed = seed
        bad = [t.src for t in TEMPLATES if t.tool not in self.tools]
        if bad:
            raise ValueError(f"templates for unknown tools: {bad[:3]}")
        self.parsed = {t.src: Template(t.src) for t in TEMPLATES}
        self.by_split = assign_splits(TEMPLATES)
        # (split, tool, lang) → templates; falls back to train for tiny groups
        self.index = collections.defaultdict(list)
        for split, ts in self.by_split.items():
            for t in ts:
                self.index[(split, t.tool, t.lang)].append(t)

    # ── helpers ────────────────────────────────────────────────────────
    def _templates(self, split, tool, lang):
        return (self.index.get((split, tool, lang)) or
                self.index.get(("train", tool, lang)) or [])

    def _tool_choice(self, rng, allowed=None):
        names = sorted({t.tool for t in TEMPLATES if allowed is None or t.tool in allowed})
        weights = [TOOL_WEIGHT.get(n, 1.0) * (1.0 if self.tools[n].get("implemented") else 0.7)
                   for n in names]
        return rng.choices(names, weights=weights)[0]

    def single(self, ctx, lang, allowed=None, strength=1.0):
        """→ (segs, tool, args) for one templated call, or None."""
        rng = ctx.rng
        for _ in range(20):
            tool = self._tool_choice(rng, allowed)
            ts = self._templates(ctx.split, tool, lang)
            if ts:
                break
        else:
            return None
        t = rng.choice(ts)
        segs = self.parsed[t.src].sample(rng, ctx.filler(lang))
        args = dict(t.const)
        for slot, val in slot_values(segs).items():
            arg = arg_for(tool, slot)
            if arg in self.tools[tool]["params"]:
                args[arg] = val
        segs = augment(segs, rng, lang, strength)
        return segs, tool, args, t.src

    def offered(self, rng, gold: list[str]) -> list[str]:
        names = list(self.tools)
        if rng.random() < 0.15:
            return names
        pick = set(gold)
        for g in gold:
            for fam in FAMILIES:
                if g in fam:
                    extra = sorted(fam - pick)
                    rng.shuffle(extra)
                    pick.update(extra[:rng.randint(1, 3)])
        rest = sorted(set(names) - pick)
        rng.shuffle(rest)
        pick.update(rest[:rng.randint(3, 10)])
        return [n for n in names if n in pick]  # registry order, stable

    # ── one example ────────────────────────────────────────────────────
    def example(self, rng: random.Random, split: str, family: str):
        ctx = D.Ctx(rng, split, self.tools)
        prompt_lang = rng.choice(PROMPT_LANG)
        meta: dict = {}
        if family == "single":
            lang = rng.choice(["en", "hi"])
            r = self.single(ctx, lang)
            if r is None:
                return None
            segs, tool, args, src = r
            msgs = [{"role": "user", "content": join(segs)},
                    {"role": "assistant", "content": make_call(self.tools, (tool, args))}]
            meta = {"family": "single", "tool": tool, "lang": lang, "template": _h(src)}
        elif family == "ask":
            msgs, meta = D.ask_example(ctx, prompt_lang, multi_turn=rng.random() < 0.5)
        elif family == "pronoun":
            msgs, meta = D.pronoun_example(ctx, prompt_lang)
        elif family == "multi":
            def pick(lang, allowed):
                r = self.single(ctx, lang, allowed, strength=0.3)
                return r[0], r[1], r[2]
            msgs, meta = D.multi_example(ctx, pick, prompt_lang)
        elif family == "plan":
            msgs, meta = D.plan_example(ctx)
        elif family == "escalate":
            msgs, meta = D.escalate_example(ctx)
        else:
            msgs, meta = D.smalltalk_example(ctx, prompt_lang)

        gold = sorted({c["name"] for m in msgs if m["role"] == "assistant"
                       for c in m["content"].get("calls", [])} |
                      ({m["content"]["pending"] for m in msgs if m["role"] == "assistant"
                        and m["content"].get("pending")}))
        offered = self.offered(rng, gold)
        # validate every assistant turn against what the user said so far
        said = ""
        for m in msgs:
            if m["role"] == "user":
                said += " " + m["content"]
                continue
            errs = validate(m["content"], self.tools, allowed=set(offered),
                            user_text=said, grounded=True)
            if errs:
                return {"_invalid": errs, "msgs": msgs}
        now = random_now(rng)
        return {"split": split, "source": "template", "family": meta.get("family", family),
                "lang": meta.get("lang"), "prompt_lang": prompt_lang, "tools": offered,
                "now": now if rng.random() < 0.7 else None, "messages": msgs, "meta": meta}

    def run(self, n: int, split: str, seed_offset: int = 0):
        rng = random.Random(self.seed * 1_000_003 + seed_offset)
        fams = list(FAMILY_MIX)
        weights = [FAMILY_MIX[f] for f in fams]
        made, invalid = 0, collections.Counter()
        while made < n:
            ex = self.example(rng, split, rng.choices(fams, weights=weights)[0])
            if ex is None:
                continue
            if "_invalid" in ex:
                invalid[ex["_invalid"][0].split(":")[0]] += 1
                continue
            made += 1
            yield ex
        self.invalid = invalid


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=200_000, help="train examples")
    ap.add_argument("--eval-n", type=int, default=6_000, help="dev and test examples each")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="out/templated")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    g = Generator(seed=a.seed)
    stats = {}
    for i, (split, n) in enumerate([("train", a.n), ("dev", a.eval_n), ("test", a.eval_n)]):
        fam, tool = collections.Counter(), collections.Counter()
        path = os.path.join(a.out, f"{split}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for j, ex in enumerate(g.run(n, split, seed_offset=i)):
                ex["id"] = f"tpl-{split}-{j:07d}"
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
                fam[ex["family"]] += 1
                for m in ex["messages"]:
                    if m["role"] == "assistant":
                        for c in m["content"].get("calls", []):
                            tool[c["name"]] += 1
        stats[split] = {"n": n, "families": dict(fam), "tools": dict(tool.most_common()),
                        "dropped_invalid": dict(g.invalid)}
        print(f"{split}: {n} -> {path}  (dropped invalid: {sum(g.invalid.values())})")
    stats["templates"] = {k: len(v) for k, v in g.by_split.items()}
    stats["generated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    with open(os.path.join(a.out, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
