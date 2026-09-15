"""Vision service contract + the emit throttle — fake gesture engine, no
camera, no MediaPipe, no spawn, no sleeping.
"""

from __future__ import annotations

from core.vision_service import (
    GestureEmitter, encode_jpeg, make_vision_handler, vision_handler_factory,
)


class _Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class _FakeGestures:
    def __init__(self, available=True):
        self._available = available
        self._enabled = False
        self._cursor = False
        self.listeners = []
        self.starts = 0
        self.stops = 0

    def is_available(self):
        return self._available

    def is_enabled(self):
        return self._enabled

    def is_cursor_mode(self):
        return self._cursor

    def set_cursor_mode(self, on):
        self._cursor = bool(on)
        return self._cursor

    def start(self):
        if not self._available:
            return False
        self.starts += 1
        self._enabled = True
        return True

    def stop(self):
        self.stops += 1
        self._enabled = False

    def add_listener(self, fn):
        self.listeners.append(fn)

    def fire(self, name):
        for fn in list(self.listeners):
            fn(name)


def _handler(engine=None, emit=None, snapshot_fn=None, emitter=None):
    eng = engine or _FakeGestures()
    h = make_vision_handler(engine_builder=lambda: eng, emit=emit,
                            snapshot_fn=snapshot_fn, emitter=emitter)
    return h, eng


class TestThrottle:
    def test_first_gesture_passes(self):
        assert GestureEmitter(clock=_Clock()).offer("swipe_left") is True

    def test_same_gesture_twice_in_the_window_is_dropped(self):
        c = _Clock()
        g = GestureEmitter(clock=c)
        assert g.offer("palm") is True
        c.advance(0.1)
        assert g.offer("palm") is False and g.dropped_repeat == 1

    def test_the_same_gesture_passes_again_after_the_window(self):
        c = _Clock()
        g = GestureEmitter(clock=c)
        g.offer("palm")
        c.advance(1.0)
        assert g.offer("palm") is True

    def test_a_different_gesture_is_not_blocked_by_the_repeat_guard(self):
        c = _Clock()
        g = GestureEmitter(clock=c)
        g.offer("palm")
        assert g.offer("fist") is True

    def test_a_stuck_detector_cannot_flood_the_bus(self):
        """The reply queue is unbounded and a GUI that stopped polling would
        grow it forever, so the rate ceiling is the real protection."""
        c = _Clock()
        g = GestureEmitter(max_per_s=3, clock=c)
        passed = 0
        for i in range(50):
            if g.offer(f"g{i}"):        # all distinct → repeat guard can't help
                passed += 1
            c.advance(0.001)
        assert passed == 3 and g.dropped_rate == 47

    def test_the_ceiling_is_per_second_not_forever(self):
        c = _Clock()
        g = GestureEmitter(max_per_s=2, clock=c)
        assert [g.offer("a"), g.offer("b"), g.offer("c")] == [True, True, False]
        c.advance(1.1)
        assert g.offer("d") is True

    def test_empty_names_are_ignored(self):
        assert GestureEmitter(clock=_Clock()).offer("") is False


class TestContract:
    def test_ping(self):
        h, _ = _handler()
        assert h("ping", {}) == {"pong": True}

    def test_start_and_stop(self):
        h, eng = _handler()
        r = h("start", {})
        assert r["ok"] is True and r["enabled"] is True and eng.starts == 1
        r = h("stop", {})
        assert r["ok"] is True and r["enabled"] is False and eng.stops == 1

    def test_a_machine_without_mediapipe_is_answered_not_crashed(self):
        h, eng = _handler(engine=_FakeGestures(available=False))
        r = h("start", {})
        assert r["ok"] is False and r["available"] is False
        assert "mediapipe" in r["reason"] and eng.starts == 0

    def test_status_reports_the_engine(self):
        h, _ = _handler()
        assert h("status", {})["enabled"] is False
        h("start", {})
        assert h("status", {})["enabled"] is True

    def test_cursor_mode_round_trip(self):
        h, eng = _handler()
        assert h("cursor_mode", {"on": True}) == {"ok": True, "cursor_mode": True}
        assert eng.is_cursor_mode() is True
        assert h("cursor_mode", {"on": False})["cursor_mode"] is False

    def test_cursor_mode_on_an_engine_without_it(self):
        class _NoCursor(_FakeGestures):
            set_cursor_mode = None

        h, _ = _handler(engine=_NoCursor())
        assert h("cursor_mode", {"on": True})["ok"] is False

    def test_a_stop_that_raises_is_reported_not_propagated(self):
        class _Boom(_FakeGestures):
            def stop(self):
                raise RuntimeError("device gone")

        h, _ = _handler(engine=_Boom())
        r = h("stop", {})
        assert r["ok"] is False and "device gone" in r["error"]

    def test_unknown_kind(self):
        h, _ = _handler()
        assert "unknown" in h("weird", {})["error"]

    def test_factory_is_top_level_and_emit_aware(self):
        """Windows spawn pickles the factory by qualified name, so it has to
        stay module-level — and take `emit` for the bus to wire events."""
        import inspect
        assert vision_handler_factory.__module__ == "core.vision_service"
        assert "emit" in inspect.signature(vision_handler_factory).parameters


class TestEmit:
    def test_a_recognised_gesture_reaches_the_bus(self):
        sent = []
        h, eng = _handler(emit=lambda k, p: sent.append((k, p)))
        eng.fire("swipe_left")
        assert sent[0][0] == "gesture" and sent[0][1]["name"] == "swipe_left"

    def test_the_throttle_is_applied_on_the_emit_path(self):
        sent = []
        c = _Clock()
        h, eng = _handler(emit=lambda k, p: sent.append((k, p)),
                          emitter=GestureEmitter(clock=c))
        eng.fire("palm")
        eng.fire("palm")
        assert len(sent) == 1

    def test_an_emit_that_raises_cannot_kill_the_capture_thread(self):
        """The listener runs inside VisionEngine's frame fan-out; an exception
        escaping here would take the capture loop down with it."""
        def _boom(kind, payload):
            raise RuntimeError("bus closed")

        h, eng = _handler(emit=_boom)
        eng.fire("palm")            # must not raise

    def test_no_listener_is_attached_without_emit(self):
        h, eng = _handler()
        assert eng.listeners == []


class TestSnapshot:
    def test_the_only_frame_that_crosses_is_encoded(self):
        h, _ = _handler(snapshot_fn=lambda timeout=1.5: object())
        r = h("snapshot", {})
        # No OpenCV in the fast lane → a clean error, never an exception.
        assert "jpeg" in r or r.get("error")

    def test_no_frame_is_an_error_not_a_crash(self):
        h, _ = _handler(snapshot_fn=lambda timeout=1.5: None)
        assert h("snapshot", {})["error"] == "no frame"

    def test_a_capture_that_raises_is_reported(self):
        def _boom(timeout=1.5):
            raise OSError("camera busy")

        h, _ = _handler(snapshot_fn=_boom)
        assert "camera busy" in h("snapshot", {})["error"]

    def test_encode_jpeg_tolerates_nothing_to_encode(self):
        assert encode_jpeg(None) is None
