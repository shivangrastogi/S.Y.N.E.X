"""Briefing skills — the assistant's "tell me what's up" composites.

* ``morning_briefing`` — a single spoken-length summary stitched from the
  pieces AERIS already knows: time-of-day greeting, today's weather, battery /
  power, today's to-dos, and yesterday's presence digest. This is the concrete
  "personal assistant in the actual manner" payload that fires on first arrival
  (and on demand: "good morning", "brief me", "subah ka update").

Each sub-fetch is wrapped so one failing source (no network for weather, no
journal yet) never sinks the whole briefing — it just drops that line. Keeps
it usable on day one and offline.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _greeting() -> str:
    h = datetime.now().hour
    if 5 <= h < 12:
        return "Good morning, Shivang."
    if 12 <= h < 17:
        return "Good afternoon, Shivang."
    if 17 <= h < 21:
        return "Good evening, Shivang."
    return "Hi Shivang."


def _safe(fn) -> str:
    try:
        out = fn()
        return (out or "").strip()
    except Exception as e:
        log.debug("[briefing] piece failed: %s", e)
        return ""


def _weather_line() -> str:
    from skills.info_skills import weather_local
    txt = weather_local({})
    # weather_local already returns a compact one-liner; trim its label noise.
    return f"Mausam — {txt}" if txt and "fail" not in txt.lower() else ""


def _power_line() -> str:
    from core.power_state import get_monitor
    s = get_monitor().snapshot()
    if s.on_battery:
        return f"Battery {s.percent}% (unplugged)."
    return f"Power plugged in, battery {s.percent}%."


def _todo_line() -> str:
    from skills.dev_tools import todo_today
    txt = todo_today({})
    if not txt:
        return ""
    # Collapse a multi-line todo dump into a short headline + count.
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return txt.strip()
    head = lines[0].strip()
    return f"To-dos: {head} (+{len(lines) - 1} more)."


def _digest_line() -> str:
    from core.presence_journal import get_journal
    return get_journal().digest_line(date.today() - timedelta(days=1))


def compose_briefing() -> str:
    """Build the briefing string. Exposed for reuse by the GUI/automation."""
    parts = [_greeting()]
    for piece in (_weather_line, _power_line, _todo_line, _digest_line):
        line = _safe(piece)
        if line:
            parts.append(line)
    if len(parts) == 1:
        parts.append("System nominal — koi pending update nahi.")
    return " ".join(parts)


@skill(
    name="morning_briefing",
    description="Spoken daily briefing: greeting + weather + power + to-dos + presence digest",
    patterns=[
        "morning briefing", "brief me", "subah ka update",
        "aaj ka update", "what's up today", "brief karo",
        "din ka plan", "today's briefing", "mujhe update do",
    ],
)
def morning_briefing(_slots: dict) -> str:
    return compose_briefing()
