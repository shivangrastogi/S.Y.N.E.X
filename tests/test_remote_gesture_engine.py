"""The vision cutover adapter (§6.30) — fake vision, no camera, no spawn.

The interesting test here is the last one: it re-derives, from the source, the
`GestureEngine` surface that callers outside `core/` actually use, and asserts
the adapter covers it. So the cutover cannot silently rot when someone adds a
call to the real engine.
"""

from __future__ import annotations

import re
import pathlib

import pytest

from core.remote_gesture_engine import RemoteGestureEngine, split_vision_enabled


class _FakeVision:
    def __init__(self, available=True, enable_ok=True):
        self.available = available
        self.enable_ok = enable_ok
        self.enabled = False
        self.enables = 0
        self.disables = 0
        self.cursor = False
        self.queue = []
        self.last_error = ""
        self.boom = False

    def enable(self):
        self.enables += 1
        if not self.enable_ok:
            self.last_error = "mediapipe unavailable"
            return False
        self.enabled = True
        return True

    def disable(self, kill=True):
        self.disables += 1
        self.enabled = False

    def status(self):
        if self.boom:
            raise RuntimeError("service gone")
        return {"available": self.available, "enabled": self.enabled,
                "cursor_mode": self.cursor}

    def set_cursor_mode(self, on):
        self.cursor = bool(on)
        return self.cursor

    def poll_gestures(self):
        out, self.queue = self.queue, []
        return out


# Every engine built here is registered so the fixture stops its poll thread.
# `sleep_fn=lambda s: None` makes the loop a BUSY SPIN, so a `start()` without a
# matching `stop()` leaves a daemon thread pegging a core for the rest of the
# session — which is exactly what happened: two later tests in this file went
# from 0.1 s to ~50 s each, starved by leaked spinners.
_LIVE: list = []


def _eng(**kw):
    v = _FakeVision(**kw)
    e = RemoteGestureEngine(v, sleep_fn=lambda s: None)
    _LIVE.append(e)
    return e, v


@pytest.fixture(autouse=True)
def _stop_pollers():
    yield
    while _LIVE:
        try:
            _LIVE.pop().stop()
        except Exception:
            pass


class TestLifecycle:
    def test_start_enables_vision(self):
        e, v = _eng()
        assert e.start() is True and v.enables == 1 and e.is_enabled()

    def test_start_is_idempotent(self):
        e, v = _eng()
        e.start()
        e.start()
        assert v.enables == 1

    def test_stop_disables_and_kills_the_child(self):
        e, v = _eng()
        e.start()
        e.stop()
        assert v.disables == 1 and e.is_enabled() is False

    def test_stop_before_start_is_a_no_op(self):
        e, v = _eng()
        e.stop()
        assert v.disables == 0

    def test_a_refusal_is_reported_not_raised(self):
        e, v = _eng(enable_ok=False)
        assert e.start() is False and e.is_enabled() is False

    def test_availability_reflects_the_service(self):
        e, _ = _eng(available=False)
        assert e.is_available() is False
        e2, _ = _eng(available=True)
        assert e2.is_available() is True

    def test_a_dead_service_reads_as_unavailable_rather_than_raising(self):
        e, v = _eng()
        v.boom = True
        assert e.is_available() is False and e.is_cursor_mode() is False


class TestCursorMode:
    def test_round_trip(self):
        e, _ = _eng()
        assert e.set_cursor_mode(True) is True and e.is_cursor_mode() is True
        assert e.set_cursor_mode(False) is False


class TestPushPullConversion:
    """`GestureEngine` pushes to listeners; the bus pulls. This is the seam."""

    def test_polled_gestures_reach_listeners(self):
        e, v = _eng()
        seen = []
        e.add_listener(seen.append)
        v.queue = ["swipe_left", "palm"]
        assert e.drain_once() == 2
        assert seen == ["swipe_left", "palm"]

    def test_every_listener_gets_every_gesture(self):
        e, v = _eng()
        a, b = [], []
        e.add_listener(a.append)
        e.add_listener(b.append)
        v.queue = ["palm"]
        e.drain_once()
        assert a == b == ["palm"]

    def test_one_bad_listener_does_not_stop_the_others(self):
        """`GestureEngine` swallows listener errors too — and here an escaping
        exception would also kill the poll thread."""
        e, v = _eng()
        seen = []

        def _boom(name):
            raise RuntimeError("ui gone")

        e.add_listener(_boom)
        e.add_listener(seen.append)
        v.queue = ["palm"]
        assert e.drain_once() == 1 and seen == ["palm"]

    def test_a_failing_poll_is_survived(self):
        e, v = _eng()

        def _boom():
            raise RuntimeError("bus closed")

        v.poll_gestures = _boom
        assert e.drain_once() == 0

    def test_nothing_to_drain(self):
        e, _ = _eng()
        assert e.drain_once() == 0

    def test_no_listeners_still_counts_the_gesture(self):
        e, v = _eng()
        v.queue = ["palm"]
        assert e.drain_once() == 1 and e.dispatched == 1

    def test_the_poll_thread_delivers(self):
        import time
        v = _FakeVision()
        e = RemoteGestureEngine(v, poll_s=0.001)
        seen = []
        e.add_listener(seen.append)
        e.start()
        try:
            v.queue = ["palm"]
            end = time.time() + 3.0
            while time.time() < end and not seen:
                time.sleep(0.005)
        finally:
            e.stop()
        assert seen == ["palm"]


class TestFlag:
    def test_off_by_default(self):
        assert split_vision_enabled({}) is False
        assert split_vision_enabled({"AERIS_SPLIT_VISION": "0"}) is False

    def test_on_when_asked(self):
        for v in ("1", "true", "YES", "on"):
            assert split_vision_enabled({"AERIS_SPLIT_VISION": v}) is True

    def test_the_singleton_is_in_process_by_default(self, monkeypatch):
        """Never constructs the REAL GestureEngine: doing so loads MediaPipe
        and blocks (the documented freeze trap `main_window` avoids by peeking
        at `_DEFAULT_ENGINE`). A sentinel proves which branch was taken."""
        monkeypatch.delenv("AERIS_SPLIT_VISION", raising=False)
        import core.gesture_engine as ge

        class _Sentinel:
            pass

        monkeypatch.setattr(ge, "_DEFAULT_ENGINE", None)
        monkeypatch.setattr(ge, "GestureEngine", _Sentinel)
        try:
            eng = ge.get_gesture_engine()
            assert isinstance(eng, _Sentinel)
            assert not isinstance(eng, RemoteGestureEngine)
        finally:
            ge._DEFAULT_ENGINE = None

    def test_the_flag_swaps_the_singleton(self, monkeypatch):
        monkeypatch.setenv("AERIS_SPLIT_VISION", "1")
        import core.gesture_engine as ge
        monkeypatch.setattr(ge, "_DEFAULT_ENGINE", None)
        try:
            assert isinstance(ge.get_gesture_engine(), RemoteGestureEngine)
        finally:
            ge._DEFAULT_ENGINE = None

    def test_a_broken_split_falls_back_rather_than_losing_gestures(
            self, monkeypatch):
        monkeypatch.setenv("AERIS_SPLIT_VISION", "1")
        import core.gesture_engine as ge
        import core.remote_gesture_engine as rge
        monkeypatch.setattr(ge, "_DEFAULT_ENGINE", None)

        class _Sentinel:
            pass

        def _boom(*a, **k):
            raise RuntimeError("no bus")

        monkeypatch.setattr(rge, "RemoteGestureEngine", _boom)
        monkeypatch.setattr(ge, "GestureEngine", _Sentinel)   # never build the real one
        try:
            assert isinstance(ge.get_gesture_engine(), _Sentinel)
        finally:
            ge._DEFAULT_ENGINE = None


class TestTheAdapterCoversWhatCallersActuallyUse:
    """Re-derived from the source, so the cutover cannot silently rot.

    If someone adds `engine.calibrate()` in a skill, this fails and says so —
    rather than the split quietly losing a feature at runtime.
    """

    @staticmethod
    def _surface() -> set:
        """Scoped per function by `tests/surface_probe`, which is what keeps
        `main_window`'s two same-named locals (voice engine in one method,
        gesture engine in another) from contaminating each other."""
        from tests.surface_probe import engine_surface
        root = pathlib.Path(__file__).resolve().parents[1]
        return engine_surface(root, ("skills", "ui"),
                              r"get_gesture_engine\(\)|_DEFAULT_ENGINE")

    def test_every_used_name_exists_on_the_adapter(self):
        surface = self._surface()
        assert surface, "surface detection found nothing — the regex broke"
        missing = [n for n in surface
                   if not callable(getattr(RemoteGestureEngine, n, None))]
        assert not missing, (
            f"RemoteGestureEngine is missing {missing}, which callers outside "
            f"core/ use on the real GestureEngine. Split mode would lose them.")

    def test_the_surface_is_the_seven_we_scoped(self):
        """Pinned so a NEW call site shows up as a failure here, prompting a
        decision, instead of being discovered in split mode."""
        assert self._surface() == {
            "add_listener", "is_available", "is_cursor_mode", "is_enabled",
            "set_cursor_mode", "start", "stop"}
