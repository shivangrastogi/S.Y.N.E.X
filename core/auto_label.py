"""Auto-label engine — surface YOLO labels when objects are close to the camera.

Subscribes to the shared VisionEngine. Each Nth frame is sent to the
``ObjectDetector``; any detection whose bbox occupies ≥ ``_AREA_THRESH``
of the frame AND has confidence ≥ ``_CONF_THRESH`` is considered "close"
and gets surfaced via the listener callbacks (typically a chat bubble
or a toast).

Throttle: per-label cool-down of ``_LABEL_COOLDOWN_S`` prevents the
same object from refire-spamming while it sits in front of the camera.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)


_DETECT_EVERY_N_FRAMES = 8         # ~3.75 detections/sec at 30 fps
_CONF_THRESH = 0.55
_AREA_THRESH = 0.08                # at least 8% of frame area = "close"
_LABEL_COOLDOWN_S = 4.0


class AutoLabelEngine:
    """Background object-label producer. Listener-based output."""

    def __init__(self):
        self._enabled = False
        self._lock = threading.RLock()
        self._listeners: list[Callable[[str, float, tuple], None]] = []
        self._frame_count = 0
        self._last_seen: dict[str, float] = {}
        self._detector = None

    def is_enabled(self) -> bool:
        return self._enabled

    def add_listener(self, fn: Callable[[str, float, tuple], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    def start(self) -> bool:
        if self._enabled:
            return True
        try:
            from core.object_detector import ObjectDetector
        except Exception as e:
            log.info("[auto_label] ObjectDetector import failed: %s", e)
            return False
        try:
            from core.vision_engine import get_vision_engine
        except Exception as e:
            log.info("[auto_label] VisionEngine import failed: %s", e)
            return False
        self._detector = ObjectDetector()
        if not self._detector.is_available():
            # Try once — backend may lazy-load on first detect().
            log.info("[auto_label] detector reports unavailable; will try on first frame.")
        vis = get_vision_engine()
        if not vis.subscribe("auto_label", self._on_frame):
            return False
        self._enabled = True
        log.info("[auto_label] started.")
        return True

    def stop(self) -> None:
        if not self._enabled:
            return
        try:
            from core.vision_engine import get_vision_engine
            get_vision_engine().unsubscribe("auto_label")
        except Exception:
            pass
        self._enabled = False
        log.info("[auto_label] stopped.")

    # ── per-frame ──────────────────────────────────────────────────

    def _on_frame(self, frame_bgr) -> None:
        # Throttle detection to every Nth frame to keep CPU sane.
        self._frame_count += 1
        if self._frame_count % _DETECT_EVERY_N_FRAMES != 0:
            return
        if self._detector is None:
            return
        try:
            detections = self._detector.detect(frame_bgr)
        except Exception as e:
            log.debug("[auto_label] detect failed: %s", e)
            return
        if not detections:
            return
        try:
            h, w = frame_bgr.shape[:2]
            frame_area = float(max(1, h * w))
        except Exception:
            return
        now = time.monotonic()
        for d in detections:
            if d.score < _CONF_THRESH:
                continue
            if d.area() / frame_area < _AREA_THRESH:
                continue
            last = self._last_seen.get(d.label, 0.0)
            if (now - last) < _LABEL_COOLDOWN_S:
                continue
            self._last_seen[d.label] = now
            self._fan_out(d.label, float(d.score), d.bbox)

    def _fan_out(self, label: str, score: float, bbox: tuple) -> None:
        with self._lock:
            subs = list(self._listeners)
        for fn in subs:
            try:
                fn(label, score, bbox)
            except Exception as e:
                log.debug("[auto_label] listener raised: %s", e)


# Module-level singleton.
_DEFAULT: Optional[AutoLabelEngine] = None


def get_auto_label_engine() -> AutoLabelEngine:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = AutoLabelEngine()
    return _DEFAULT
