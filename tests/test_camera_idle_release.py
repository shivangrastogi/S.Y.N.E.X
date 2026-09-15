"""Idle camera release — roadmap §4.2 "sensors on-demand".

`VisionEngine` already held the webcam open only while something was
subscribed and released it when the last consumer left; that half was always
right. The gap was `GestureEngine`, which never unsubscribed on its own — so
enabling gestures once kept the camera and MediaPipe inference running at
~30 fps until the app closed, whether or not a hand had been in front of it
for hours ("always-on sensors", con #7 in this doc's assessment).

OFF BY DEFAULT: auto-release means gestures silently stop working until
switched back on, which is the user's call to make. `AERIS_CAMERA_IDLE_S`
opts in.
"""

from __future__ import annotations

import threading
import time

import pytest

from core.gesture_engine import camera_idle_seconds


# --------------------------------------------------------------------- #
#  The switch                                                            #
# --------------------------------------------------------------------- #

def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AERIS_CAMERA_IDLE_S", raising=False)
    assert camera_idle_seconds() == 0.0


def test_blank_is_disabled(monkeypatch):
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "   ")
    assert camera_idle_seconds() == 0.0


def test_reads_the_configured_window(monkeypatch):
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "90")
    assert camera_idle_seconds() == 90.0


def test_garbage_disables_rather_than_raising(monkeypatch):
    """A bad value must not break the capture thread mid-frame."""
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "two minutes")
    assert camera_idle_seconds() == 0.0


def test_negative_clamps_to_disabled(monkeypatch):
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "-5")
    assert camera_idle_seconds() == 0.0


def test_read_at_call_time(monkeypatch):
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "10")
    assert camera_idle_seconds() == 10.0
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "20")
    assert camera_idle_seconds() == 20.0


# --------------------------------------------------------------------- #
#  The release decision                                                  #
# --------------------------------------------------------------------- #

class _Engine:
    """The release logic bound to a stand-in, so no camera or MediaPipe is
    needed. GestureEngine.__init__ probes MediaPipe and would be slow (and
    hardware-dependent) here."""

    def __init__(self):
        from core.gesture_engine import GestureEngine
        self._enabled = True
        self._last_hand_at = time.monotonic()
        self._idle_release_pending = False
        self.stopped = threading.Event()
        self._maybe_idle_release = GestureEngine._maybe_idle_release.__get__(self)
        self._note_hand_seen = GestureEngine._note_hand_seen.__get__(self)

    def stop(self):
        self.stopped.set()


def test_no_release_when_disabled(monkeypatch):
    monkeypatch.delenv("AERIS_CAMERA_IDLE_S", raising=False)
    e = _Engine()
    e._last_hand_at = time.monotonic() - 10_000     # idle for hours
    e._maybe_idle_release()
    assert not e.stopped.wait(0.5), "released the camera with the feature off"


def test_no_release_while_a_hand_is_present(monkeypatch):
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "60")
    e = _Engine()
    e._maybe_idle_release()
    assert not e.stopped.wait(0.5), "released while the user was gesturing"


def test_releases_after_the_window(monkeypatch):
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "5")
    e = _Engine()
    e._last_hand_at = time.monotonic() - 60
    e._maybe_idle_release()
    assert e.stopped.wait(5), "camera never released after the idle window"


def test_release_happens_off_the_capture_thread(monkeypatch):
    """stop() -> unsubscribe() -> VisionEngine.stop() joins the capture
    thread. Calling it inline from the frame callback would join the current
    thread and raise, so the release must be handed to a worker."""
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "5")

    caller = {}

    class _E(_Engine):
        def stop(self):
            caller["thread"] = threading.current_thread()
            self.stopped.set()

    e = _E()
    e._last_hand_at = time.monotonic() - 60
    here = threading.current_thread()
    e._maybe_idle_release()

    assert e.stopped.wait(5)
    assert caller["thread"] is not here, \
        "stop() ran on the calling (capture) thread — that self-joins"


def test_only_one_release_is_scheduled(monkeypatch):
    """_mark_neutral_frame runs on every hand-free frame (~30/s); that must
    not spawn 30 release threads a second."""
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "5")

    stops = []

    class _E(_Engine):
        def stop(self):
            stops.append(1)
            time.sleep(0.2)         # a real stop joins a thread — not instant
            self.stopped.set()

    e = _E()
    e._last_hand_at = time.monotonic() - 60
    for _ in range(30):
        e._maybe_idle_release()

    assert e.stopped.wait(5)
    time.sleep(0.3)
    assert stops == [1], f"scheduled {len(stops)} releases instead of 1"


def test_a_hand_reappearing_resets_the_clock(monkeypatch):
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "5")
    e = _Engine()
    e._last_hand_at = time.monotonic() - 60

    e._note_hand_seen()             # user came back
    e._maybe_idle_release()
    assert not e.stopped.wait(0.5), "released despite a hand in frame"


def test_no_release_when_gestures_are_already_off(monkeypatch):
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "5")
    e = _Engine()
    e._enabled = False
    e._last_hand_at = time.monotonic() - 60
    e._maybe_idle_release()
    assert not e.stopped.wait(0.5)


def test_a_failing_stop_clears_the_pending_flag(monkeypatch):
    """Otherwise one failed release would block every future one."""
    monkeypatch.setenv("AERIS_CAMERA_IDLE_S", "5")

    class _E(_Engine):
        def stop(self):
            self.stopped.set()
            raise RuntimeError("camera handle already gone")

    e = _E()
    e._last_hand_at = time.monotonic() - 60
    e._maybe_idle_release()
    assert e.stopped.wait(5)

    deadline = time.time() + 5
    while e._idle_release_pending and time.time() < deadline:
        time.sleep(0.05)
    assert e._idle_release_pending is False
