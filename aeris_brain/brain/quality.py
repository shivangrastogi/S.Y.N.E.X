"""Quality pipeline for neutral JSONL (plan §6.5).

    py -m brain.quality --in out/templated/train.jsonl out/converted/*.jsonl \
        --eval eval/seed_real.jsonl out/templated/test.jsonl \
        --out out/clean/train.jsonl [--near-dup] [--cap-template 400]

Steps, in order (each prints how many it dropped):
  1. validate       every assistant turn passes the contract validator
                    (string args grounded in the user's words, unless the
                    record is flagged meta.ungrounded — e.g. paraphrases of
                    multi-turn context)
  2. decontaminate  drop anything whose user text matches an eval item
                    exactly, or overlaps it ≥ 0.8 (word-trigram Jaccard).
                    Eval items under 4 words are exempt: "go back" or "bye"
                    can't leak — they ARE the command, and banning them
                    from training would just make the model not know them.
  3. exact dedupe   same normalised user text(s) + same targets
  4. near dedupe    (optional) MinHash/LSH on user text, same target → keep one
  5. cap            at most N examples per template (stops a few templates
                    dominating after paraphrasing)
"""
from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import os
import random

from .contract import canonical, load_tools, norm_text, tools_for, validate
from . import nlu as _nlu


def users(rec) -> str:
    if rec.get("task") == "nlu":
        return norm_text(rec["text"])
    if rec.get("task") == "memory":
        return " || ".join(norm_text(t) for t in rec["turns"])
    return " || ".join(norm_text(m["content"]) for m in rec["messages"] if m["role"] == "user")


def targets(rec) -> str:
    if rec.get("task") == "nlu":
        return _nlu.canonical(rec["nlu"])
    if rec.get("task") == "memory":
        return json.dumps(rec["facts"], ensure_ascii=False)
    return " || ".join(canonical(m["content"]) for m in rec["messages"] if m["role"] == "assistant")


def shingles(text: str, n: int = 3) -> set:
    w = text.split()
    if len(w) < n:
        return {" ".join(w)}
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


class MinHashLSH:
    """Small MinHash + LSH (stdlib). 64 permutations, 16 bands × 4 rows."""

    P = (1 << 61) - 1

    def __init__(self, perms: int = 64, bands: int = 16, seed: int = 1):
        rng = random.Random(seed)
        self.ab = [(rng.randrange(1, self.P), rng.randrange(0, self.P)) for _ in range(perms)]
        self.bands, self.rows = bands, perms // bands
        self.buckets = collections.defaultdict(list)

    def signature(self, sh: set) -> list[int]:
        hs = [int(hashlib.blake2b(s.encode(), digest_size=8).hexdigest(), 16) for s in sh] or [0]
        return [min((a * h + b) % self.P for h in hs) for a, b in self.ab]

    def candidates(self, sig) -> set:
        out = set()
        for i in range(self.bands):
            out.update(self.buckets.get((i, tuple(sig[i * self.rows:(i + 1) * self.rows])), ()))
        return out

    def add(self, key, sig):
        for i in range(self.bands):
            self.buckets[(i, tuple(sig[i * self.rows:(i + 1) * self.rows]))].append(key)


def load(paths) -> list[dict]:
    out = []
    for p in paths:
        for path in sorted(glob.glob(p)) or [p]:
            with open(path, encoding="utf-8") as f:
                out += [json.loads(ln) for ln in f if ln.strip()]
    return out


def run(records, evals, tools, *, near_dup=False, cap_template=0, log=print):
    # 1. validate
    kept = []
    known_intents = set(_nlu.intents(tools))
    for r in records:
        if r.get("task") == "nlu":
            if not _nlu.validate_nlu(r, known_intents):
                kept.append(r)
            continue
        if r.get("task") == "memory":
            if not _nlu.validate_memory(r):
                kept.append(r)
            continue
        rtools = tools_for(r, tools)
        allowed = set(r.get("tools") or rtools)
        grounded = not r.get("meta", {}).get("ungrounded")
        said, ok = "", True
        for m in r["messages"]:
            if m["role"] == "user":
                said += " " + m["content"]
            elif validate(m["content"], rtools, allowed=allowed, user_text=said, grounded=grounded):
                ok = False
                break
        if ok:
            kept.append(r)
    log(f"validate:      {len(records)} -> {len(kept)}")

    # 2. decontaminate against eval user texts (4+ words only, see above)
    evals = [e for e in evals if len(users(e).split()) >= 4]
    ev_exact = {users(e) for e in evals}
    ev_sh = [shingles(users(e)) for e in evals]
    index = collections.defaultdict(set)
    for i, sh in enumerate(ev_sh):
        for s in sh:
            index[s].add(i)
    before, clean = len(kept), []
    for r in kept:
        u = users(r)
        if u in ev_exact:
            continue
        sh = shingles(u)
        cand = set().union(*(index.get(s, set()) for s in sh)) if sh else set()
        if any(jaccard(sh, ev_sh[i]) >= 0.8 for i in cand):
            continue
        clean.append(r)
    log(f"decontaminate: {before} -> {len(clean)}")

    # 3. exact dedupe
    seen, dedup = set(), []
    for r in clean:
        k = (users(r), targets(r))
        if k not in seen:
            seen.add(k)
            dedup.append(r)
    log(f"exact dedupe:  {len(clean)} -> {len(dedup)}")

    # 4. near dedupe (same target only — paraphrases with different labels stay)
    if near_dup:
        lsh, out = MinHashLSH(), []
        sigs = {}
        for i, r in enumerate(dedup):
            sh = shingles(users(r))
            sig = lsh.signature(sh)
            t = targets(r)
            chat = r.get("source") == "teacher_chat" and not r.get("task")
            # same label + near-identical words = duplicate; for teacher chats the
            # replies always differ, so near-identical USER turns alone count (stops
            # a pile-up of the same "hi aeris kaise ho" opener)
            if any((targets(dedup[j]) == t and jaccard(sh, sigs[j]) >= 0.9)
                   or (chat and dedup[j].get("source") == "teacher_chat" and not dedup[j].get("task")
                       and jaccard(sh, sigs[j]) >= 0.8)
                   for j in lsh.candidates(sig)):
                continue
            sigs[i] = sh
            lsh.add(i, sig)
            out.append(r)
        log(f"near dedupe:   {len(dedup)} -> {len(out)}")
        dedup = out

    # 5. cap per template
    if cap_template:
        per = collections.Counter()
        capped = []
        for r in dedup:
            t = r.get("meta", {}).get("template")
            if t is not None:
                per[t] += 1
                if per[t] > cap_template:
                    continue
            capped.append(r)
        log(f"cap/template:  {len(dedup)} -> {len(capped)}")
        dedup = capped
    return dedup


def main(argv=None):
    ap = argparse.ArgumentParser(description="Clean + decontaminate neutral JSONL.")
    ap.add_argument("--in", dest="inputs", nargs="+", required=True)
    ap.add_argument("--eval", nargs="+", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--near-dup", action="store_true")
    ap.add_argument("--cap-template", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1, help="shuffle seed for the output")
    a = ap.parse_args(argv)
    tools = load_tools()
    recs = load(a.inputs)
    evals = load(a.eval) if a.eval else []
    out = run(recs, evals, tools, near_dup=a.near_dup, cap_template=a.cap_template)
    random.Random(a.seed).shuffle(out)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(open(a.out, "rb").read()).hexdigest()[:16]
    print(f"wrote {len(out)} -> {a.out}  sha256:{sha}")


if __name__ == "__main__":
    main()
