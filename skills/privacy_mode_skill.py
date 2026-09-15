"""Voice + text commands for privacy mode.

Skills:
  * ``privacy_mode_on``      — stop every listener subsystem
  * ``privacy_mode_off``     — flip the flag (subsystems stay off; user
                              re-enables what they want explicitly)
  * ``privacy_mode_status``  — describe current state per subsystem
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="privacy_mode_on",
    description="Hard 'stop listening' — disables wake-word + STT + "
                "gesture engine + camera + auto-label + notification mirror.",
    patterns=[
        "privacy mode on", "stop listening", "go private",
        "privacy on", "mic off entirely", "mute everything",
        "privacy mode chalu karo", "stop watching me",
        "shut down listening", "stop all sensing",
    ],
    required_entities=[],
)
def privacy_mode_on(_slots: dict) -> str:
    try:
        from core import privacy_mode as pm
    except Exception as e:
        return f"privacy_mode load fail: {e}"
    stopped = pm.enable()
    if not stopped:
        return "Privacy mode ON — koi listener subsystem chal raha nahi tha."
    return ("Privacy mode ON. Stopped: " + ", ".join(stopped)
            + ". 'privacy mode off' to flip the flag (manual re-enable needed).")


@skill(
    name="privacy_mode_off",
    description="Disable privacy mode (does NOT auto-resume subsystems — "
                "you re-enable what you want).",
    patterns=[
        "privacy mode off", "resume listening", "privacy off",
        "privacy mode band karo", "stop privacy mode",
        "back to normal", "exit privacy mode",
    ],
    required_entities=[],
)
def privacy_mode_off(_slots: dict) -> str:
    try:
        from core import privacy_mode as pm
    except Exception as e:
        return f"privacy_mode load fail: {e}"
    return pm.disable()


@skill(
    name="privacy_mode_status",
    description="Report privacy mode state + per-subsystem on/off.",
    patterns=[
        "privacy mode status", "privacy status",
        "is privacy mode on", "kya privacy mode chalu hai",
        "show privacy state",
    ],
    required_entities=[],
)
def privacy_mode_status(_slots: dict) -> str:
    try:
        from core import privacy_mode as pm
    except Exception as e:
        return f"privacy_mode load fail: {e}"
    return pm.explain()
