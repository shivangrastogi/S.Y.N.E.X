"""Camera-presence engine — tracks whether a user is currently visible.

Subscribes to the shared ``VisionEngine`` and runs face detection at a
low cadence (every ``_PROBE_INTERVAL_S`` ≈ 2 s) — cheap enough to keep
running, expensive enough to skip if the user just walked away. Emits
``user_present`` / ``user_absent`` transitions to registered listeners
so the gesture engine (or any other consumer) can auto-pause itself
when there's no one in front of the camera.

Public API:
    eng = get_presence_engine()
    eng.start()
    eng.is_present()             # True / False
    eng.last_seen_at()           # monotonic timestamp
    eng.add_listener(fn)         # fn("present"|"absent")
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)


_PROBE_INTERVAL_S = 2.0       # min seconds between face detections
_ABSENCE_GRACE_S  = 4.0       # need this much absence before "user_absent" fires
                              # (covers brief turn-aways / brief detection misses)


class PresenceEngine:
    """Background user-presence tracker on top of VisionEngine + InsightFace."""

    def __init__(self):
        self._enabled = False
        self._lock = threading.RLock()
        self._listeners: list[Callable[[str], None]] = []
        self._frame_count = 0
        self._present = False
        self._last_probe_at = 0.0
        self._last_present_at = 0.0
        self._last_absent_at = 0.0
        self._latest_frame = None

    # ── lifecycle ──────────────────────────────────────────────────

    def is_enabled(self) -> bool:
        return self._enabled

    def is_present(self) -> bool:
        return self._present

    def last_seen_at(self) -> float:
        return self._last_present_at

    def add_listener(self, fn: Callable[[str], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    def start(self) -> bool:
        if self._enabled:
            return True
        try:
            from core.vision_engine import get_vision_engine
        except Exception as e:
            log.info("[presence] VisionEngine import failed: %s", e)
            return False
        try:
            from core.face_recognition import get_recognizer  # noqa: F401
        except Exception as e:
            log.info("[presence] FaceRecognizer import failed: %s", e)
            return False
        vis = get_vision_engine()
        if not vis.subscribe("presence", self._on_frame):
            return False
        self._enabled = True
        log.info("[presence] started.")
        return True

    def stop(self) -> None:
        if not self._enabled:
            return
        try:
            from core.vision_engine import get_vision_engine
            get_vision_engine().unsubscribe("presence")
        except Exception:
            pass
        self._enabled = False
        log.info("[presence] stopped.")

    # ── per-frame ──────────────────────────────────────────────────

    def _on_frame(self, frame_bgr) -> None:
        now = time.monotonic()
        self._latest_frame = frame_bgr
        # Cadence — don't burn CPU running InsightFace on every frame.
        if (now - self._last_probe_at) < _PROBE_INTERVAL_S:
            return
        self._last_probe_at = now
        try:
            from core.face_recognition import get_recognizer
            rec = get_recognizer()
        except Exception:
            return
        if not rec.is_available():
            return
        try:
            names = rec.identify_faces(frame_bgr)
        except Exception as e:
            log.debug("[presence] identify failed: %s", e)
            return

        # Any face = present. We don't care WHO it is here.
        any_face = bool(names)
        if any_face:
            self._last_present_at = now
            if not self._present:
                self._present = True
                self._fan_out("present")
        else:
            self._last_absent_at = now
            # Require sustained absence before flipping to "absent".
            since_seen = now - self._last_present_at
            if self._present and since_seen >= _ABSENCE_GRACE_S:
                self._present = False
                self._fan_out("absent")

    def _fan_out(self, event: str) -> None:
        with self._lock:
            subs = list(self._listeners)
        for fn in subs:
            try:
                fn(event)
            except Exception as e:
                log.debug("[presence] listener raised: %s", e)


# Module-level singleton.
_DEFAULT: Optional[PresenceEngine] = None


def get_presence_engine() -> PresenceEngine:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = PresenceEngine()
    return _DEFAULT


# ── Gesture-engine auto-pause integration ────────────────────────


_AUTO_PAUSE_HOOK_INSTALLED = False


def install_gesture_auto_pause() -> bool:
    """Idempotently wire the presence engine to auto-pause / resume the
    gesture engine. When the user walks away the gesture engine stops
    consuming frames; when they return, it starts again.

    Returns True when the hook is in place, False on any wiring failure.
    """
    global _AUTO_PAUSE_HOOK_INSTALLED
    if _AUTO_PAUSE_HOOK_INSTALLED:
        return True
    try:
        eng = get_presence_engine()
        if not eng.start():
            return False
    except Exception:
        return False

    def _hook(event: str) -> None:
        try:
            from core.gesture_engine import get_gesture_engine
            ge = get_gesture_engine()
            if event == "absent" and ge.is_enabled():
                ge.stop()
                log.info("[presence] auto-paused gesture engine (user absent).")
            elif event == "present" and not ge.is_enabled():
                ge.start()
                log.info("[presence] auto-resumed gesture engine (user present).")
        except Exception as e:
            log.debug("[presence] hook raised: %s", e)

    eng.add_listener(_hook)
    _AUTO_PAUSE_HOOK_INSTALLED = True
    return True


def uninstall_gesture_auto_pause() -> None:
    """No-op safe — listener filtering on the engine isn't supported, so
    this just stops the presence engine entirely. The hook will no-op
    when called next because the engine won't produce events."""
    global _AUTO_PAUSE_HOOK_INSTALLED
    try:
        get_presence_engine().stop()
    finally:
        _AUTO_PAUSE_HOOK_INSTALLED = False
