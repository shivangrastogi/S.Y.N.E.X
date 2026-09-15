"""Vision service — camera + MediaPipe + gesture recognition in their OWN
process (docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md, P1 §"Extract Voice
and Vision as separate on-demand services", and §4.2 "one ML stack at a time").

The brain moved out in §6.6/§6.22. Vision is the other heavy native stack the
GUI still carries: MediaPipe + OpenCV, plus a capture thread running inference
at ~30 fps inside the Qt process. Moving it out means the GUI holds *no* native
ML at all, a MediaPipe fault can't corrupt the Qt heap, and the camera stack is
only resident while gestures are actually switched on.

### Where the boundary goes, and why it isn't obvious

The tempting design — child owns the camera, parent gets the frames — is the
wrong one. A 640×480 BGR frame is ~920 KB; at 30 fps that is ~27 MB/s of
pickle-and-pipe, which costs *more* than the MediaPipe inference it was
supposed to offload, and adds latency to a path whose whole job is feeling
instant.

So the process boundary is drawn where the data is small:

    child:  cv2.VideoCapture → VisionEngine → MediaPipe → GestureEngine
    bus:    event:gesture {"name": "swipe_left"}          ← ~40 bytes
            request/response for lifecycle + status

Frames never leave the child. The one exception is ``snapshot``, which is
on-demand, rare (the object-detector / "what am I holding" path), and ships a
JPEG rather than a raw array — ~50 KB instead of ~920 KB.

That is the general rule this file is an instance of: **isolate a stack at the
point where its output is smaller than its input.** Vision qualifies
enormously; something like a tokenizer would not.

### On-demand by construction

Nothing here is started at boot. The supervisor spawns this service when the
user turns gestures on and stops it when they turn them off, so the default
state of the machine has no MediaPipe resident anywhere — which is the §4.2
"one ML stack at a time" rule, enforced by process lifetime instead of by an
unloader that has to guess.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# Gestures are already debounced inside GestureEngine, but the emit path
# crosses a process boundary from the capture thread, so it gets its own
# guard: a stuck detector must never be able to flood the bus (the reply
# queue is unbounded, and a GUI that stopped polling would grow it forever).
MIN_REPEAT_S = 0.6          # same gesture twice inside this window → dropped
MAX_PER_S = 8.0             # hard ceiling across all gestures


class GestureEmitter:
    """Decides whether a recognised gesture is worth putting on the bus.

    Pure and clock-injected: the whole throttle is unit-tested without any
    camera, any thread, or any sleeping.
    """

    def __init__(self, min_repeat_s: float = MIN_REPEAT_S,
                 max_per_s: float = MAX_PER_S,
                 clock: Callable[[], float] = time.monotonic):
        self._min_repeat = min_repeat_s
        self._max_per_s = max_per_s
        self._clock = clock
        self._last_at: dict[str, float] = {}
        self._recent: list[float] = []
        self.dropped_repeat = 0
        self.dropped_rate = 0

    def offer(self, name: str) -> bool:
        if not name:
            return False
        now = self._clock()
        last = self._last_at.get(name)
        if last is not None and (now - last) < self._min_repeat:
            self.dropped_repeat += 1
            return False
        self._recent = [t for t in self._recent if now - t < 1.0]
        if len(self._recent) >= self._max_per_s:
            self.dropped_rate += 1
            return False
        self._last_at[name] = now
        self._recent.append(now)
        return True


def _default_gesture_engine():
    # Imported inside the child only — MediaPipe never touches the GUI heap.
    from core.gesture_engine import get_gesture_engine
    return get_gesture_engine()


def _default_snapshot(timeout: float = 1.5):
    from core.vision_engine import get_vision_engine
    return get_vision_engine().snapshot(timeout=timeout)


def encode_jpeg(frame: Any, quality: int = 70) -> Optional[bytes]:
    """BGR array → JPEG bytes. ``None`` when there is nothing to encode or
    OpenCV isn't available — the caller turns that into a clean error reply
    rather than an exception across the boundary."""
    if frame is None:
        return None
    try:
        import cv2
    except ImportError:
        return None
    try:
        ok, buf = cv2.imencode(".jpg", frame,
                               [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    except Exception as e:
        log.debug("[vision_service] jpeg encode failed: %s", e)
        return None
    return bytes(buf) if ok else None


def make_vision_handler(engine_builder: Optional[Callable] = None,
                        emit: Optional[Callable[[str, dict], None]] = None,
                        snapshot_fn: Optional[Callable] = None,
                        emitter: Optional[GestureEmitter] = None):
    """Build the request handler.

    Everything heavy is injected, so the contract is unit-tested with a fake
    gesture engine: no camera, no MediaPipe, no spawn.

    Note the engine is built **eagerly**, like ``brain_service`` does — the
    child exists only because someone asked for vision, so there is nothing to
    defer, and building here means a MediaPipe import failure surfaces as the
    bus's FATAL handshake instead of as a mystery on the first ``start``.
    """
    engine = (engine_builder or _default_gesture_engine)()
    snap = snapshot_fn or _default_snapshot
    gate = emitter or GestureEmitter()
    lock = threading.RLock()

    if emit is not None:
        def _on_gesture(name: str) -> None:
            # Runs on the capture thread. Must be cheap and must never raise:
            # an exception here would propagate into VisionEngine's frame
            # fan-out and take the capture loop down with it.
            try:
                if gate.offer(name):
                    emit("gesture", {"name": name, "ts": time.time()})
            except Exception as e:
                log.debug("[vision_service] gesture emit failed: %s", e)

        try:
            engine.add_listener(_on_gesture)
        except Exception as e:
            log.warning("[vision_service] could not attach listener: %s", e)

    def _status() -> dict:
        def _try(fn, default=None):
            try:
                return fn()
            except Exception:
                return default
        return {
            "available": bool(_try(engine.is_available, False)),
            "enabled": bool(_try(engine.is_enabled, False)),
            "cursor_mode": bool(_try(getattr(engine, "is_cursor_mode",
                                             lambda: False), False)),
            "dropped_repeat": gate.dropped_repeat,
            "dropped_rate": gate.dropped_rate,
        }

    def handler(kind: str, payload: dict) -> dict:
        if kind == "ping":
            return {"pong": True}
        if kind == "status":
            return _status()
        if kind == "start":
            with lock:
                if not engine.is_available():
                    # A machine without MediaPipe is a normal configuration,
                    # not a fault: report it and let the GUI say so, rather
                    # than crash-looping the service.
                    return {"ok": False, "available": False,
                            "reason": "mediapipe unavailable"}
                ok = bool(engine.start())
            return {"ok": ok, "available": True, **_status()}
        if kind == "stop":
            with lock:
                try:
                    engine.stop()
                except Exception as e:
                    return {"ok": False, "error": repr(e)}
            return {"ok": True, **_status()}
        if kind == "cursor_mode":
            on = bool((payload or {}).get("on"))
            setter = getattr(engine, "set_cursor_mode", None)
            if not callable(setter):
                return {"ok": False, "reason": "cursor mode unsupported"}
            return {"ok": True, "cursor_mode": bool(setter(on))}
        if kind == "snapshot":
            timeout = float((payload or {}).get("timeout") or 1.5)
            quality = int((payload or {}).get("quality") or 70)
            try:
                frame = snap(timeout=timeout)
            except Exception as e:
                return {"error": f"capture failed: {e!r}"}
            jpeg = encode_jpeg(frame, quality)
            if jpeg is None:
                return {"error": "no frame"}
            # The ONE place a frame crosses the boundary — encoded, on demand.
            return {"jpeg": jpeg, "bytes": len(jpeg)}
        return {"error": f"unknown kind {kind!r}"}

    return handler


def vision_handler_factory(emit=None):
    """Top-level emit-aware factory for ServiceProxy(spawn)."""
    return make_vision_handler(emit=emit)
