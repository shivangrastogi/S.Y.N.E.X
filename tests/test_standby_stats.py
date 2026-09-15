"""Tests for StandbyStats — the standby duty-cycle telemetry."""

import pytest

from core.standby_stats import StandbyStats
from core.standby_orchestrator import StandbyState


class _Clock:
    def __init__(self, t=1000.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def _stats():
    clk = _Clock()
    return StandbyStats(now=clk), clk


# ── initial ──────────────────────────────────────────────────────────── #

def test_starts_dormant_and_empty():
    s, _ = _stats()
    snap = s.snapshot()
    assert snap["uptime_s"] == 0.0
    assert snap["dormant_pct"] == 100.0   # nothing yet → treated as fully dormant
    assert snap["wakes"] == 0
    assert snap["spinups"] == 0
    assert snap["avg_active_s"] == 0.0


def test_wake_count():
    s, _ = _stats()
    s.on_wake()
    s.on_wake()
    assert s.snapshot()["wakes"] == 2


# ── time in state ────────────────────────────────────────────────────── #

def test_spinup_counted_on_dormant_to_active():
    s, clk = _stats()
    clk.advance(90)
    s.on_state_change(StandbyState.ACTIVE)
    assert s.snapshot()["spinups"] == 1


def test_duty_cycle_after_one_cycle():
    s, clk = _stats()
    clk.advance(90)                          # dormant 90s
    s.on_state_change(StandbyState.ACTIVE)
    clk.advance(10)                          # active 10s
    s.on_state_change(StandbyState.DORMANT)
    snap = s.snapshot()
    assert snap["active_s"] == 10.0
    assert snap["dormant_s"] == 90.0
    assert snap["dormant_pct"] == 90.0
    assert snap["avg_active_s"] == 10.0      # 10s / 1 spinup


def test_snapshot_includes_in_progress_segment():
    s, clk = _stats()
    clk.advance(90)
    s.on_state_change(StandbyState.ACTIVE)
    clk.advance(5)                           # still active, not yet ended
    snap = s.snapshot()
    assert snap["active_s"] == 5.0           # in-progress active counted
    assert snap["dormant_s"] == 90.0
    assert snap["dormant_pct"] == pytest.approx(94.7, abs=0.1)


def test_multiple_cycles_average_active():
    s, clk = _stats()
    # cycle 1: active 20s
    clk.advance(100)
    s.on_state_change(StandbyState.ACTIVE)
    clk.advance(20)
    s.on_state_change(StandbyState.DORMANT)
    # cycle 2: active 40s
    clk.advance(100)
    s.on_state_change(StandbyState.ACTIVE)
    clk.advance(40)
    s.on_state_change(StandbyState.DORMANT)
    snap = s.snapshot()
    assert snap["spinups"] == 2
    assert snap["active_s"] == 60.0
    assert snap["avg_active_s"] == 30.0      # (20+40)/2


def test_uptime_tracks_total_elapsed():
    s, clk = _stats()
    clk.advance(250)
    assert s.snapshot()["uptime_s"] == 250.0


def test_summary_line_is_human():
    s, clk = _stats()
    clk.advance(100)
    s.on_state_change(StandbyState.ACTIVE)
    clk.advance(1)
    line = s.summary_line()
    assert "dormant" in line and "%" in line and "spin-up" in line


# ── thread-safety (the periodic checkpoint reads while threads write) ─── #

def test_concurrent_on_wake_loses_no_increments():
    import threading
    s = StandbyStats()
    threads, per = 8, 2000
    barrier = threading.Barrier(threads)

    def hammer():
        barrier.wait()               # maximise contention
        for _ in range(per):
            s.on_wake()

    ts = [threading.Thread(target=hammer) for _ in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert s.snapshot()["wakes"] == threads * per   # lock → no lost updates


def test_snapshot_never_tears_under_concurrent_state_changes():
    import threading
    s = StandbyStats()
    stop = threading.Event()

    def flip():
        while not stop.is_set():
            s.on_state_change(StandbyState.ACTIVE)
            s.on_state_change(StandbyState.DORMANT)

    w = threading.Thread(target=flip)
    w.start()
    try:
        for _ in range(3000):
            snap = s.snapshot()          # must never raise or read torn state
            assert snap["dormant_s"] >= 0.0
            assert snap["active_s"] >= 0.0
            assert 0.0 <= snap["dormant_pct"] <= 100.0
    finally:
        stop.set()
        w.join()
