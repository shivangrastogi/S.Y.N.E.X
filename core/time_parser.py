"""Hinglish/English natural-time-string parser → datetime.

Handles the time forms the brain commonly extracts from reminder utterances:

    "5 pm"            → today 17:00 (or tomorrow if past)
    "5:30 am"         → today 05:30 (or tomorrow if past)
    "5 baje shaam"    → today 17:00
    "5 baje subah"    → today 05:00
    "5 baje"          → today 17:00 (heuristic: business-hours assumption)
    "kal 9 baje"      → tomorrow 09:00 (subah default)
    "kal 9 baje raat" → tomorrow 21:00
    "10 minute mein"  → now + 10 min
    "30 minutes"      → now + 30 min
    "1 hour mein"     → now + 1 hour
    "tomorrow at 4 pm"→ tomorrow 16:00

Returns ``None`` if no time signal could be extracted.
"""

from __future__ import annotations

import re
from datetime import datetime, time as dtime, timedelta
from typing import Optional


_REL_RE = re.compile(
    r"(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs|second|seconds|sec|secs)\s*(mein|me|in)?",
    re.IGNORECASE,
)

_CLOCK_RE = re.compile(
    r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje)?",
    re.IGNORECASE,
)

_MERIDIEM_HINTS = {
    "subah":  "am",   # morning
    "morning": "am",
    "shaam":  "pm",   # evening
    "evening":"pm",
    "raat":   "pm",   # night
    "night":  "pm",
    "dopahar":"pm",   # afternoon
    "afternoon":"pm",
}


def _today_at(hour: int, minute: int = 0, base: Optional[datetime] = None) -> datetime:
    base = base or datetime.now()
    candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= base:
        candidate += timedelta(days=1)
    return candidate


def parse_time_string(text: str, base: Optional[datetime] = None) -> Optional[datetime]:
    """Best-effort parse. Returns absolute datetime, or None on failure."""
    if not text:
        return None
    base = base or datetime.now()
    t = text.lower().strip()

    rel_match = _REL_RE.search(t)
    if rel_match:
        n = int(rel_match.group(1))
        unit = rel_match.group(2)
        if unit.startswith("min"):
            return base + timedelta(minutes=n)
        if unit.startswith("hour") or unit.startswith("hr"):
            return base + timedelta(hours=n)
        if unit.startswith("sec"):
            return base + timedelta(seconds=n)

    add_days = 0
    if "kal" in t or "tomorrow" in t:
        add_days = 1
    elif "parso" in t:
        add_days = 2

    meridiem_hint = None
    for word, m in _MERIDIEM_HINTS.items():
        if word in t:
            meridiem_hint = m
            break

    clock_match = _CLOCK_RE.search(t)
    if not clock_match:
        return None

    hour = int(clock_match.group(1))
    minute = int(clock_match.group(2) or 0)
    explicit = (clock_match.group(3) or "").lower()

    if explicit == "am":
        if hour == 12:
            hour = 0
    elif explicit == "pm":
        if hour < 12:
            hour += 12
    elif explicit == "baje":
        if meridiem_hint == "am":
            if hour == 12:
                hour = 0
        elif meridiem_hint == "pm" and hour < 12:
            hour += 12
        elif 1 <= hour <= 7:
            # bare "5 baje" without subah/shaam — default to PM for daytime hours
            hour += 12

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    if add_days > 0:
        anchor = (base + timedelta(days=add_days)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        return anchor

    return _today_at(hour, minute, base=base)
