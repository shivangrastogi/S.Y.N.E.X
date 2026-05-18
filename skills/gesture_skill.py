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
    description="Activate hand-gesture control — 17 gestures + cursor mode for hands-free desktop control.",
    patterns=[
        # English — explicit
        "gesture mode on", "gestures on", "open gesture mode",
        "open gestures", "start gesture mode", "start gestures",
        "turn on gestures", "turn on gesture mode",
        "enable gestures", "enable gesture mode", "enable gesture control",
        "activate gestures", "activate gesture mode",
        "gestures activate", "gestures start",
        "hand gesture on", "hand gestures on",
        "gesture control on", "vision mode on",
        # Hinglish
        "gesture on karo", "gesture mode chalu karo", "gestures kholo",
        "gesture mode kholo", "gestures chalu karo",
        "haath se control karo", "haath chalu karo", "hand gesture chalu karo",
        "vision chalu karo",
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
        return (
            "Gesture mode ON. 17 gestures live:\n"
            "  ── single-hand ──\n"
            "  • Fist (0.6s)         → lock screen\n"
            "  • Long fist (3s)      → open command palette\n"
            "  • Open palm hold      → play/pause media\n"
            "  • Swipe ←/→           → prev/next window/tab\n"
            "  • Swipe ↑/↓           → page up / page down\n"
            "  • Wave (rapid L↔R)    → Esc (dismiss dialog)\n"
            "  • Thumbs up / down    → volume up / down\n"
            "  • Peace (V)           → screenshot snip\n"
            "  • Pinch (closed)      → toggle mic mute\n"
            "  • Three fingers up    → next track\n"
            "  • OK sign             → open command palette\n"
            "  ── two-handed ──\n"
            "  • Both palms apart    → Ctrl++ zoom in\n"
            "  • Both palms together → Ctrl+- zoom out\n"
            "  • Clap                → bring AERIS to front\n"
            "  ── advanced ──\n"
            "  • 'cursor mode on'    → finger = mouse · pinch = click"
        )
    # Surface the actual reason — usually webcam access blocked / in-use.
    try:
        from core.vision_engine import get_vision_engine
        reason = get_vision_engine().last_error() or "unknown"
    except Exception:
        reason = "unknown"
    return f"Camera open nahi ho paya. {reason}"


@skill(
    name="gesture_mode_off",
    description="Stop the gesture controller and release the camera.",
    patterns=[
        # English
        "gesture mode off", "gestures off", "close gesture mode",
        "close gestures", "stop gestures", "stop gesture mode",
        "turn off gestures", "turn off gesture mode",
        "disable gestures", "disable gesture mode", "disable gesture control",
        "gesture control off", "vision mode off",
        # Hinglish
        "gestures off karo", "gestures band karo", "gesture mode band karo",
        "hand gestures stop karo", "gesture mode bandh karo",
        "haath se control band karo", "gestures disable karo",
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
    parts = ["Gestures: ON" if eng.is_enabled() else "Gestures: OFF"]
    if eng.is_cursor_mode():
        parts.append("cursor mode: ON")
    return " · ".join(parts)


@skill(
    name="cursor_mode_on",
    description="Turn your index finger into a mouse — pinch = left click.",
    patterns=[
        "cursor mode on", "mouse mode on", "cursor on karo",
        "hand cursor on", "finger mouse", "air cursor",
        "haath ko mouse banao",
    ],
    required_entities=[],
)
def cursor_mode_on(slots: dict) -> str:
    eng = get_gesture_engine()
    if not eng.is_available():
        return "Gesture engine offline — install mediapipe + opencv-python."
    if not eng.is_enabled():
        # Cursor mode REQUIRES the gesture engine running (so frames flow).
        if not eng.start():
            return "Camera open nahi ho paya."
    eng.set_cursor_mode(True)
    return ("Cursor mode ON. Index fingertip drives mouse · "
            "pinch (thumb+index touch) = left click · "
            "'cursor mode off' to stop.")


@skill(
    name="cursor_mode_off",
    description="Stop the air-cursor (gesture engine stays on for other gestures).",
    patterns=[
        "cursor mode off", "mouse mode off", "cursor off karo",
        "hand cursor off", "stop cursor",
    ],
    required_entities=[],
)
def cursor_mode_off(slots: dict) -> str:
    eng = get_gesture_engine()
    if not eng.is_cursor_mode():
        return "Cursor mode already off."
    eng.set_cursor_mode(False)
    return "Cursor mode OFF."
