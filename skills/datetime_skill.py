"""Date/time intelligence by voice — world clock, date math, countdowns.

100% local (core/datetime_tools uses stdlib zoneinfo — full IANA tz DB,
no network).
"""
from __future__ import annotations

import re

from core.skill_registry import skill

_PLACE_RE = re.compile(
    r"(?:me|mein| me|in|at)\s+([a-z][a-z\s]+?)\s+"
    r"(?:me|mein|kitne|kya|ka|time|baje|abhi)|"
    r"([a-z][a-z ]+?)\s+(?:ka|me|mein)\s+(?:time|samay|baje)",
    re.IGNORECASE)


@skill(
    name="world_time",
    description="Current time in any city/country (offline, stdlib zoneinfo).",
    patterns=[
        "abhi london me kitne baje hain", "new york ka time kya hai",
        "tokyo me kya time hua", "world clock", "dubai me kitne baje hain",
        "usa ka time batao", "london me time kya hai",
        "kisi aur country ka time", "wahan kitne baje honge",
    ],
    required_entities=[],
)
def world_time(slots: dict) -> str:
    from core.datetime_tools import world_time as _wt, _CITY_ZONE
    text = (slots.get("raw_text") or slots.get("text") or "").lower()
    # Find a known place mentioned anywhere in the utterance.
    place = None
    for city in sorted(_CITY_ZONE, key=len, reverse=True):
        if city in text:
            place = city
            break
    if not place:
        m = _PLACE_RE.search(text)
        if m:
            place = (m.group(1) or m.group(2) or "").strip()
    if not place:
        return ("Kis sheher ka time chahiye, sir? Jaise: 'london me kitne "
                "baje hain'.")
    out = _wt(place)
    return out or f"'{place}' ka timezone nahi pehchana — sheher ka naam clear bolo."


@skill(
    name="date_math",
    description="Add/subtract days, weeks, months, years from today (offline).",
    patterns=[
        "aaj se 45 din baad kaunsi date hogi", "30 din baad ki date",
        "3 hafte baad kya date hogi", "2 mahine baad kaunsi date",
        "10 din pehle kya date thi", "1 saal baad ki date",
        "aaj se kitne din baad", "date nikalo aage ki",
    ],
    required_entities=[],
)
def date_math(slots: dict) -> str:
    from core.datetime_tools import date_math as _dm
    text = slots.get("raw_text") or slots.get("text") or ""
    out = _dm(text)
    return out or ("Kitne din/hafte/mahine? Jaise: 'aaj se 45 din baad "
                   "kaunsi date hogi'.")


@skill(
    name="days_until",
    description="Countdown of days to a date or fixed occasion (offline).",
    patterns=[
        "new year me kitne din bache hain", "kitne din bache hain",
        "15 august me kitne din bache", "christmas me kitne din",
        "republic day me kitne din bache", "26 january tak kitne din",
        "kitne din bache hain us date tak", "us din tak kitne din",
    ],
    required_entities=[],
)
def days_until(slots: dict) -> str:
    from core.datetime_tools import days_until as _du
    text = slots.get("raw_text") or slots.get("text") or ""
    out = _du(text)
    return out or ("Kis din tak, sir? Ek date ya occasion bolo — jaise "
                   "'15 august me kitne din bache' ya 'christmas'. (Diwali/"
                   "holi jaise moving festivals ke liye date bata do.)")


@skill(
    name="age_calc",
    description="Work out age from a birthdate or birth year (offline).",
    patterns=[
        "meri age kya hai", "umar batao", "age calculate karo",
        "main 1995 me paida hua meri age kya hai", "kitne saal ka hoon main",
        "15 august 2000 ko born hua age batao", "birthday se age nikalo",
        "meri umar kitni hai",
    ],
    required_entities=[],
)
def age_calc(slots: dict) -> str:
    from core.datetime_tools import age_from
    text = slots.get("raw_text") or slots.get("text") or ""
    out = age_from(text)
    return out or ("Aapki birthdate ya birth-year bolo, sir — jaise 'main "
                   "1995 me paida hua' ya '15 aug 2000 ko born hua'.")


@skill(
    name="day_of_week",
    description="Which weekday a given date falls on (offline).",
    patterns=[
        "15 august 2027 ko kaunsa din hai", "26 january 2027 ko kaunsa din",
        "is date ko kya din tha", "kaunsa din hoga us date ko",
        "din batao date ka", "15 august ko kaunsa din",
        "2027 diwali kaunsa din", "kya din hai us tareekh ko",
    ],
    required_entities=[],
)
def day_of_week(slots: dict) -> str:
    from core.datetime_tools import day_of_week as _dow
    text = slots.get("raw_text") or slots.get("text") or ""
    out = _dow(text)
    return out or ("Poori date do, sir (din + mahina, saal optional) — "
                   "jaise '15 august 2027 ko kaunsa din hai'.")


@skill(
    name="time_until",
    description="How much time is left until a clock time today (offline).",
    patterns=[
        "5 baje tak kitna time hai", "8 pm tak kitni der hai",
        "kitna time bacha hai 5 baje tak", "9 baje tak kitna time",
        "10 pm tak kitni der", "3 baje tak kitna time bacha",
        "lunch time tak kitna time",
    ],
    required_entities=[],
)
def time_until(slots: dict) -> str:
    from core.datetime_tools import time_until as _tu
    text = slots.get("raw_text") or slots.get("text") or ""
    out = _tu(text)
    return out or ("Kis time tak, sir? Jaise '5 baje tak kitna time hai' "
                   "ya '8 pm tak kitni der'.")


@skill(
    name="timezone_convert",
    description="Convert a clock time between two cities/timezones (offline zoneinfo).",
    patterns=[
        "3pm ist london me kitne baje", "meeting 5pm india new york me kitne baje",
        "ye time london me kya hoga", "10 am dubai me kitne baje india me",
        "time convert karo zone me", "5pm ko tokyo me kitne baje",
        "india ka 3 baje usa me kya time",
    ],
    required_entities=[],
)
def timezone_convert(slots: dict) -> str:
    from core.datetime_tools import convert_time_zone
    out = convert_time_zone(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Time aur do sheher bolo, sir — jaise '3pm india london me "
                   "kitne baje'. (Ek sheher do to India se maan lunga.)")
