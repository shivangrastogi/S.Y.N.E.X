"""Temporal recall — "kal maine kya kiya tha?" (Blueprint I2).

Parses a Hinglish time-window out of an utterance (kal / parso / aaj /
pichhle hafte / is hafte / weekday names) and composes a short digest of that
window from what AERIS already records: the presence journal's day summary,
completed goals, and autonomous actions from the ledger.

Pure + injectable — every source passes in, so it tests with fakes and a
frozen clock. The engine wires the live singletons.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, Optional

log = logging.getLogger(__name__)

_DAY_S = 86400.0

# weekday name → Python weekday() index (Mon=0)
_WEEKDAYS = {
    "somwar": 0, "monday": 0,
    "mangalwar": 1, "tuesday": 1,
    "budhwar": 2, "wednesday": 2,
    "guruwar": 3, "thursday": 3, "brihaspatiwar": 3,
    "shukrawar": 4, "friday": 4,
    "shaniwar": 5, "saturday": 5,
    "ravivar": 6, "sunday": 6, "itwar": 6,
}

# The question must actually ask about past activity — "kal alarm laga do"
# is a command, not a recall.
_ASK_RE = re.compile(
    r"\b(kya (kiya|hua|kar raha tha)|kaisa (gaya|raha)|summary|recap|"
    r"kitna kaam|what did (i|we) do|kya kaam)\b", re.I)

_WORD_RE = re.compile(
    r"\b(aaj|kal|parso|pichhle hafte|last week|is hafte|this week|"
    + "|".join(_WEEKDAYS) + r")\b", re.I)


def _midnight(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def parse_window(text: str, now: float) -> Optional[tuple[float, float, str]]:
    """(t0, t1, label) for a *recall* question about a past window, else None.
    "kal" is read as YESTERDAY (recall context — the ask-guard filters
    commands where "kal" would mean tomorrow)."""
    if not text or not _ASK_RE.search(text):
        return None
    m = _WORD_RE.search(text)
    if not m:
        return None
    word = m.group(1).lower()
    today0 = _midnight(datetime.fromtimestamp(now))

    if word == "aaj":
        t0 = today0
        return t0.timestamp(), now, "aaj"
    if word == "kal":
        t0 = today0 - timedelta(days=1)
        return t0.timestamp(), t0.timestamp() + _DAY_S, "kal"
    if word == "parso":
        t0 = today0 - timedelta(days=2)
        return t0.timestamp(), t0.timestamp() + _DAY_S, "parso"
    if word in ("pichhle hafte", "last week"):
        start = today0 - timedelta(days=today0.weekday() + 7)
        return start.timestamp(), start.timestamp() + 7 * _DAY_S, "pichhle hafte"
    if word in ("is hafte", "this week"):
        start = today0 - timedelta(days=today0.weekday())
        return start.timestamp(), now, "is hafte"
    if word in _WEEKDAYS:
        target = _WEEKDAYS[word]
        back = (today0.weekday() - target) % 7 or 7   # most recent PAST one
        t0 = today0 - timedelta(days=back)
        return t0.timestamp(), t0.timestamp() + _DAY_S, word.title()
    return None


def _fmt_h(seconds: float) -> str:
    h = seconds / 3600.0
    return f"{h:.1f} ghante" if h >= 1 else f"{int(seconds // 60)} min"


def digest(t0: float, t1: float, label: str, *,
           journal: Any = None,
           goal_store: Any = None,
           ledger: Any = None) -> str:
    """Compose the window's story from whatever sources are available."""
    parts: list[str] = []

    # presence: focus/active time per day in the window
    if journal is not None:
        try:
            focus_s = active_s = 0.0
            arrivals = 0
            d = datetime.fromtimestamp(t0).date()
            # t1 is an EXCLUSIVE bound (usually next midnight) — step back 1s
            # so a one-day window doesn't double-count the following day.
            end_d = datetime.fromtimestamp(
                max(t0, min(t1, t0 + 366 * _DAY_S) - 1)).date()
            while d <= end_d:
                s = journal.day_summary(d) or {}
                focus_s += float(s.get("focus_s", 0.0))
                active_s += float(s.get("active_s", 0.0))
                arrivals += int(s.get("arrivals", 0))
                d += timedelta(days=1)
            if focus_s or active_s:
                parts.append(f"{_fmt_h(focus_s)} focus, "
                             f"{_fmt_h(active_s)} active")
        except Exception as e:
            log.debug("[temporal] journal read failed: %s", e)

    # goals completed in the window
    if goal_store is not None:
        try:
            done = [g.text for g in goal_store.all()
                    if g.state == "done" and t0 <= (g.updated or 0) < t1]
            if done:
                shown = ", ".join(done[:3])
                more = f" (+{len(done)-3})" if len(done) > 3 else ""
                parts.append(f"goals poore: {shown}{more}")
        except Exception as e:
            log.debug("[temporal] goals read failed: %s", e)

    # autonomous actions from the ledger
    if ledger is not None:
        try:
            acts = [e for e in ledger.all()
                    if t0 <= (e.get("ts") or 0) < t1
                    and e.get("decision") == "allow"]
            if acts:
                names = []
                for e in acts:
                    a = e.get("action", "")
                    if a and a not in names:
                        names.append(a)
                shown = ", ".join(names[:4])
                parts.append(f"maine {len(acts)} kaam kiye ({shown})")
        except Exception as e:
            log.debug("[temporal] ledger read failed: %s", e)

    if not parts:
        return (f"{label.title()} ka koi record nahi mila — "
                f"shayad main us waqt chala nahi tha.")
    return f"{label.title()}: " + "; ".join(parts) + "."


def answer(text: str, now: float, *, journal: Any = None,
           goal_store: Any = None, ledger: Any = None) -> Optional[str]:
    """One-shot: parse + digest, or None if this isn't a temporal recall."""
    win = parse_window(text, now)
    if win is None:
        return None
    t0, t1, label = win
    return digest(t0, t1, label, journal=journal, goal_store=goal_store,
                  ledger=ledger)
