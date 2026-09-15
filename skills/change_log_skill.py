"""\"What did you change?\" — narrative diff of AERIS's recent activity.

Sibling to ``activity_digest`` but broader: instead of just skill counts it
narrates every event kind (skills, scheduled routines, presence moments…) in
the window. Ask it after a stretch of work / a routine-heavy morning.

Examples:
    "what did you change"
    "what's new"
    "summarise the last 24 hours"
    "what have you been up to"
    "kya naya hua"
    "what did you do since boot"
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="change_log",
    description="Narrate everything AERIS changed/did recently across all event kinds.",
    patterns=[
        "what did you change", "what's new", "whats new",
        "what did you add", "summarise the last 24 hours",
        "summarize recent changes", "what have you been up to",
        "kya naya hua", "kya naya kiya", "kya kya hua",
        "what did you do since boot", "recent changes", "change log",
    ],
    required_entities=[],
)
def change_log(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    try:
        from core.change_log import summarize_changes, changes_since_boot
        if "boot" in text.lower() or "since" in text.lower():
            return changes_since_boot()
        # Reuse the activity-digest window parser so "last 3 hours" / "today"
        # / "this week" behave identically across both summary skills.
        from skills.activity_digest_skill import _window_hours
        return summarize_changes(_window_hours(text))
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[change_log] failed: %s", e)
        return "Change summary nahi bana paya abhi, sir."
