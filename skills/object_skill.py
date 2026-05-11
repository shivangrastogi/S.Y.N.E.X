"""Voice-triggered object detection.

Triggers:
    "what am I holding"  / "yeh kya hai mere haath mein"
    "what do you see"    / "camera mein kya dikh raha hai"
    "describe the scene" / "scene describe karo"
"""

from __future__ import annotations

import logging
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.object_detector import (  # noqa: E402
    format_holding_response, format_scene_response, get_object_detector,
)
from core.skill_registry import skill  # noqa: E402
from core.vision_engine import get_vision_engine  # noqa: E402

log = logging.getLogger(__name__)


def _grab_frame(timeout: float = 1.5):
    """Snapshot a single frame from the shared vision engine."""
    return get_vision_engine().snapshot(timeout=timeout)


@skill(
    name="detect_holding",
    description="Look at the webcam and identify what the user is holding.",
    patterns=[
        "what am I holding", "what is in my hand",
        "yeh kya hai mere haath mein", "haath mein kya hai",
        "main kya pakad raha hoon", "ye kya hold kar raha hoon",
        "detect what I am holding", "identify object in my hand",
        "what object am I holding",
    ],
    required_entities=[],
)
def detect_holding(slots: dict) -> str:
    detector = get_object_detector()
    if not detector.is_available():
        return ("Object detection model offline hai — "
                "'pip install ultralytics' chalao for the best backend.")
    # Give the camera a moment to expose properly.
    frame = _grab_frame(timeout=2.0)
    if frame is None:
        return "Webcam frame nahi mila — camera connect hai?"
    detections = detector.detect(frame)
    return format_holding_response(detections, frame.shape)


@skill(
    name="detect_scene",
    description="Describe what the webcam currently sees.",
    patterns=[
        "what do you see", "describe the scene",
        "camera mein kya dikh raha hai", "tum kya dekh rahe ho",
        "scene describe karo", "kya nazar aa raha hai",
        "look around and tell me", "tell me what you see",
        "camera scan karo",
    ],
    required_entities=[],
)
def detect_scene(slots: dict) -> str:
    detector = get_object_detector()
    if not detector.is_available():
        return "Object detection offline. 'pip install ultralytics' for YOLO backend."
    frame = _grab_frame(timeout=2.0)
    if frame is None:
        return "Camera available nahi hai abhi."
    detections = detector.detect(frame)
    return format_scene_response(detections)


@skill(
    name="snap_and_save",
    description="Grab a webcam frame and save it to data/snapshots/.",
    patterns=[
        "snap a photo", "selfie le lo", "webcam ka photo lo",
        "camera snapshot lo", "ek photo capture karo",
        "take a photo from webcam",
    ],
    required_entities=[],
)
def snap_and_save(slots: dict) -> str:
    frame = _grab_frame(timeout=2.0)
    if frame is None:
        return "Webcam frame fail."
    try:
        import cv2
        from datetime import datetime
        out_dir = os.path.join(_ROOT, "data", "snapshots")
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"snap_{ts}.jpg")
        cv2.imwrite(path, frame)
        return f"Snapshot save kiya: {os.path.basename(path)}"
    except Exception as e:
        return f"Snapshot save fail: {e}"
