"""Voice control for the gesture engine's sensitivity multiplier.

Scales the per-frame motion thresholds (swipe delta + velocity) so the
user can pick how decisive a gesture must be to fire. Five levels:

    very_sensitive  0.70x  — easier; small/slow motion still fires
    sensitive       0.85x
    normal          1.00x  (default)
    relaxed         1.20x  — fewer false positives
    very_relaxed    1.50x  — only the snappiest motion fires

Persists via the same settings store as everything else, so the choice
survives restart.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core import settings as _settings
from core.skill_registry import skill

log = logging.getLogger(__name__)


_LEVEL_ALIASES: dict[str, str] = {
    "very sensitive": "very_sensitive",
    "very_sensitive": "very_sensitive",
    "high sensitivity": "very_sensitive",
    "ultra sensitive": "very_sensitive",
    "max sensitive": "very_sensitive",

    "sensitive":     "sensitive",
    "more sensitive": "sensitive",
    "zyada sensitive": "sensitive",

    "normal":        "normal",
    "default":       "normal",
    "reset":         "normal",
    "standard":      "normal",
    "vapas normal":  "normal",

    "relaxed":       "relaxed",
    "less sensitive": "relaxed",
    "kam sensitive": "relaxed",
    "less responsive": "relaxed",

    "very relaxed":  "very_relaxed",
    "very_relaxed":  "very_relaxed",
    "very lazy":     "very_relaxed",
    "bahut relaxed": "very_relaxed",
    "ultra relaxed": "very_relaxed",
}


def _resolve_level(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower().strip()
    # Sort aliases longest-first so "very sensitive" wins over "sensitive".
    for alias, level in sorted(_LEVEL_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias in t:
            return level
    return None


@skill(
    name="gesture_sensitivity_set",
    description="Set the gesture engine sensitivity — very_sensitive / "
                "sensitive / normal / relaxed / very_relaxed.",
    patterns=[
        "gesture sensitivity",
        "set gesture sensitivity",
        "gestures more sensitive", "gestures less sensitive",
        "make gestures more sensitive", "make gestures less sensitive",
        "gestures kam sensitive karo", "gestures zyada sensitive karo",
        "gestures normal karo", "reset gesture sensitivity",
        "gestures relaxed mode", "gestures sensitive mode",
        "default gesture sensitivity",
    ],
    required_entities=[],
)
def gesture_sensitivity_set(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    level = _resolve_level(text)
    if level is None:
        valid = ", ".join(sorted(set(_LEVEL_ALIASES.values())))
        return ("Sensitivity level samjha nahi. Try one of: "
                + valid + ". Example: 'gestures less sensitive'.")
    _settings.set_("gesture_sensitivity", level)
    try:
        from core.gesture_engine import _sensitivity_multiplier
        mult = _sensitivity_multiplier()
    except Exception:
        mult = 1.0
    return f"Gesture sensitivity → {level} (multiplier {mult:.2f}x)."


@skill(
    name="gesture_sensitivity_status",
    description="Report the current gesture sensitivity level + multiplier.",
    patterns=[
        "gesture sensitivity status", "what is gesture sensitivity",
        "current gesture sensitivity", "gesture sensitivity kya hai",
        "show gesture sensitivity", "sensitivity level batao",
    ],
    required_entities=[],
)
def gesture_sensitivity_status(_slots: dict) -> str:
    level = _settings.get("gesture_sensitivity") or "normal"
    try:
        from core.gesture_engine import _sensitivity_multiplier, _SENSITIVITY_LEVELS
        mult = _sensitivity_multiplier()
        valid = ", ".join(sorted(_SENSITIVITY_LEVELS.keys()))
    except Exception:
        mult = 1.0
        valid = "very_sensitive, sensitive, normal, relaxed, very_relaxed"
    return (f"Gesture sensitivity: {level} (×{mult:.2f}). "
            f"Available levels: {valid}.")
