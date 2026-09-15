"""Tests for SpinUpBreaker — the brain spin-up circuit breaker.

Deterministic via an injected clock: every CLOSED → OPEN → HALF_OPEN → CLOSED
transition and the exponential backoff schedule are checked with no real waiting.
"""

import pytest

from core.standby_breaker import SpinUpBreaker, BreakerState


class _Clock:
    def __init__(self, t=1000.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def _breaker(threshold=3, base=10.0, mx=300.0, clock=None):
    clock = clock or _Clock()
    return SpinUpBreaker(threshold=threshold, base_cooldown_s=base,
                         max_cooldown_s=mx, now=clock), clock


# ── closed / tripping ────────────────────────────────────────────────── #

def test_starts_closed_and_allows():
    b, _ = _breaker()
    assert b.state is BreakerState.CLOSED
    assert b.allow() is True


def test_failures_below_threshold_stay_closed():
    b, _ = _breaker(threshold=3)
    b.record_failure()
    b.record_failure()
    assert b.state is BreakerState.CLOSED   # 2 < 3
    assert b.allow() is True
    assert b.consecutive_failures == 2


def test_threshold_failure_trips_open():
    b, _ = _breaker(threshold=3)
    for _ in range(3):
        b.record_failure()
    assert b.state is BreakerState.OPEN
    assert b.allow() is False               # fail fast — no spawn attempted


def test_success_resets_failure_count():
    b, _ = _breaker(threshold=3)
    b.record_failure()
    b.record_failure()
    b.record_success()
    assert b.consecutive_failures == 0
    assert b.state is BreakerState.CLOSED


# ── open → half-open → recovery ──────────────────────────────────────── #

def test_open_becomes_half_open_after_cooldown():
    b, clk = _breaker(threshold=1, base=10.0)
    b.record_failure()                      # trip
    assert b.state is BreakerState.OPEN
    clk.advance(9)
    assert b.allow() is False               # still cooling down
    clk.advance(1)                          # 10s elapsed
    assert b.state is BreakerState.HALF_OPEN
    assert b.allow() is True                # one trial permitted


def test_half_open_success_closes():
    b, clk = _breaker(threshold=1, base=10.0)
    b.record_failure()
    clk.advance(10)
    assert b.state is BreakerState.HALF_OPEN
    b.record_success()                      # the trial spin-up worked
    assert b.state is BreakerState.CLOSED
    assert b.allow() is True


def test_half_open_failure_reopens_with_longer_cooldown():
    b, clk = _breaker(threshold=1, base=10.0)
    b.record_failure()                      # trip #1 → cooldown 10
    clk.advance(10)
    assert b.state is BreakerState.HALF_OPEN
    b.record_failure()                      # trial failed → reopen, cooldown 20
    assert b.state is BreakerState.OPEN
    clk.advance(10)
    assert b.state is BreakerState.OPEN     # 10 < 20, still open
    clk.advance(10)
    assert b.state is BreakerState.HALF_OPEN  # 20s elapsed


def test_backoff_is_exponential_and_capped():
    b, clk = _breaker(threshold=1, base=10.0, mx=30.0)
    # trip 1 → 10
    b.record_failure()
    assert b.cooldown_remaining() == pytest.approx(10.0)
    clk.advance(10); b.record_failure()     # trip 2 → 20
    assert b.cooldown_remaining() == pytest.approx(20.0)
    clk.advance(20); b.record_failure()     # trip 3 → 40 capped at 30
    assert b.cooldown_remaining() == pytest.approx(30.0)


# ── observation ──────────────────────────────────────────────────────── #

def test_cooldown_remaining_zero_when_closed():
    b, _ = _breaker()
    assert b.cooldown_remaining() == 0.0


def test_describe_reflects_state():
    b, clk = _breaker(threshold=1, base=10.0)
    assert b.describe() == "ok"
    b.record_failure()
    assert "unavailable" in b.describe()
    clk.advance(10)
    assert "recovery" in b.describe()


def test_threshold_floor_is_one():
    b, _ = _breaker(threshold=0)            # coerced up to 1
    b.record_failure()
    assert b.state is BreakerState.OPEN
