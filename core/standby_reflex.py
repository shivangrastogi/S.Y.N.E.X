"""Tier-0 reflexes — trivial queries answered WITHOUT waking the heavy brain.

The whole point of standby is keeping the ~2GB brain dormant. Yet today every
wake spins it up — even "what time is it". A reflex router answers a small set
of trivial, deterministic queries (time, date, day, "you there?") entirely in
Tier-0, so the brain stays dormant: a real power win, and an instant reply.

Matching is deliberately *tight* — an exact-phrase set after light
normalisation — so anything beyond these canned forms (e.g. "what time does the
pharmacy close") falls through to the brain rather than being mis-answered. The
clock is injected, so the formatted replies are unit-tested deterministically.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Callable, Optional


def _norm(text: str) -> str:
    t = (text or "").lower().replace("'", "")
    t = re.sub(r"[?.!,]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Exact normalised phrases per reflex. Keep these short and unambiguous — a
# longer/edge phrasing simply isn't matched and goes to the brain (safe default).
_TIME = {
    "time", "the time", "time now", "current time",
    "what time", "what time is it", "whats the time", "what is the time",
    "time kya hai", "kitne baje", "kitne baje hai", "kitne baj rahe hai",
    "abhi kitne baje hai", "samay kya hai",
}
_DATE = {
    "date", "todays date", "the date", "whats the date", "what is the date",
    "what date is it", "what is todays date", "tareekh kya hai",
    "aaj ki tareekh", "aaj kaunsi tareekh hai", "aaj ki tareekh kya hai",
}
_DAY = {
    "what day", "what day is it", "what day is today", "which day",
    "kaunsa din", "kaunsa din hai", "aaj kaunsa din hai", "aaj kaun sa din hai",
}
_PRESENCE = {
    "are you there", "you there", "are you awake", "are you up",
    "sun rahe ho", "sun rahe ho aap", "aap wahan ho",
}

# Control commands — these ACT on the OS (power state), they don't just reply.
_SLEEP = {
    "go to sleep", "sleep now", "go dormant", "power down", "rest now",
    "so jao", "sona", "so jaao", "sleep",
}
_WAKE = {
    "wake up", "wake up now", "get ready", "spin up",
    "jaago", "jag jao", "uth jao",
}
_PAUSE = {
    "pause", "pause listening", "stop listening", "mute yourself",
    "chup ho jao", "sun na band karo", "ruk jao",
}
_STATUS = {
    "status", "system status", "standby status", "your status",
    "report", "health check", "how are you doing",
}


class ReflexRouter:
    """Answers trivial queries in Tier-0. ``match`` returns a reply or None."""

    def __init__(self, *, now: Callable[[], datetime] = datetime.now) -> None:
        self._now = now

    def match(self, text: str) -> Optional[str]:
        t = _norm(text)
        if not t:
            return None
        if t in _TIME:
            return self._time()
        if t in _DATE:
            return self._date()
        if t in _DAY:
            return self._day()
        if t in _PRESENCE:
            return "Yes sir, I'm here."
        return None

    def control(self, text: str) -> Optional[str]:
        """Return a control-action name ('sleep' / 'wake') for a command reflex,
        else None. Kept separate from ``match`` so the informational path (which
        only returns spoken replies) stays untouched."""
        t = _norm(text)
        if not t:
            return None
        if t in _SLEEP:
            return "sleep"
        if t in _WAKE:
            return "wake"
        if t in _PAUSE:
            return "pause"
        if t in _STATUS:
            return "status"
        return None

    # ---- formatted replies (injected clock) -------------------------- #

    def _time(self) -> str:
        return "It's " + self._now().strftime("%I:%M %p").lstrip("0") + "."

    def _date(self) -> str:
        d = self._now()
        return f"Today is {d:%A}, {d.day} {d:%B %Y}."

    def _day(self) -> str:
        return "It's " + self._now().strftime("%A") + "."
