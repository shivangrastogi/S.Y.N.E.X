"""Idle brain retirement — the state machine, with a fake proxy and a fake
clock. No spawn, no models, no sleeping: hibernation is a timing policy, and a
timing policy tested with `sleep` is a slow flaky test.
"""

from __future__ import annotations

import threading

from core.brain_hibernator import (
    AWAKE, HIBERNATED, BrainHibernator, idle_window_from_env,
)
from core.remote_brain import RemoteBrain
from core.service_bus import Msg

SNAP = {"v": 1, "dialogue": {"last_intent": "open_app", "last_entities": {},
                             "last_user_text": "", "last_reply": "",
                             "age_s": 1.0}}


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class _FakeProxy:
    def __init__(self, ready=True, snapshot=SNAP):
        self._ready = ready
        self.snapshot = snapshot
        self.starts = 0
        self.stops = 0
        self.restored_with = None
        self.snapshot_mode = "ok"     # ok | raise | error
        self.start_ok = True

    def start(self, ready_timeout=0):
        self.starts += 1
        self._ready = self.start_ok
        return self.start_ok

    def stop(self, timeout=0):
        self.stops += 1
        self._ready = False

    def is_ready(self):
        return self._ready

    def request(self, kind, payload=None, timeout=0):
        if kind == "snapshot":
            if self.snapshot_mode == "raise":
                raise TimeoutError("wedged")
            if self.snapshot_mode == "error":
                return Msg(kind=kind, id="1", ok=False, error="boom")
            return Msg(kind=kind, id="1", ok=True,
                       payload={"state": self.snapshot})
        if kind == "restore":
            self.restored_with = (payload or {}).get("state")
            return Msg(kind=kind, id="2", ok=True,
                       payload={"restored": ["dialogue"]})
        return Msg(kind=kind, id="3", ok=True,
                   payload={"reply": f"handled:{(payload or {}).get('text','')}",
                            "skill": "s"})

    def poll_events(self):
        return []


def _hib(proxy=None, idle_s=60.0):
    clock = _Clock()
    return BrainHibernator(proxy or _FakeProxy(), idle_s=idle_s,
                           clock=clock), clock


class TestWindow:
    def test_disabled_by_default(self):
        h, clock = _hib(idle_s=0)
        clock.advance(99999)
        assert not h.enabled and h.maybe_hibernate() is False
        assert h.state == AWAKE

    def test_not_yet_idle(self):
        h, clock = _hib()
        clock.advance(59)
        assert h.maybe_hibernate() is False

    def test_idle_past_the_window_retires_the_child(self):
        p = _FakeProxy()
        h, clock = _hib(p)
        clock.advance(61)
        assert h.maybe_hibernate() is True
        assert h.state == HIBERNATED and p.stops == 1 and h.hibernations == 1

    def test_activity_resets_the_countdown(self):
        h, clock = _hib()
        clock.advance(59)
        h.note_activity()
        clock.advance(59)
        assert h.maybe_hibernate() is False

    def test_already_asleep_is_not_re_hibernated(self):
        p = _FakeProxy()
        h, clock = _hib(p)
        clock.advance(61)
        h.maybe_hibernate()
        clock.advance(61)
        assert h.maybe_hibernate() is False and p.stops == 1


class TestSnapshotIsTheGate:
    def test_snapshot_is_taken_before_the_child_dies(self):
        p = _FakeProxy()
        h, clock = _hib(p)
        clock.advance(61)
        h.maybe_hibernate()
        assert h._snapshot == SNAP

    def test_a_live_child_that_will_not_snapshot_stays_resident(self):
        """Losing the conversation is worse than holding the RAM."""
        p = _FakeProxy()
        p.snapshot_mode = "raise"
        h, clock = _hib(p)
        clock.advance(61)
        assert h.maybe_hibernate() is False
        assert h.state == AWAKE and p.stops == 0

    def test_an_error_reply_also_keeps_it_resident(self):
        p = _FakeProxy()
        p.snapshot_mode = "error"
        h, clock = _hib(p)
        clock.advance(61)
        assert h.maybe_hibernate() is False and p.stops == 0

    def test_an_already_dead_child_hibernates_without_a_snapshot(self):
        """Nothing left to save, nothing gained by keeping the corpse."""
        p = _FakeProxy(ready=False)
        h, clock = _hib(p)
        clock.advance(61)
        assert h.maybe_hibernate() is True
        assert h.state == HIBERNATED and p.stops == 1


class TestWake:
    def test_wake_restores_the_conversation(self):
        p = _FakeProxy()
        h, clock = _hib(p)
        clock.advance(61)
        h.maybe_hibernate()
        assert h.ensure_awake() is True
        assert h.state == AWAKE and p.starts == 1
        assert p.restored_with == SNAP and h.last_restored == ["dialogue"]

    def test_awake_is_a_no_op(self):
        p = _FakeProxy()
        h, _ = _hib(p)
        assert h.ensure_awake() is True and p.starts == 0

    def test_empty_snapshot_skips_the_restore_round_trip(self):
        p = _FakeProxy(snapshot={"v": 1})
        h, clock = _hib(p)
        clock.advance(61)
        h.maybe_hibernate()
        h.ensure_awake()
        assert p.restored_with is None

    def test_a_brain_that_will_not_come_back_reports_failure(self):
        p = _FakeProxy()
        h, clock = _hib(p)
        clock.advance(61)
        h.maybe_hibernate()
        p.start_ok = False
        assert h.ensure_awake() is False and h.state == HIBERNATED

    def test_a_failed_restore_still_leaves_a_usable_brain(self):
        class _NoRestore(_FakeProxy):
            def request(self, kind, payload=None, timeout=0):
                if kind == "restore":
                    raise TimeoutError("nope")
                return super().request(kind, payload, timeout)

        p = _NoRestore()
        h, clock = _hib(p)
        clock.advance(61)
        h.maybe_hibernate()
        assert h.ensure_awake() is True
        assert h.state == AWAKE and h.restore_failures == 1

    def test_waking_is_single_flight(self):
        """Two turns arriving together must not spawn two brains."""
        p = _FakeProxy()
        h, clock = _hib(p)
        clock.advance(61)
        h.maybe_hibernate()
        threads = [threading.Thread(target=h.ensure_awake) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert p.starts == 1 and h.wakes == 1


class TestEnv:
    def test_unset_and_garbage_mean_off(self):
        assert idle_window_from_env({}) == 0.0
        assert idle_window_from_env({"AERIS_BRAIN_HIBERNATE_S": "soon"}) == 0.0
        assert idle_window_from_env({"AERIS_BRAIN_HIBERNATE_S": "0"}) == 0.0
        assert idle_window_from_env({"AERIS_BRAIN_HIBERNATE_S": "-5"}) == 0.0

    def test_a_positive_window_enables_it(self):
        assert idle_window_from_env({"AERIS_BRAIN_HIBERNATE_S": "300"}) == 300.0


class TestRemoteBrainIntegration:
    def test_off_by_default(self):
        rb = RemoteBrain(proxy=_FakeProxy())
        assert rb.hibernation_status()["enabled"] is False
        assert rb.tick() is False

    def test_a_turn_wakes_a_hibernated_brain_instead_of_stalling(self):
        """The utterance that should wake the brain must not be answered with
        'dimaag load ho raha hai'."""
        p = _FakeProxy()
        rb = RemoteBrain(proxy=p, hibernate_after_s=60)
        rb._hib._clock = _Clock()
        assert rb._hib.hibernate_now() is True
        assert rb.process_text("chrome kholo") == "handled:chrome kholo"
        assert p.starts == 1 and p.restored_with == SNAP

    def test_a_turn_resets_the_idle_countdown(self):
        clock = _Clock()
        rb = RemoteBrain(proxy=_FakeProxy(), hibernate_after_s=60)
        rb._hib._clock = clock
        rb._hib.note_activity()
        clock.advance(59)
        rb.process_text("hi")
        clock.advance(59)
        assert rb.tick() is False

    def test_no_offers_are_polled_while_asleep(self):
        rb = RemoteBrain(proxy=_FakeProxy(), hibernate_after_s=60)
        rb._hib.hibernate_now()
        assert rb.poll_events() == [] and rb.poll_offers() == []
