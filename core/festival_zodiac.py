"""Fixed-date holiday countdown + Chinese zodiac. Pure math, offline.

Only holidays with a FIXED calendar date are here — lunar/luni-solar festivals
(Diwali, Holi, Eid) move every year and would need an ephemeris, so we don't
guess them.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

# name aliases -> (month, day)
_FIXED = {
    "new year": (1, 1), "naya saal": (1, 1),
    "republic day": (1, 26), "gantantra": (1, 26), "26 january": (1, 26),
    "valentine": (2, 14), "valentines day": (2, 14),
    "womens day": (3, 8), "mahila diwas": (3, 8),
    "labour day": (5, 1), "may day": (5, 1), "mazdoor": (5, 1),
    "yoga day": (6, 21), "yoga diwas": (6, 21),
    "independence day": (8, 15), "swatantrata": (8, 15), "15 august": (8, 15),
    "teachers day": (9, 5), "shikshak": (9, 5),
    "gandhi jayanti": (10, 2), "2 october": (10, 2),
    "childrens day": (11, 14), "bal diwas": (11, 14),
    "christmas": (12, 25), "bada din": (12, 25),
    "new years eve": (12, 31),
}


def festival_countdown(text: str, today: Optional[_dt.date] = None) -> Optional[str]:
    t = (text or "").lower()
    today = today or _dt.date.today()
    hit = None
    for name, md in _FIXED.items():
        if name in t:
            hit = (name, md)
            break
    if hit is None:
        return ("Fixed-date festival batao — jaise 'independence day', "
                "'christmas', 'new year'. (Diwali/Holi har saal badalte hain.)")
    name, (mon, day) = hit
    target = _dt.date(today.year, mon, day)
    if target < today:
        target = _dt.date(today.year + 1, mon, day)
    days = (target - today).days
    label = name.title()
    if days == 0:
        return f"Aaj hi {label} hai! Mubarak ho."
    when = target.strftime("%d %B %Y")
    return f"{label} me {days} din baaki ({when})."


_ANIMALS = ["Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
            "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"]
_CZ_TRAIT = {
    "Rat": "smart, resourceful", "Ox": "diligent, dependable",
    "Tiger": "brave, competitive", "Rabbit": "gentle, elegant",
    "Dragon": "confident, ambitious", "Snake": "wise, intuitive",
    "Horse": "energetic, free", "Goat": "calm, creative",
    "Monkey": "clever, curious", "Rooster": "observant, hardworking",
    "Dog": "loyal, honest", "Pig": "generous, easygoing",
}


def chinese_zodiac(text: str) -> Optional[str]:
    m = re.search(r"\b(\d{4})\b", text or "")
    if not m:
        return ("Janam saal batao — jaise '1998 ka chinese zodiac' — "
                "main animal sign bata dunga.")
    year = int(m.group(1))
    if not (0 <= year <= 9999):
        return "Saal 4-digit me do — jaise 1998."
    animal = _ANIMALS[(year - 4) % 12]
    return f"{year} = Year of the {animal} ({_CZ_TRAIT[animal]})."
