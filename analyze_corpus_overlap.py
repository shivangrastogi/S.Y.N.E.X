"""Which training patterns actually confuse the router? (§6.40)

    python analyze_corpus_overlap.py            # ranked report
    python analyze_corpus_overlap.py --json     # machine-readable

`docs/ROUTING_ACCURACY_AUDIT.md` measured ~50% routing accuracy on natural
phrasings and blamed 587-intent corpus bloat. The doc's suggested fix is to cut
the "formula-calculator" intents, which is the user's data decision — so this
tool **changes nothing**. It produces the evidence that decision needs.

### Why not just match intent names

The obvious approach is a regex over intent names for calculator-ish words.
Tried first, and it was actively dangerous: `_to_` and `list` swept in
`set_reminder`, `translate_to_hindi`, `clipboard_to_phone` and
`start_calibration_wizard`. A trim list that recommends deleting
`set_reminder` is worse than no trim list, because it looks authoritative.

Name-matching answers "does this sound like a formula skill". The question
that matters is **"do two intents claim phrasings a human could not tell
apart"** — and that is measurable from the corpus alone, with no training run
and no judgement about which skills are worth keeping.

### What it measures

Exact duplicate phrasings across intents are already handled (the pattern
unification pass: one owner per phrase, with a guard test). What remains is
**near**-duplicates: patterns that differ by a filler word or word order and
therefore land in the same region of embedding space while claiming different
labels. Those are what make a k-NN or cosine router pick the wrong one.

For each pair of intents it reports how many of their patterns are near
neighbours, and the closest examples — so a decision is made on the actual
colliding phrasings, not on a guess about a name.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CORPUS = os.path.join("data", "training_corpus.json")

# Words that carry no topic. Two patterns sharing only these are not similar
# in any way a router could use.
FILLER = {
    "a", "an", "the", "is", "are", "to", "for", "of", "in", "on", "at", "my",
    "me", "please", "plz", "karo", "kar", "kro", "do", "de", "dedo", "dena",
    "aeris", "jarvis", "hey", "ok", "okay", "kya", "hai", "ho", "ka", "ki",
    "ke", "ko", "se", "mera", "meri", "mujhe", "ye", "yeh", "wo", "woh",
    "aur", "bata", "batao", "dikha", "dikhao", "kitna", "kitne", "na", "bhi",
}

_TOK = re.compile(r"[a-z0-9]+")


def tokens(pattern: str) -> frozenset:
    return frozenset(t for t in _TOK.findall((pattern or "").lower())
                     if t not in FILLER)


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load(path: str = CORPUS) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def analyse(corpus: dict, threshold: float = 0.6, min_tokens: int = 2) -> dict:
    """Near-duplicate patterns claimed by different intents.

    ``min_tokens`` drops one-content-word patterns ("chrome"), which collide
    with everything and are a separate problem from genuine near-duplicates.
    """
    prepared = {}
    for intent, spec in corpus.items():
        pats = []
        for p in (spec or {}).get("patterns", []) or []:
            t = tokens(p)
            if len(t) >= min_tokens:
                pats.append((p, t))
        if pats:
            prepared[intent] = pats

    pairs = defaultdict(list)
    for a, b in combinations(sorted(prepared), 2):
        for pa, ta in prepared[a]:
            for pb, tb in prepared[b]:
                s = jaccard(ta, tb)
                if s >= threshold:
                    pairs[(a, b)].append((round(s, 3), pa, pb))

    ranked = []
    for (a, b), hits in pairs.items():
        hits.sort(key=lambda h: -h[0])
        ranked.append({
            "intents": [a, b],
            "collisions": len(hits),
            "worst": hits[0][0],
            "examples": hits[:3],
        })
    ranked.sort(key=lambda r: (-r["collisions"], -r["worst"]))

    involved = defaultdict(int)
    for r in ranked:
        for i in r["intents"]:
            involved[i] += r["collisions"]

    return {
        "intents": len(corpus),
        "patterns": sum(len((v or {}).get("patterns", []) or [])
                        for v in corpus.values()),
        "threshold": threshold,
        "colliding_pairs": len(ranked),
        "pairs": ranked,
        "worst_intents": sorted(involved.items(), key=lambda kv: -kv[1])[:20],
    }


def render(result: dict, limit: int = 15) -> str:
    out = [
        "",
        "Corpus overlap analysis",
        "=" * 60,
        f"  intents            {result['intents']}",
        f"  patterns           {result['patterns']}",
        f"  similarity floor   {result['threshold']}",
        f"  colliding pairs    {result['colliding_pairs']}",
        "",
        "Nothing was changed. This is evidence for a decision, not a decision.",
        "",
    ]
    if not result["pairs"]:
        out.append("No near-duplicate phrasings above the threshold.")
        return "\n".join(out)

    out += ["Intents most often confusable with another intent:", ""]
    for name, n in result["worst_intents"][:limit]:
        out.append(f"  {n:4}  {name}")
    out += ["", f"Worst pairs (top {limit}):", ""]
    for r in result["pairs"][:limit]:
        a, b = r["intents"]
        out.append(f"  {r['collisions']:3} collisions  {a}  <->  {b}")
        for sim, pa, pb in r["examples"]:
            out.append(f"        {sim:.2f}  {pa!r}")
            out.append(f"              {pb!r}")
        out.append("")
    out += [
        "How to read this:",
        "  A pair means both intents claim phrasings a router cannot separate.",
        "  The fix is usually to delete or re-word the colliding PATTERNS -",
        "  not to delete a skill. Keep the skill, drop the phrasing it stole.",
        "",
    ]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    corpus = load(args.corpus)
    result = analyse(corpus, threshold=args.threshold)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render(result, limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
