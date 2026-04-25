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


class HinglishNormalizer:
    _PUNCT_RE = re.compile(r"[^\w\s+\-.:/%]")
    _WS_RE = re.compile(r"\s+")

    def clean(self, text: str) -> str:
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
