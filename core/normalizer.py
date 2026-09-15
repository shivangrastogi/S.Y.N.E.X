"""Light text cleaner.

The multilingual sentence encoder used by `IntentClassifier` understands
Hinglish, Hindi, and English natively, so the previous Hinglish→English
translation map is no longer needed (and was actively harmful — it stripped
context the model could have used).

This module now only canonicalises text:
    - lowercase
    - replace non-essential punctuation with spaces
    - collapse repeated whitespace

URL-safe characters (`/`, `:`, `.`, `-`, `+`, `%`) are preserved so the
entity extractor (C2) can still pull URLs and math expressions out of
cleaned text.
"""

from __future__ import annotations

import re

from core.cache_registry import bounded_cache


_PUNCT_RE = re.compile(r"[^\w\s+\-.:/%]")
_WS_RE = re.compile(r"\s+")


# ── Hinglish / SMS shorthand canonicalization (Normalizer v2) ────────── #
#
# Real users type "chrome kro", "time kya h", "screenshot le lo jldy" — the
# neural model half-copes, but the exact-match fast path and k-NN index are
# far more reliable when every surface form of a word collapses to ONE
# canonical token. Since this runs on BOTH training patterns and live
# queries (shared path via intent_loader), a pattern written "karo" and a
# query typed "kro" now meet at "karo".
#
# CURATION RULE: whole-token replacement only, and only forms that are
# UNAMBIGUOUS in a command context. Ambiguous single letters (r, n, k, pl)
# are deliberately excluded — a wrong expansion corrupts every utterance
# that contains the token, which is worse than not expanding at all.
_SHORTHAND: dict[str, str] = {
    # kar-family (do/make) — the most frequent Hinglish verb
    "kr": "kar", "kro": "karo", "krna": "karna",
    "krke": "karke", "kre": "kare", "krdo": "kardo", "krde": "karde",
    "kidhr": "kidhar", "kdhr": "kidhar",
    # copulas / fillers
    "h": "hai", "hn": "haan", "nai": "nahi", "nhi": "nahi", "nhin": "nahin",
    "q": "kyun", "kyu": "kyun", "kyo": "kyun",
    # SMS English
    "nd": "and", "bt": "but", "yr": "yaar", "plz": "please",
    "pls": "please", "plss": "please", "u": "you", "ur": "your",
    "abt": "about", "coz": "because", "cuz": "because", "bcoz": "because",
    "wat": "what", "wt": "what", "thx": "thanks", "thnx": "thanks",
    "msg": "message", "pic": "picture", "vid": "video",
    "jldi": "jaldi", "jldy": "jaldi", "jaldii": "jaldi",
    "bnd": "band", "khl": "khol", "chlo": "chalo",
    "gana": "gaana", "gne": "gaane", "bta": "bata", "dikao": "dikhao",
}

# Collapse 3+ repeated LETTERS to 2 ("plssss" → "plss" → "please",
# "haaaan" → "haan"). Digits are excluded — "1000" must NOT become "100".
_REPEAT_RE = re.compile(r"([a-z])\1{2,}")


def _expand_token(tok: str) -> str:
    mapped = _SHORTHAND.get(tok)
    if mapped is not None:
        return mapped
    # de-elongate then retry ("haaan" → "haan" → mapped, "yesss" → "yess")
    squeezed = _REPEAT_RE.sub(r"\1\1", tok)
    if squeezed != tok:
        return _SHORTHAND.get(squeezed, squeezed)
    return tok


# Module-level cache so repeated normalization of the same utterance
# (very common: every classifier sees the same query, then entity
# extractor sees it again, then state-manager logs it) hits in O(1).
# Subscribes to memory_pressure via the registry — auto-shrinks on
# warning, clears on critical.
@bounded_cache(maxsize=4096, name="normalizer.clean")
def _clean_impl(text: str) -> str:
    text = text.lower().strip()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    text = text.strip()
    if not text:
        return ""
    # Token-level shorthand expansion. Tokens carrying URL/math punctuation
    # (., :, /, +, -, %) are left untouched so links and expressions survive.
    out = []
    for tok in text.split(" "):
        if any(ch in tok for ch in "./:+-%"):
            out.append(tok)
        else:
            out.append(_expand_token(tok))
    return " ".join(out)


class HinglishNormalizer:
    _PUNCT_RE = _PUNCT_RE   # kept as class attrs for back-compat
    _WS_RE = _WS_RE

    def clean(self, text: str) -> str:
        if not text:
            return ""
        return _clean_impl(text)

    def _legacy_clean(self, text: str) -> str:
        """Pre-cache implementation kept around in case anyone monkey-patches
        the regex. Same output as ``clean`` but bypasses the LRU."""
        if not text:
            return ""
        text = text.lower().strip()
        text = self._PUNCT_RE.sub(" ", text)
        text = self._WS_RE.sub(" ", text)
        return text.strip()

    # Backwards-compat alias for callers still using the old name.
    def normalize(self, text: str) -> str:
        return self.clean(text)


if __name__ == "__main__":
    n = HinglishNormalizer()
    samples = [
        "Bhai Chrome kholo!",
        "5 baje YouTube pe Arijit ka gaana chala do.",
        "https://github.com/user/repo kholo",
        "12 + 7 * 3 calculate karo",
        "  multiple   spaces   here  ",
    ]
    for s in samples:
        print(f"{s!r:60s} -> {n.clean(s)!r}")
