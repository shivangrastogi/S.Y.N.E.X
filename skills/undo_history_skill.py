"""\"What can I undo?\" — list the pending reversible actions.

Shows the undo stack (newest first) so the user knows what "undo" would revert
before saying it. Read-only companion to the `undo_last` skill.

Examples:
    "what can I undo"
    "undo history"
    "show undo stack"
    "kya undo kar sakta hoon"
    "what will undo do"
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="undo_history",
    description="List the pending undoable actions (what 'undo' would revert).",
    patterns=[
        "what can i undo", "undo history", "show undo stack", "undo list",
        "what will undo do", "kya undo kar sakta hoon", "undo kya karega",
        "list undo", "pending undo",
    ],
    required_entities=[],
)
def undo_history(_slots: dict) -> str:
    try:
        from core.action_history import labels
        items = labels()
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[undo_history] failed: %s", e)
        return "Undo history nahi nikal paya abhi, sir."

    if not items:
        return "Abhi kuch undo karne ko nahi hai, sir."

    if len(items) == 1:
        return f"Undo karega: {items[0]}."

    shown = items[:5]
    lines = "\n".join(f"  {i+1}. {label}" for i, label in enumerate(shown))
    more = f" (+{len(items) - 5} aur)" if len(items) > 5 else ""
    return f"{len(items)} cheezein undo ho sakti hain (newest pehle){more}:\n{lines}"
