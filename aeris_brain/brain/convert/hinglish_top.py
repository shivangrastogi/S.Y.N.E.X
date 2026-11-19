"""Hinglish-TOP (Google Research, Apache-2.0) → neutral JSONL.

    py -m brain.convert.hinglish_top --dir "Hinglish-TOP-Dataset/Dataset" --out out/converted

Files (verified 2026-10-17): "Human Annotated Data/{train,validation,test}.tsv"
and "Synthetically Generated Data/train.tsv"; TSV with header
en_query, cs_query, en_parse, cs_parse, domain.

Parses are TOPv2 trees:  [IN:CREATE_ALARM alarm laga do [SL:DATE_TIME 4 pm ko ] ]
Only intents that map cleanly onto our tools are kept; slot TEXT is copied
as the span (our args are spans), so every label stays grounded.

Split policy (plan §6.1/6.6): human train+validation → train; human TEST →
our eval set (never trained); synthetic CST5 data → train.
Both the code-switched AND the English side of each row are used.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys

from .common import call, record, write

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


# ── TOP tree parsing ───────────────────────────────────────────────────────
class Node:
    def __init__(self, label: str):
        self.label = label          # "IN:CREATE_ALARM" / "SL:DATE_TIME"
        self.children: list = []    # Node | str tokens

    def text(self) -> str:
        out = []
        for c in self.children:
            out.append(c.text() if isinstance(c, Node) else c)
        return " ".join(t for t in out if t)

    def slots(self) -> list["Node"]:
        return [c for c in self.children if isinstance(c, Node) and c.label.startswith("SL:")]


def parse_top(s: str) -> Node | None:
    toks = s.replace("[", " [ ").replace("]", " ] ").split()
    pos = 0

    def node():
        nonlocal pos
        assert toks[pos] == "["
        pos += 1
        n = Node(toks[pos])
        pos += 1
        while toks[pos] != "]":
            if toks[pos] == "[":
                n.children.append(node())
            else:
                n.children.append(toks[pos])
                pos += 1
        pos += 1
        return n
    try:
        return node()
    except (AssertionError, IndexError):
        return None


def _slot(root: Node, *names) -> str | None:
    for s in root.slots():
        if s.label[3:] in names:
            return s.text() or None
    return None


def _strip_lead(v: str | None, *leads) -> str | None:
    if not v:
        return v
    for ld in leads:
        if v.lower().startswith(ld + " "):
            return v[len(ld) + 1:]
    return v


MUSIC_SLOTS = ("MUSIC_ARTIST_NAME", "MUSIC_TRACK_TITLE", "MUSIC_PLAYLIST_TITLE",
               "MUSIC_ALBUM_TITLE", "MUSIC_GENRE", "MUSIC_RADIO_ID")
TRAVEL = {"walk": "walking", "walking": "walking", "paidal": "walking", "drive": "driving",
          "driving": "driving", "car": "driving", "bus": "transit", "train": "transit",
          "metro": "transit", "transit": "transit", "bike": "two_wheeler", "scooter": "two_wheeler"}
LIVE = {"GET_WEATHER", "GET_EVENT", "GET_INFO_TRAFFIC", "GET_ESTIMATED_DURATION",
        "GET_ESTIMATED_ARRIVAL", "GET_ESTIMATED_DEPARTURE", "GET_DISTANCE", "GET_SUNRISE", "GET_SUNSET"}


def to_contract(root: Node, query: str) -> dict | None:
    """Map one TOP tree to our contract, or None if it doesn't map cleanly."""
    intent = root.label[3:]
    if intent == "CREATE_ALARM":
        times = [_strip_lead(s.text(), "for", "at") for s in root.slots()
                 if s.label == "SL:DATE_TIME" and s.text()]
        if not times:
            return {"type": "ask", "text": "For what time?", "pending": "set_alarm"}
        return {"type": "tool_call", "calls": [{"name": "set_alarm", "args": {"time": t}} for t in times]}
    if intent == "CREATE_TIMER":
        d = _strip_lead(_slot(root, "DATE_TIME"), "for")
        if not d:
            return {"type": "ask", "text": "For how long?", "pending": "set_timer"}
        return call("set_timer", duration=d)
    if intent == "SEND_MESSAGE":
        if _slot(root, "TYPE_CONTENT"):     # video/audio messages — no tool
            return None
        to = _slot(root, "RECIPIENT")
        msg = _slot(root, "CONTENT_EXACT")
        if not to:
            return None
        if not msg:
            return {"type": "ask", "text": "What should I say?", "pending": "send_message"}
        app = None
        q = query.lower()
        if "whatsapp" in q or "whats app" in q:
            app = "whatsapp"
        elif "sms" in q or "text message" in q:
            app = "sms"
        return call("send_message", contact=to, message=msg, app=app)
    if intent == "PLAY_MUSIC":
        q = next((v for v in (_slot(root, n) for n in MUSIC_SLOTS) if v), None)
        other = [s for s in root.slots() if s.label[3:] not in MUSIC_SLOTS +
                 ("MUSIC_PROVIDER_NAME", "MUSIC_TYPE")]
        if q is None and other:
            return None  # e.g. "5th song of my playlist" — no tool expresses it
        prov = (_slot(root, "MUSIC_PROVIDER_NAME") or "").lower()
        app = "spotify" if "spotify" in prov else "youtube" if "youtube" in prov else None
        return call("play_music", query=q, app=app)
    media = {"PAUSE_MUSIC": "pause", "SKIP_TRACK_MUSIC": "next", "PREVIOUS_TRACK_MUSIC": "previous",
             "STOP_MUSIC": "stop", "RESUME_MUSIC": "play"}
    if intent in media:
        return call("media_control", action=media[intent])
    if intent == "GET_DIRECTIONS":
        dest = _slot(root, "DESTINATION")
        if not dest:
            return {"type": "ask", "text": "Where do you want to go?", "pending": "navigate_to"}
        how = (_slot(root, "METHOD_TRAVEL") or "").lower().split()
        mode = next((TRAVEL[w] for w in how if w in TRAVEL), None)
        return call("navigate_to", destination=dest, mode=mode)
    if intent == "CREATE_REMINDER":
        todo = _slot(root, "TODO")
        if not todo:
            return {"type": "ask", "text": "What should I remind you about?", "pending": "set_reminder"}
        return call("set_reminder", text=todo, when=_slot(root, "DATE_TIME"))
    if intent in LIVE:
        return {"type": "escalate", "reason": "live_info", "query": query}
    return None


def convert(dir_: str, out_dir: str, seed: int = 1, max_synth: int | None = None,
            cap_intent: int = 0):
    rng = random.Random(seed)
    per_intent: dict = {}
    files = [("human-train", os.path.join(dir_, "Human Annotated Data", "train.tsv"), "train"),
             ("human-validation", os.path.join(dir_, "Human Annotated Data", "validation.tsv"), "train"),
             ("human-test", os.path.join(dir_, "Human Annotated Data", "test.tsv"), "eval"),
             ("synthetic", os.path.join(dir_, "Synthetically Generated Data", "train.tsv"), "train")]
    train, evals, skipped = [], [], 0
    for tag, path, dest in files:
        if not os.path.exists(path):
            print(f"  missing {path} — skipped")
            continue
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        if tag == "synthetic" and max_synth:
            rng.shuffle(rows)
            rows = rows[:max_synth]
        for i, row in enumerate(rows):
            for side, qk, pk, lang in (("cs", "cs_query", "cs_parse", "hi"), ("en", "en_query", "en_parse", "en")):
                if dest == "eval" and side == "en":
                    continue  # the eval set is the code-switched human split
                # human files say en_parse/cs_parse; the synthetic file says
                # en_parses/cs_parses (verified 2026-10-17)
                q = (row.get(qk) or "").strip()
                p = (row.get(pk) or row.get(pk + "s") or "").strip()
                root = parse_top(p) if p else None
                if not q or root is None or not root.label.startswith("IN:"):
                    skipped += 1
                    continue
                out = to_contract(root, q)
                if out is None:
                    skipped += 1
                    continue
                if cap_intent and dest == "train":
                    k = (root.label, side)
                    per_intent[k] = per_intent.get(k, 0) + 1
                    if per_intent[k] > cap_intent:
                        continue
                gold = [c["name"] for c in out.get("calls", [])] + ([out["pending"]] if out.get("pending") else [])
                rec = record(f"htop-{tag}-{side}-{i}", f"hinglish_top/{tag}",
                             [{"role": "user", "content": q}, {"role": "assistant", "content": out}],
                             rng, lang=lang, gold=gold, split="test" if dest == "eval" else "train",
                             meta={"domain": row.get("domain"), "intent": root.label[3:]})
                (evals if dest == "eval" else train).append(rec)
    n1 = write(os.path.join(out_dir, "hinglish_top.train.jsonl"), train)
    n2 = write(os.path.join(out_dir, "hinglish_top.eval.jsonl"), evals)
    print(f"hinglish_top: train {n1}, eval {n2}, skipped (unmapped/unparsable) {skipped}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", required=True, help="the repo's Dataset/ folder")
    ap.add_argument("--out", default="out/converted")
    ap.add_argument("--max-synth", type=int, default=60000, help="cap on CST5 synthetic rows")
    ap.add_argument("--cap-intent", type=int, default=4000,
                    help="max train examples per (intent, language side) — stops weather swamping")
    a = ap.parse_args(argv)
    convert(a.dir, a.out, max_synth=a.max_synth, cap_intent=a.cap_intent)


if __name__ == "__main__":
    main()
