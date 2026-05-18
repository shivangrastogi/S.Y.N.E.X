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
    return text.strip()


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
