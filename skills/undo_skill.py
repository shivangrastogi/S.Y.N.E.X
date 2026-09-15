"""Undo the last reversible action.

Pops the newest entry off ``core.action_history`` and runs its undo. Only
skills that registered an undo participate (currently: clipboard_copy; more
to come). "force undo" ignores the time window.

Examples:
    "undo"
    "undo that"
    "wait no"
    "undo last action"
    "wapas karo"
    "force undo"
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="undo_last",
    description="Undo the most recent reversible action (clipboard, etc.).",
    patterns=[
        "undo", "undo that", "undo last action", "undo it", "wait no",
        "no undo that", "undo karo", "wapas karo", "wapis karo",
        "ye galat tha", "force undo", "undo last",
    ],
    required_entities=[],
)
def undo_last(slots: dict) -> str:
    text = (slots.get("raw_text") or slots.get("text") or "").lower()
    force = "force" in text
    try:
        from core.action_history import undo_last as _undo
        # force → ignore the time window; otherwise use the default window.
        return _undo(within_s=None) if force else _undo()
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[undo] failed: %s", e)
        return "Undo nahi kar paya abhi, sir."
