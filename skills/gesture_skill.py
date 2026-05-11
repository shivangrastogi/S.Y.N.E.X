"""Voice-activated control for the gesture engine.

Users can switch the whole gesture system on/off via voice:
    "gesture mode on" / "gesture on karo"
    "gesture mode off" / "gestures band karo"
    "gesture status"
"""

from __future__ import annotations

import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.gesture_engine import get_gesture_engine  # noqa: E402
from core.skill_registry import skill  # noqa: E402

log = logging.getLogger(__name__)


@skill(
    name="gesture_mode_on",
    description="Activate hand-gesture control: fist locks screen, swipe switches windows/tabs, thumbs up/down for volume.",
    patterns=[
        "gesture mode on", "gesture on karo", "gestures activate karo",
        "hand gesture chalu karo", "vision mode on", "gestures start karo",
        "enable gestures", "gesture control on",
        "haath se control karo", "haath chalu karo",
    ],
    required_entities=[],
)
def gesture_mode_on(slots: dict) -> str:
    eng = get_gesture_engine()
    if not eng.is_available():
        return ("Gesture engine offline hai — mediapipe install karo: "
                "'pip install mediapipe opencv-python'.")
    if eng.is_enabled():
        return "Gestures already on hain, sir."
    if eng.start():
        return ("Gesture mode on. Fist = lock screen, swipe left/right = "
                "window/tab switch, thumbs up/down = volume, palm hold = play/pause.")
    return "Camera open nahi ho paya — webcam check karo."


@skill(
    name="gesture_mode_off",
    description="Stop the gesture controller and release the camera.",
    patterns=[
        "gesture mode off", "gestures off karo", "gestures band karo",
        "hand gestures stop karo", "vision mode off", "gestures disable karo",
        "stop gestures", "gesture control off",
        "haath se control band karo",
    ],
    required_entities=[],
)
def gesture_mode_off(slots: dict) -> str:
    eng = get_gesture_engine()
    if not eng.is_enabled():
        return "Gestures already off hain, sir."
    eng.stop()
    return "Gesture mode off. Camera released."


@skill(
    name="gesture_status",
    description="Report whether gesture control is currently active.",
    patterns=[
        "gesture status", "gestures chalu hain kya",
        "is gesture mode on", "gesture mode status",
        "vision mode status",
    ],
    required_entities=[],
)
def gesture_status(slots: dict) -> str:
    eng = get_gesture_engine()
    if not eng.is_available():
        return "Gesture engine offline (mediapipe missing)."
    return "Gestures: ON" if eng.is_enabled() else "Gestures: OFF"
