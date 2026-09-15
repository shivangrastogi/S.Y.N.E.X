"""Leap-year check + days-in-month. Pure math, offline. Complements datetime_tools."""
from __future__ import annotations

import re
from typing import Optional

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
_DAYS = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def is_leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _year(text: str) -> Optional[int]:
    m = re.search(r"\b(\d{3,4})\b", text or "")
    return int(m.group(1)) if m else None


def leap_year(text: str) -> Optional[str]:
    y = _year(text)
    if y is None or not (1 <= y <= 9999):
        return None
    if is_leap(y):
        nxt = y + 1
        while not is_leap(nxt):
            nxt += 1
        return (f"Haan, {y} ek leap year hai — February me 29 din. "
                f"(Agla leap year: {nxt}.)")
    prv = y - 1
    while prv >= 1 and not is_leap(prv):
        prv -= 1
    nxt = y + 1
    while not is_leap(nxt):
        nxt += 1
    return (f"Nahi, {y} leap year nahi hai — February me 28 din. "
            f"(Aaspaas ke leap years: {prv} aur {nxt}.)")


def days_in_month(text: str) -> Optional[str]:
    t = (text or "").lower()
    mon = None
    for name, num in _MONTHS.items():
        if re.search(rf"\b{name}\b", t):
            mon = num
            break
    if mon is None:
        return None
    y = _year(t)
    n = _DAYS[mon]
    if mon == 2:
        if y is None:
            return ("February me 28 din hote hain (leap year me 29). "
                    "Saal batao to exact bata dunga.")
        n = 29 if is_leap(y) else 28
    name = [k for k, v in _MONTHS.items() if v == mon and len(k) > 3][0].title()
    tail = f" {y}" if y else ""
    return f"{name}{tail} me {n} din hote hain."
