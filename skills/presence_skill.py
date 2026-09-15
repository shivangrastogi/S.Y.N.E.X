"""Voice control for the camera-presence engine.

Skills:
  * ``presence_status`` — report user-present state + last seen
  * ``presence_auto_pause_on``  — install gesture-engine auto-pause hook
  * ``presence_auto_pause_off`` — stop the presence engine
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="presence_status",
    description="Report whether AERIS currently sees a user in front of the camera.",
    patterns=[
        "presence status", "am i present", "is anyone there",
        "camera presence", "presence kya hai",
        "user present", "are you watching",
    ],
    required_entities=[],
)
def presence_status(_slots: dict) -> str:
    try:
        from core.presence import get_presence_engine
    except Exception as e:
        return f"presence module load fail: {e}"
    eng = get_presence_engine()
    state = "ON" if eng.is_enabled() else "OFF"
    if not eng.is_enabled():
        return f"Presence engine: {state}. 'presence auto pause on' to start."
    present = "PRESENT" if eng.is_present() else "ABSENT"
    last = eng.last_seen_at()
    ago = (time.monotonic() - last) if last else None
    ago_str = f"{ago:.1f}s ago" if ago is not None else "never"
    return f"Presence engine: {state}. User {present} (last seen {ago_str})."


@skill(
    name="presence_auto_pause_on",
    description="Auto-pause the gesture engine when you walk away from the camera "
                "and resume when you return.",
    patterns=[
        "presence auto pause on", "auto pause gestures",
        "camera presence on", "presence on",
        "smart pause on", "auto pause on",
        "pause when absent",
    ],
    required_entities=[],
)
def presence_auto_pause_on(_slots: dict) -> str:
    try:
        from core.presence import install_gesture_auto_pause
    except Exception as e:
        return f"presence load fail: {e}"
    if install_gesture_auto_pause():
        return ("Presence auto-pause ON — gesture engine will pause when "
                "you walk away, resume when you return.")
    return ("Presence auto-pause could not start — camera or insightface "
            "missing? Run 'diagnose'.")


@skill(
    name="presence_auto_pause_off",
    description="Disable the camera-presence auto-pause for gestures.",
    patterns=[
        "presence auto pause off", "stop presence",
        "presence off", "smart pause off",
        "auto pause off", "stop watching for me",
    ],
    required_entities=[],
)
def presence_auto_pause_off(_slots: dict) -> str:
    try:
        from core.presence import uninstall_gesture_auto_pause
    except Exception as e:
        return f"presence load fail: {e}"
    uninstall_gesture_auto_pause()
    return "Presence auto-pause OFF."
