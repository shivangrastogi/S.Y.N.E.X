"""Scheduled-routines introspection — "what fires at 9am?" / "show my routines".

Read-only view over ``data/routines.json`` (the automation engine owns the
firing). Lets the user see what's scheduled and what triggers at a given hour
without opening JSON.

Examples:
    "show my routines"
    "what routines do I have"
    "what fires at 9am"
    "what's scheduled at 7 pm"
    "9 baje kya hota hai"
    "which routines are enabled"
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _parse_hour(text: str):
    """Pull an hour-of-day (0–23) out of the phrase, or None."""
    t = text.lower()

    # 24h "21:00" / "21"
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", t)
    if m:
        h = int(m.group(1))
        return h if 0 <= h <= 23 else None

    # "9am" / "9 am" / "7pm" / "7 p.m."
    m = re.search(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)\b", t)
    if m:
        h = int(m.group(1)) % 12
        if m.group(2).startswith("p"):
            h += 12
        return h

    # Hinglish "9 baje" — assume the literal hour (24h if >12 already)
    m = re.search(r"\b(\d{1,2})\s*baje\b", t)
    if m:
        h = int(m.group(1))
        return h if 0 <= h <= 23 else None

    return None


@skill(
    name="routines_view",
    description="Show scheduled routines and what fires at a given time.",
    patterns=[
        "show my routines", "what routines do i have",
        "my routines", "what is scheduled", "what's scheduled",
        "what fires at", "what runs at", "which routines are enabled",
        "9 baje kya hota hai", "scheduled tasks",
        "what automations do i have",
    ],
    required_entities=[],
)
def routines_view(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    try:
        from core.routines_view import summarize_routines, summarize_at

        hour = _parse_hour(text)
        if hour is not None and re.search(r"\b(fire|run|scheduled|hota|baje|at)\b", text.lower()):
            return summarize_at(hour)

        enabled_only = bool(re.search(r"\benabled?\b|\bactive\b|\bon\b", text.lower()))
        return summarize_routines(enabled_only=enabled_only)
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[routines_view] failed: %s", e)
        return "Routines nahi dikha paya abhi, sir."
