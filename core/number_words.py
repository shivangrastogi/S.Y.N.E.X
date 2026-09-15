"""Number → words, Indian (lakh/crore) and International (million/billion).

Pure logic, no data files, no network. Handles 0..99 crore range and a
decimal part ("1234.5" → "… point five").
"""
from __future__ import annotations

import re
from typing import Optional

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven",
         "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
         "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]


def _two(n: int) -> str:
    if n < 20:
        return _ONES[n]
    t, o = divmod(n, 10)
    return _TENS[t] + (f"-{_ONES[o]}" if o else "")


def _three(n: int) -> str:
    h, rest = divmod(n, 100)
    parts = []
    if h:
        parts.append(f"{_ONES[h]} hundred")
    if rest:
        parts.append(_two(rest))
    return " ".join(parts)


def _indian(n: int) -> str:
    """Indian numbering: crore, lakh, thousand, hundred."""
    if n == 0:
        return "zero"
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1000)
    if crore:
        parts.append(f"{_indian(crore)} crore")
    if lakh:
        parts.append(f"{_two(lakh)} lakh")
    if thousand:
        parts.append(f"{_two(thousand)} thousand")
    if n:
        parts.append(_three(n))
    return " ".join(parts)


def _international(n: int) -> str:
    """International: billion, million, thousand. Each group is 0-999."""
    if n == 0:
        return "zero"
    parts = []
    for value, name in ((1_000_000_000, "billion"), (1_000_000, "million"),
                        (1000, "thousand")):
        q, n = divmod(n, value)
        if q:
            parts.append(f"{_three(q)} {name}")
    if n:
        parts.append(_three(n))
    return " ".join(parts)


def number_to_words(value: str, system: str = "indian") -> Optional[str]:
    """'1234567' → 'twelve lakh thirty-four thousand five hundred sixty-seven'.
    ``system``: 'indian' (lakh/crore) or 'international' (million/billion)."""
    s = str(value).strip().replace(",", "")
    m = re.match(r"^(-)?(\d+)(?:\.(\d+))?$", s)
    if not m:
        return None
    neg, intpart, dec = m.group(1), m.group(2), m.group(3)
    n = int(intpart)
    if n > 999_99_99_999:            # cap ~ 999 crore for sane output
        return None
    words = _indian(n) if system == "indian" else _international(n)
    if neg:
        words = "minus " + words
    if dec:
        digits = " ".join(_ONES[int(d)] for d in dec)
        words += " point " + digits
    return words


def parse_and_spell(text: str) -> Optional[str]:
    """Pull a number from an utterance and spell it. Picks Indian unless
    'international'/'million'/'billion' hinted."""
    t = (text or "").lower()
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", t)
    if not m:
        return None
    system = ("international" if re.search(r"international|million|billion", t)
              else "indian")
    words = number_to_words(m.group(0), system)
    if not words:
        return None
    return f"{m.group(0)} = {words}."
