"""Activity digest skill — "what did you do today?"

Asks AERIS to summarise its own recent activity from the structured
``skill_dispatch`` event log. The time window is parsed out of the spoken
phrase ("last hour", "aaj", "this week"); default is the last 24 hours.

Examples:
    "what did you do today"
    "activity summary"
    "aaj kya kiya"
    "summarise the last hour"
    "what have you done this week"
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _window_hours(text: str) -> float:
    """Map a spoken phrase to a window length in hours. Default 24h."""
    t = text.lower()

    # Explicit "last N minutes / hours / days"
    m = re.search(r"(?:last|past|pichhle|pichle)\s+(\d+)\s*(min|minute|hour|ghante|ghanta|day|din|hafte|week)", t)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("min"):
            return max(n / 60.0, 1 / 60.0)
        if unit in ("hour", "ghante", "ghanta"):
            return float(n)
        if unit in ("day", "din"):
            return n * 24.0
        if unit in ("week", "hafte"):
            return n * 24.0 * 7.0

    if re.search(r"\b(last hour|past hour|pichhle ghante|ek ghante|ghante mein)\b", t):
        return 1.0
    if re.search(r"\b(week|hafte|hafta|7 din|saat din)\b", t):
        return 24.0 * 7.0
    if re.search(r"\b(today|aaj|din bhar|aaj ka)\b", t):
        return 24.0
    if re.search(r"\b(month|mahine|mahina|30 din)\b", t):
        return 24.0 * 30.0
    return 24.0


@skill(
    name="activity_digest",
    description="Summarise AERIS's own recent activity (skills fired) over a time window.",
    patterns=[
        "what did you do", "what did you do today", "activity summary",
        "what have you done", "what did you do this week",
        "kya kiya aaj tumne", "aaj tak kya kiya",
        "summarise the last hour", "activity digest", "your activity",
        "what skills did you run", "kitne command chale",
        "show my activity", "recent activity",
    ],
    required_entities=[],
)
def activity_digest(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    window_h = _window_hours(text)
    try:
        from core.activity_digest import summarize
        return summarize(window_h)
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[activity_digest] failed: %s", e)
        return "Activity summary nahi bana paya abhi, sir."
