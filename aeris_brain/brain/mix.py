"""Blend cleaned sources into the final training file at chosen proportions.

    py -m brain.mix --total 400000 --out out/final/train.jsonl \
        template=out/clean/template.jsonl:0.42 \
        hinglish_top=out/clean/hinglish_top.jsonl:0.14 \
        massive=out/clean/massive.jsonl:0.08 \
        mobile_actions=out/clean/mobile_actions.jsonl:0.02 \
        when2call=out/clean/when2call.jsonl:0.06 \
        xlam=out/clean/xlam.jsonl:0.08 \
        chat=out/clean/chat.jsonl:0.12 \
        paraphrase=out/clean/paraphrase.jsonl:0.08

A source smaller than its share is repeated at most --max-repeat times
(default 2); the shortfall is reported, never silently filled. The mix
is a hyper-parameter — the training notebook can sweep it.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import random


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sources", nargs="+", help="name=path:weight")
    ap.add_argument("--total", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-repeat", type=float, default=2.0)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    specs = []
    for s in a.sources:
        name, rest = s.split("=", 1)
        path, w = rest.rsplit(":", 1)
        specs.append((name, path, float(w)))
    wsum = sum(w for _, _, w in specs)
    out, report = [], {}
    for name, path, w in specs:
        if not os.path.exists(path):
            print(f"  {name}: {path} missing — skipped")
            continue
        with open(path, encoding="utf-8") as f:
            pool = [json.loads(ln) for ln in f if ln.strip()]
        want = round(a.total * w / wsum)
        cap = int(len(pool) * a.max_repeat)
        take = min(want, cap)
        rng.shuffle(pool)
        picked = [pool[i % len(pool)] for i in range(take)] if pool else []
        out += picked
        report[name] = {"available": len(pool), "wanted": want, "taken": take,
                        "short_by": max(0, want - take)}
    rng.shuffle(out)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(open(a.out, "rb").read()).hexdigest()[:16]
    fam = collections.Counter(r.get("family") for r in out)
    report["_total"] = len(out)
    report["_families"] = dict(fam)
    report["_sha256"] = sha
    with open(a.out + ".mix.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    for k, v in report.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
