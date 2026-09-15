"""RemoteVision seam — fake proxy, no spawn. Proves the on-demand lifecycle
(gestures off ⇒ zero vision residency) and that a machine with no MediaPipe
gets an answer rather than a crash loop.
"""

from __future__ import annotations

from core.remote_vision import RemoteVision, extract_gestures
from core.service_bus import Msg


class _FakeProxy:
    def __init__(self, ready=False, start_ok=True, available=True):
        self._ready = ready
        self.start_ok = start_ok
        self.available = available
        self.starts = 0
        self.stops = 0
        self.events = []
        self.calls = []
        self.mode = "ok"          # ok | raise | error
        self._alive = ready

    def start(self, ready_timeout=0):
        self.starts += 1
        self._ready = self.start_ok
        self._alive = self.start_ok
        return self.start_ok

    def is_alive(self):
        return getattr(self, "_alive", False)

    def stop(self, timeout=0):
        self.stops += 1
        self._ready = False

    def is_ready(self):
        return self._ready

    def request(self, kind, payload=None, timeout=0):
        self.calls.append(kind)
        if self.mode == "raise":
            raise TimeoutError("vision down")
        if self.mode == "error":
            return Msg(kind=kind, id="1", ok=False, error="boom")
        if kind == "start":
            if not self.available:
                return Msg(kind=kind, id="1", ok=True,
                           payload={"ok": False, "available": False,
                                    "reason": "mediapipe unavailable"})
            return Msg(kind=kind, id="1", ok=True,
                       payload={"ok": True, "available": True, "enabled": True})
        if kind == "status":
            return Msg(kind=kind, id="2", ok=True,
                       payload={"available": True, "enabled": True})
        if kind == "cursor_mode":
            return Msg(kind=kind, id="3", ok=True,
                       payload={"ok": True,
                                "cursor_mode": bool((payload or {}).get("on"))})
        if kind == "snapshot":
            return Msg(kind=kind, id="4", ok=True,
                       payload={"jpeg": b"\xff\xd8jpeg", "bytes": 6})
        return Msg(kind=kind, id="5", ok=True, payload={"ok": True})

    def poll_events(self):
        out, self.events = self.events, []
        return out


class TestExtract:
    def test_picks_gesture_events_in_order(self):
        evs = [Msg(kind="event:gesture", payload={"name": "palm"}),
               Msg(kind="event:offer", payload={"text": "not a gesture"}),
               Msg(kind="event:gesture", payload={"name": "fist"})]
        assert extract_gestures(evs) == ["palm", "fist"]

    def test_malformed_events_are_skipped_not_raised(self):
        evs = [Msg(kind="event:gesture", payload=None),
               Msg(kind="event:gesture", payload={"name": "   "}),
               {"kind": "event:gesture", "payload": {"name": "wave"}},
               None]
        assert extract_gestures(evs) == ["wave"]

    def test_nothing_in_nothing_out(self):
        assert extract_gestures([]) == [] and extract_gestures(None) == []


class TestOnDemandLifecycle:
    def test_enable_spawns_then_starts(self):
        p = _FakeProxy()
        rv = RemoteVision(proxy=p)
        assert rv.enable() is True
        assert p.starts == 1 and p.calls == ["start"]

    def test_disable_kills_the_child_so_the_ram_comes_back(self):
        """'Gestures off' has to mean zero vision residency — a stopped
        capture with a live MediaPipe child would defeat the point."""
        p = _FakeProxy()
        rv = RemoteVision(proxy=p)
        rv.enable()
        rv.disable()
        assert p.calls == ["start", "stop"] and p.stops == 1
        assert rv.is_running() is False

    def test_disable_can_keep_the_child_when_asked(self):
        p = _FakeProxy()
        rv = RemoteVision(proxy=p)
        rv.enable()
        rv.disable(kill=False)
        assert p.stops == 0 and rv.is_running() is True

    def test_enable_twice_does_not_spawn_twice(self):
        p = _FakeProxy()
        rv = RemoteVision(proxy=p)
        rv.enable()
        rv.enable()
        assert p.starts == 1

    def test_disable_before_enable_is_a_no_op(self):
        p = _FakeProxy()
        RemoteVision(proxy=p).disable()
        assert p.calls == [] and p.stops == 0


class TestDegradation:
    def test_no_mediapipe_is_a_reason_not_an_exception(self):
        p = _FakeProxy(available=False)
        rv = RemoteVision(proxy=p)
        assert rv.enable() is False
        assert "mediapipe" in rv.last_error

    def test_a_child_that_will_not_come_up(self):
        p = _FakeProxy(start_ok=False)
        rv = RemoteVision(proxy=p)
        assert rv.enable() is False and rv.last_error

    def test_a_service_that_does_not_answer(self):
        p = _FakeProxy()
        p.mode = "raise"
        rv = RemoteVision(proxy=p)
        assert rv.enable() is False and rv.last_error

    def test_status_when_nothing_is_running(self):
        rv = RemoteVision(proxy=_FakeProxy())
        assert rv.status() == {"available": False, "enabled": False,
                               "running": False}

    def test_polling_a_dead_service_is_empty_not_an_error(self):
        rv = RemoteVision(proxy=_FakeProxy())
        assert rv.poll_gestures() == []


class TestSurface:
    def test_gestures_reach_the_gui(self):
        p = _FakeProxy()
        rv = RemoteVision(proxy=p)
        rv.enable()
        p.events = [Msg(kind="event:gesture", payload={"name": "swipe_left"})]
        assert rv.poll_gestures() == ["swipe_left"]
        assert rv.poll_gestures() == []          # drained

    def test_cursor_mode(self):
        rv = RemoteVision(proxy=_FakeProxy())
        rv.enable()
        assert rv.set_cursor_mode(True) is True
        assert rv.set_cursor_mode(False) is False

    def test_snapshot_returns_bytes(self):
        rv = RemoteVision(proxy=_FakeProxy())
        rv.enable()
        assert rv.snapshot_jpeg() == b"\xff\xd8jpeg"

    def test_snapshot_failure_is_none_with_a_reason(self):
        p = _FakeProxy()
        rv = RemoteVision(proxy=p)
        rv.enable()
        p.mode = "error"
        assert rv.snapshot_jpeg() is None and rv.last_error


class TestHarness:
    """`run_vision_split.watch` — the live-validation loop, with fakes."""

    def test_drains_gestures_until_told_to_stop(self):
        from run_vision_split import watch

        class _V:
            def __init__(self):
                self.batches = [["palm"], [], ["fist", "wave"]]

            def poll_gestures(self):
                return self.batches.pop(0) if self.batches else []

        v = _V()
        out = []
        ticks = [0]

        def _stop():
            ticks[0] += 1
            return ticks[0] > 3

        n = watch(v, out.append, _stop, sleep_fn=lambda s: None)
        assert n == 3
        assert out == ["  gesture: palm", "  gesture: fist", "  gesture: wave"]

    def test_stops_immediately_when_asked(self):
        from run_vision_split import watch

        class _V:
            def poll_gestures(self):
                raise AssertionError("should not poll")

        assert watch(_V(), print, lambda: True, sleep_fn=lambda s: None) == 0
