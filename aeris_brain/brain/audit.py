"""Dataset audit + gate — measure balance and variety instead of trusting the sampler.

    py -m brain.audit out/final/train.jsonl            # report (+ train.jsonl.audit.json)
    py -m brain.audit out/final/train.jsonl --gate     # exit 1 if any limit is broken

What it checks (limits in GATE, tune per run):
  balance      task mix, intent distribution (max share, max/min ratio, normalised entropy),
               source/family shares
  language     english / hinglish / hindi_roman / devanagari shares of user turns and the
               code-mix-index spread (all four buckets must be present)
  people       gender and region of every known name in user turns / slot values
  variety      distinct-1 / distinct-2 of user turns, the most repeated user trigram's share,
               exact-duplicate rate
  persona      AERIS replies with feminine first-person forms (must be 0), Devanagari in
               replies (must be 0), reply length (spoken: short)
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
import sys

from .diversity import NAMES
from .langmix import lang_label, mix_bucket
from .teacher import FEMININE_SELF

GATE = {
    "max_intent_share": 0.08,        # no single intent above 8 % of NLU-labelled examples
    "max_intent_ratio": 60.0,        # biggest / smallest intent count
    "min_intent_entropy": 0.80,      # normalised Shannon entropy of intents (1 = perfectly even)
    "min_mix_bucket_share": 0.04,    # every code-mix bucket ≥ 4 % of user turns
    "max_gender_skew": 0.65,         # no gender above 65 % of recognised names
    "min_distinct2": 0.25,           # distinct bigrams / bigrams over user turns
    "max_top_trigram_share": 0.02,   # the most common user trigram ≤ 2 % of turns
    "max_exact_dup_rate": 0.01,
    "max_feminine_replies": 0,
    "max_devanagari_replies": 0,
    "max_mean_reply_words": 28,
}
_NAME_INFO = {n.lower(): (g, r) for n, g, r, _ in NAMES}
_W = re.compile(r"[A-Za-z']+")


def _user_texts(r: dict) -> list[str]:
    if r.get("task") == "nlu":
        return [r["text"]]
    if r.get("task") == "memory":
        return list(r["turns"])
    return [m["content"] for m in r.get("messages", []) if m["role"] == "user"]


def _replies(r: dict) -> list[str]:
    if r.get("task"):
        return []
    return [m["content"]["text"] for m in r.get("messages", [])
            if m["role"] == "assistant" and isinstance(m["content"], dict) and m["content"].get("type") == "reply"]


def _intent(r: dict) -> str | None:
    if r.get("task") == "nlu":
        return r["nlu"]["intent"]
    return None


def _record_dup_rate(records: list[dict]) -> float:
    from .quality import targets, users
    per: dict[str, list] = collections.defaultdict(list)
    for r in records:
        per[r.get("task", "turn")].append((users(r), targets(r), tuple(r.get("memory") or ())))
    rates = [1 - len(set(k)) / len(k) for k in per.values() if k]
    return round(max(rates), 4) if rates else 0.0


def _by_task(records: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = collections.defaultdict(list)
    for r in records:
        out[r.get("task", "turn")] += _user_texts(r)
    return out


def entropy(counts) -> float:
    tot = sum(counts)
    if tot == 0 or len(counts) < 2:
        return 0.0
    h = -sum(c / tot * math.log(c / tot) for c in counts if c)
    return h / math.log(len(counts))


def audit(records: list[dict]) -> dict:
    rep: dict = {"total": len(records)}
    rep["tasks"] = dict(collections.Counter(r.get("task", "turn") for r in records))
    rep["sources"] = dict(collections.Counter(r.get("source", "?").split(">")[0] for r in records).most_common(20))

    intents = collections.Counter(i for r in records if (i := _intent(r)))
    if intents:
        tot = sum(intents.values())
        top, top_n = intents.most_common(1)[0]
        rep["intents"] = {"n": len(intents), "top": top, "top_share": round(top_n / tot, 4),
                          "max_min_ratio": round(top_n / min(intents.values()), 1),
                          "entropy": round(entropy(list(intents.values())), 3),
                          "rarest": intents.most_common()[-5:]}

    users = [u for r in records for u in _user_texts(r)]
    langs = collections.Counter(lang_label(u) for u in users)
    buckets = collections.Counter(mix_bucket(u) for u in users)
    nu = max(1, len(users))
    rep["lang"] = {k: round(v / nu, 3) for k, v in langs.most_common()}
    rep["mix_buckets"] = {k: round(v / nu, 3) for k, v in buckets.most_common()}

    genders, regions = collections.Counter(), collections.Counter()
    for u in users:
        for w in _W.findall(u):
            info = _NAME_INFO.get(w.lower())
            if info:
                genders[info[0]] += 1
                regions[info[1]] += 1
    ng = max(1, sum(genders.values()))
    rep["names"] = {"genders": {k: round(v / ng, 3) for k, v in genders.items()},
                    "regions": dict(regions), "recognised": sum(genders.values())}

    toks = [[w.lower() for w in _W.findall(u)] for u in users]
    uni = [w for t in toks for w in t]
    bi = [(a, b) for t in toks for a, b in zip(t, t[1:])]
    tri = collections.Counter(tuple(t[i:i + 3]) for t in toks for i in range(len(t) - 2))
    rep["variety"] = {"distinct1": round(len(set(uni)) / max(1, len(uni)), 3),
                      "distinct2": round(len(set(bi)) / max(1, len(bi)), 3),
                      "top_trigram": " ".join(tri.most_common(1)[0][0]) if tri else "",
                      "top_trigram_share": round(tri.most_common(1)[0][1] / nu, 4) if tri else 0.0,
                      # whole-record duplicates within each task (user turns + memory +
                      # target, as quality.py dedupes). The same question asked with
                      # different memory and a different answer is a different example.
                      "exact_dup_rate": _record_dup_rate(records)}

    replies = [t for r in records for t in _replies(r)]
    rep["persona"] = {"replies": len(replies),
                      "feminine": sum(1 for t in replies if FEMININE_SELF.search(t)),
                      "devanagari": sum(1 for t in replies if lang_label(t) == "devanagari"),
                      "mean_words": round(sum(len(t.split()) for t in replies) / max(1, len(replies)), 1),
                      "feminine_examples": [t for t in replies if FEMININE_SELF.search(t)][:3]}
    return rep


def gate(rep: dict, limits: dict = GATE) -> list[str]:
    fails = []
    it = rep.get("intents")
    if it:
        if it["top_share"] > limits["max_intent_share"]:
            fails.append(f"intent '{it['top']}' is {it['top_share']:.1%} of NLU data (> {limits['max_intent_share']:.0%})")
        if it["max_min_ratio"] > limits["max_intent_ratio"]:
            fails.append(f"intent imbalance {it['max_min_ratio']}× (> {limits['max_intent_ratio']}×)")
        if it["entropy"] < limits["min_intent_entropy"]:
            fails.append(f"intent entropy {it['entropy']} (< {limits['min_intent_entropy']})")
    for b in ("en", "en_heavy", "balanced", "hi_heavy"):
        if rep["mix_buckets"].get(b, 0) < limits["min_mix_bucket_share"]:
            fails.append(f"code-mix bucket '{b}' only {rep['mix_buckets'].get(b, 0):.1%} of user turns")
    g = rep["names"]["genders"]
    if rep["names"]["recognised"] >= 200:
        for k in ("m", "f"):
            if g.get(k, 0) > limits["max_gender_skew"]:
                fails.append(f"names skew to gender '{k}' ({g[k]:.0%})")
    v = rep["variety"]
    if v["distinct2"] < limits["min_distinct2"]:
        fails.append(f"distinct-2 {v['distinct2']} (< {limits['min_distinct2']})")
    if v["top_trigram_share"] > limits["max_top_trigram_share"]:
        fails.append(f"'{v['top_trigram']}' appears in {v['top_trigram_share']:.1%} of user turns")
    if v["exact_dup_rate"] > limits["max_exact_dup_rate"]:
        fails.append(f"exact duplicate user turns {v['exact_dup_rate']:.1%}")
    p = rep["persona"]
    if p["feminine"] > limits["max_feminine_replies"]:
        fails.append(f"{p['feminine']} AERIS replies use feminine forms, e.g. {p['feminine_examples'][:1]}")
    if p["devanagari"] > limits["max_devanagari_replies"]:
        fails.append(f"{p['devanagari']} replies in Devanagari")
    if p["replies"] and p["mean_words"] > limits["max_mean_reply_words"]:
        fails.append(f"replies average {p['mean_words']} words (spoken replies should be short)")
    return fails


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path")
    ap.add_argument("--gate", action="store_true")
    a = ap.parse_args(argv)
    with open(a.path, encoding="utf-8") as f:
        recs = [json.loads(ln) for ln in f if ln.strip()]
    rep = audit(recs)
    fails = gate(rep)
    rep["gate_failures"] = fails
    with open(a.path + ".audit.json", "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in rep.items() if k != "gate_failures"}, indent=1, ensure_ascii=False))
    print("\nGATE:", "PASS" if not fails else "FAIL")
    for x in fails:
        print("  ✗", x)
    if a.gate and fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
