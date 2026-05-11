"""Shared webcam + frame fan-out.

A single cv2.VideoCapture is held open while at least one consumer is
subscribed. Each consumer registers a callback ``(frame_bgr) -> None``
that runs on the capture thread (must be cheap; heavy work goes to
its own worker).

Why a multiplexer:
  - The gesture engine wants frames at ~30 fps for swipe smoothing.
  - The object detector wants frames once on demand ("what am I holding").
  - cv2 will not let two processes hold the same webcam.

Public API:
    engine = VisionEngine()
    engine.subscribe("gestures", on_frame_cb)
    engine.start()
    ...
    engine.unsubscribe("gestures")
    engine.stop()                # auto-stops once last consumer leaves

    frame = engine.snapshot()    # one-shot grab (engine starts/stops if idle)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

FrameCallback = Callable[[object], None]   # cv2 Mat / ndarray


class VisionEngine:
    """Thread-safe webcam multiplexer."""

    def __init__(self, *, camera_index: int = 0, fps_cap: float = 30.0):
        self._camera_index = camera_index
        self._fps_cap = fps_cap
        self._consumers: dict[str, FrameCallback] = {}
        self._lock = threading.RLock()
        self._cap = None
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._latest_frame = None
        self._latest_ts: float = 0.0
        self._auto_stop = True

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                          #
    # ------------------------------------------------------------------ #

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def consumer_count(self) -> int:
        with self._lock:
            return len(self._consumers)

    def start(self) -> bool:
        with self._lock:
            if self.is_running():
                return True
            try:
                import cv2
            except ImportError:
                log.warning("[vision] opencv-python not installed.")
                return False
            cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                # CAP_DSHOW can fail on some webcams; fall through to default.
                cap.release()
                cap = cv2.VideoCapture(self._camera_index)
            if not cap.isOpened():
                log.warning("[vision] camera %s could not be opened.", self._camera_index)
                return False
            self._cap = cap
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._run, name="VisionEngine",
                                            daemon=True)
            self._thread.start()
            log.info("[vision] camera started.")
            return True

    def stop(self) -> None:
        with self._lock:
            if not self.is_running():
                # Even if not running, release any leftover capture handle.
                if self._cap is not None:
                    try: self._cap.release()
                    except Exception: pass
                    self._cap = None
                return
            self._stop_evt.set()
        # Join outside the lock so the loop can release.
        if self._thread:
            self._thread.join(timeout=2.0)
        with self._lock:
            self._thread = None
            if self._cap is not None:
                try: self._cap.release()
                except Exception: pass
                self._cap = None
            log.info("[vision] camera stopped.")

    # ------------------------------------------------------------------ #
    #  Subscriber API                                                     #
    # ------------------------------------------------------------------ #

    def subscribe(self, name: str, cb: FrameCallback) -> bool:
        """Register a consumer; auto-starts the engine if idle."""
        with self._lock:
            self._consumers[name] = cb
        if not self.is_running():
            return self.start()
        return True

    def unsubscribe(self, name: str) -> None:
        with self._lock:
            self._consumers.pop(name, None)
            empty = not self._consumers
        if empty and self._auto_stop:
            self.stop()

    # ------------------------------------------------------------------ #
    #  Snapshot helper (one-shot frame grab)                              #
    # ------------------------------------------------------------------ #

    def snapshot(self, timeout: float = 1.5):
        """Grab a single frame. If engine was idle, starts/stops around it."""
        was_running = self.is_running()
        if not was_running:
            if not self.start():
                return None
        # Wait briefly for the first usable frame.
        deadline = time.monotonic() + timeout
        frame = None
        while time.monotonic() < deadline:
            with self._lock:
                if self._latest_frame is not None:
                    frame = self._latest_frame.copy()
                    break
            time.sleep(0.05)
        if not was_running and self.consumer_count() == 0:
            self.stop()
        return frame

    # ------------------------------------------------------------------ #
    #  Capture loop                                                       #
    # ------------------------------------------------------------------ #

    def _run(self) -> None:
        period = 1.0 / max(self._fps_cap, 1.0)
        while not self._stop_evt.is_set():
            t0 = time.monotonic()
            cap = self._cap
            if cap is None:
                break
            ok, frame = cap.read()
            if not ok or frame is None:
                # Hiccup — sleep and retry; webcams sometimes drop a frame.
                time.sleep(0.05)
                continue
            with self._lock:
                self._latest_frame = frame
                self._latest_ts = time.monotonic()
                consumers = list(self._consumers.values())
            # Fan out to consumers OUTSIDE the lock so a slow consumer
            # never blocks the camera read.
            for cb in consumers:
                try:
                    cb(frame)
                except Exception as e:
                    log.warning("[vision] consumer raised: %s", e)
            elapsed = time.monotonic() - t0
            if elapsed < period:
                # Use the stop event so we can exit promptly mid-sleep.
                self._stop_evt.wait(period - elapsed)


# Module-level singleton.
_DEFAULT: Optional[VisionEngine] = None


def get_vision_engine() -> VisionEngine:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = VisionEngine()
    return _DEFAULT


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    eng = get_vision_engine()
    n = [0]
    def _count(_f): n[0] += 1
    eng.subscribe("smoke", _count)
    time.sleep(2.0)
    eng.unsubscribe("smoke")
    print(f"frames seen in 2s: {n[0]}")
