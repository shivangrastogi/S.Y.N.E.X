"""Marks-percentage + sleep-cycle bedtime calculator. Pure math, offline."""
from __future__ import annotations

import re
from typing import Optional


def _grade(pct: float) -> str:
    if pct >= 90:
        return "A+ (outstanding)"
    if pct >= 80:
        return "A (excellent)"
    if pct >= 70:
        return "B (very good)"
    if pct >= 60:
        return "C (good)"
    if pct >= 50:
        return "D (average)"
    if pct >= 33:
        return "E (pass)"
    return "fail"


def marks_percentage(text: str) -> Optional[str]:
    t = (text or "").lower()
    obtained = total = None
    # Hindi "Y me se X" -> total Y, obtained X
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:me se|mese|out of|/|upon)\s*(\d+(?:\.\d+)?)", t)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if "me se" in t or "mese" in t or "upon" in t:
            total, obtained = a, b
        else:                    # "X out of Y" / "X/Y"
            obtained, total = a, b
    else:
        om = re.search(r"(?:obtained|scored|got|mila|aaye|marks)\s*(\d+(?:\.\d+)?)", t)
        tm = re.search(r"(?:out of|total|max|maximum)\s*(\d+(?:\.\d+)?)", t)
        if om and tm:
            obtained, total = float(om.group(1)), float(tm.group(1))
        else:
            nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", t)]
            if len(nums) >= 2:
                obtained, total = nums[0], nums[1]
    if obtained is None or total is None or total <= 0:
        return ("Marks aur total do — jaise '450 out of 500' ya "
                "'500 me se 450'.")
    if obtained > total:         # user likely gave them the other way round
        obtained, total = total, obtained
    pct = obtained / total * 100
    return (f"{_fmt(obtained)}/{_fmt(total)} = {pct:.2f}% — {_grade(pct)}.")


# ---- sleep cycles: 90 min each, ~15 min to fall asleep ----
_CYCLE = 90
_FALL = 15


def _period_shift(text: str, hh: int) -> int:
    """Apply raat/subah/shaam/dopahar context to a 12-hour hour."""
    if hh == 0 or hh > 12:
        return hh
    if re.search(r"\b(raat|night|pm|shaam|sham|evening|dopahar|afternoon)\b", text):
        if re.search(r"\b(dopahar|afternoon)\b", text) and hh == 12:
            return 12
        return hh if hh == 12 else hh + 12
    if re.search(r"\b(subah|morning|am|sawere|savere)\b", text):
        return 0 if hh == 12 else hh
    return hh


def _parse_clock(text: str) -> Optional[int]:
    """Return minutes since midnight for the first time expression, else None."""
    t = text.lower()
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)\b", t)
    if m:
        hh = int(m.group(1)) % 12
        mm = int(m.group(2)) if m.group(2) else 0
        if m.group(3).startswith("p"):
            hh += 12
        return hh * 60 + mm
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(?:baje|bje|o'?clock)\b", t)
    if m:
        hh = int(m.group(1)) % 24
        mm = int(m.group(2)) if m.group(2) else 0
        return _period_shift(t, hh) * 60 + mm
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", t)
    if m:
        return (int(m.group(1)) % 24) * 60 + int(m.group(2))
    return None


def _fmt_clock(mins: int) -> str:
    mins %= 24 * 60
    h, m = divmod(mins, 60)
    ap = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ap}"


_WAKE_RE = re.compile(r"\b(uth\w*|wake|jaag\w*|jag\w*|get up)\b")
_SLEEP_RE = re.compile(r"\b(so\w*|sleep\w*|sote|sona|sou?n)\b")


def _wake_mode(t: str) -> bool:
    """The given time is a WAKE time when the wake-verb sits closest to it."""
    clock_m = re.search(r"\b\d{1,2}(?::\d{2})?\b", t)
    pos = clock_m.start() if clock_m else 0

    def _closest(rx):
        best = None
        for m in rx.finditer(t):
            d = min(abs(m.start() - pos), abs(m.end() - pos))
            if best is None or d < best:
                best = d
        return best
    w, s = _closest(_WAKE_RE), _closest(_SLEEP_RE)
    if w is None:
        return False
    if s is None:
        return True
    return w < s     # wake-verb nearer the time -> time is the wake time


def sleep_cycle(text: str) -> Optional[str]:
    t = (text or "").lower()
    clock = _parse_clock(t)
    if clock is None:
        return ("Time batao — jaise 'raat 11 baje soun to kab uthu' ya "
                "'6 am uthna hai to kab soun'.")
    wake_mode = _wake_mode(t)
    cycles = [6, 5, 4]
    if wake_mode:
        # given wake time, when to sleep for N full cycles
        opts = [_fmt_clock(clock - _FALL - c * _CYCLE) for c in cycles]
        body = ", ".join(f"{c} cycle: {o}" for c, o in zip(cycles, opts))
        return (f"{_fmt_clock(clock)} uthne ke liye in me se kisi time so jao — "
                f"{body}. (~15 min sone me lagte hain.)")
    # given bedtime, best wake times
    opts = [_fmt_clock(clock + _FALL + c * _CYCLE) for c in cycles]
    body = ", ".join(f"{c} cycle: {o}" for c, o in zip(cycles, opts))
    return (f"{_fmt_clock(clock)} soye to fresh uthne ke best times — {body}. "
            "(Full 90-min cycles pe uthna behtar hota hai.)")


def _fmt(n: float) -> str:
    return str(int(n)) if abs(n - round(n)) < 1e-9 else f"{n:.2f}"


# CBSE-style CGPA<->percentage (percentage = CGPA * 9.5). User may override
# the multiplier by saying "out of 10" scale variants; we keep the standard.
_CGPA_MULT = 9.5


def cgpa_percentage(text: str) -> Optional[str]:
    t = (text or "").lower()
    # explicit CGPA -> percentage (number may sit before or after the word)
    cm = re.search(r"(\d+(?:\.\d+)?)\s*(?:cgpa|gpa|grade point)", t) or \
        re.search(r"(?:cgpa|gpa|grade point)\s*(?:is|hai|of|=|:)?\s*(\d+(?:\.\d+)?)", t)
    pm = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|percentage|feesdi)", t)
    to_cgpa = bool(re.search(r"\b(?:to|into|me|mein)\s*(?:cgpa|gpa)\b", t)) or \
        (pm and re.search(r"\bcgpa\b", t) and not cm)
    if cm and not to_cgpa:
        cgpa = float(cm.group(1))
        if not (0 <= cgpa <= 10):
            return "CGPA 0-10 ke beech do."
        return (f"{_fmt(cgpa)} CGPA = {_fmt(cgpa * _CGPA_MULT)}% "
                f"(formula: CGPA x 9.5).")
    if pm:
        pct = float(pm.group(1))
        if not (0 <= pct <= 100):
            return "Percentage 0-100 ke beech do."
        return (f"{_fmt(pct)}% = {_fmt(pct / _CGPA_MULT)} CGPA "
                f"(formula: % / 9.5).")
    if cm:
        cgpa = float(cm.group(1))
        return (f"{_fmt(cgpa)} CGPA = {_fmt(cgpa * _CGPA_MULT)}% "
                f"(formula: CGPA x 9.5).")
    return ("CGPA ya percentage do — jaise '8.5 cgpa to percentage' ya "
            "'76 percent to cgpa'.")
