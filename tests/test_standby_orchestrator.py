"""Tests for the tiered-wake StandbyOrchestrator — the always-on power core.

Deterministic: a fake monotonic clock + fake spin_up/spin_down, so every
DORMANT ⇄ ACTIVE transition and its edge cases are checked without spawning a
real brain or sleeping on threads.
"""

import pytest

from core.standby_orchestrator import StandbyOrchestrator, StandbyState


class _Clock:
    """Controllable monotonic clock."""

    def __init__(self, t=1000.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class _Brain:
    """Records spin_up/spin_down calls; spin_up result is configurable."""

    def __init__(self, up_ok=True, up_raises=False, down_raises=False):
        self.up_calls = 0
        self.down_calls = 0
        self._up_ok = up_ok
        self._up_raises = up_raises
        self._down_raises = down_raises

    def up(self):
        self.up_calls += 1
        if self._up_raises:
            raise RuntimeError("spawn failed")
        return self._up_ok

    def down(self):
        self.down_calls += 1
        if self._down_raises:
            raise RuntimeError("teardown failed")


def _make(clock=None, brain=None, idle_timeout_s=180.0, on_state_change=None):
    clock = clock or _Clock()
    brain = brain or _Brain()
    orch = StandbyOrchestrator(
        spin_up=brain.up,
        spin_down=brain.down,
        idle_timeout_s=idle_timeout_s,
        now=clock,
        on_state_change=on_state_change,
    )
    return orch, clock, brain


# ── basic lifecycle ──────────────────────────────────────────────────── #

def test_starts_dormant():
    orch, _, brain = _make()
    assert orch.state is StandbyState.DORMANT
    assert brain.up_calls == 0


def test_wake_spins_brain_up():
    orch, _, brain = _make()
    assert orch.on_wake() is True
    assert orch.state is StandbyState.ACTIVE
    assert brain.up_calls == 1


def test_wake_while_active_is_idempotent():
    orch, _, brain = _make()
    orch.on_wake()
    assert orch.on_wake() is True  # second wake
    assert brain.up_calls == 1  # NOT spawned twice
    assert orch.state is StandbyState.ACTIVE


# ── idle spin-down ───────────────────────────────────────────────────── #

def test_tick_before_timeout_stays_active():
    orch, clock, brain = _make(idle_timeout_s=180)
    orch.on_wake()
    clock.advance(179)
    orch.tick()
    assert orch.state is StandbyState.ACTIVE
    assert brain.down_calls == 0


def test_tick_at_timeout_spins_down():
    orch, clock, brain = _make(idle_timeout_s=180)
    orch.on_wake()
    clock.advance(180)  # exactly the boundary → >= fires
    orch.tick()
    assert orch.state is StandbyState.DORMANT
    assert brain.down_calls == 1


def test_activity_resets_the_idle_countdown():
    orch, clock, brain = _make(idle_timeout_s=180)
    orch.on_wake()
    clock.advance(170)
    orch.on_activity()      # reset
    clock.advance(170)      # 170 since reset < 180
    orch.tick()
    assert orch.state is StandbyState.ACTIVE
    clock.advance(20)       # now 190 since reset
    orch.tick()
    assert orch.state is StandbyState.DORMANT


def test_set_idle_timeout_changes_spindown_point():
    orch, clock, brain = _make(idle_timeout_s=180)
    orch.on_wake()
    orch.set_idle_timeout(30)          # retune warm-time down
    assert orch.idle_timeout_s == 30
    clock.advance(35)                  # 35 > 30 → should fire now
    orch.tick()
    assert orch.state is StandbyState.DORMANT


def test_set_idle_timeout_is_floored():
    orch, _, _ = _make()
    orch.set_idle_timeout(0)           # absurdly small — must not be instant
    assert orch.idle_timeout_s == 5.0  # clamped to the 5s floor


def test_set_idle_timeout_coerces_type():
    orch, _, _ = _make()
    orch.set_idle_timeout("45")        # bad type coerced, not crashed
    assert orch.idle_timeout_s == 45.0


def test_tick_while_dormant_is_noop():
    orch, clock, brain = _make()
    clock.advance(10_000)
    orch.tick()
    assert orch.state is StandbyState.DORMANT
    assert brain.down_calls == 0


def test_double_tick_after_spindown_does_not_double_down():
    orch, clock, brain = _make(idle_timeout_s=60)
    orch.on_wake()
    clock.advance(60)
    orch.tick()
    orch.tick()  # already dormant
    assert brain.down_calls == 1


# ── spin-up failure handling ─────────────────────────────────────────── #

def test_spinup_failure_stays_dormant():
    orch, _, brain = _make(brain=_Brain(up_ok=False))
    assert orch.on_wake() is False
    assert orch.state is StandbyState.DORMANT
    assert brain.up_calls == 1


def test_spinup_exception_is_swallowed_and_stays_dormant():
    orch, _, brain = _make(brain=_Brain(up_raises=True))
    assert orch.on_wake() is False
    assert orch.state is StandbyState.DORMANT


def test_can_recover_after_a_failed_spinup():
    brain = _Brain(up_ok=False)
    orch, _, _ = _make(brain=brain)
    assert orch.on_wake() is False
    brain._up_ok = True  # brain becomes available
    assert orch.on_wake() is True
    assert orch.state is StandbyState.ACTIVE


# ── cycling & forced transitions ─────────────────────────────────────── #

def test_full_cycle_dormant_active_dormant_active():
    orch, clock, brain = _make(idle_timeout_s=60)
    orch.on_wake()
    assert orch.state is StandbyState.ACTIVE
    clock.advance(60)
    orch.tick()
    assert orch.state is StandbyState.DORMANT
    assert orch.on_wake() is True  # wakes again
    assert orch.state is StandbyState.ACTIVE
    assert brain.up_calls == 2
    assert brain.down_calls == 1


def test_force_dormant_spins_down():
    orch, _, brain = _make()
    orch.on_wake()
    orch.force_dormant()
    assert orch.state is StandbyState.DORMANT
    assert brain.down_calls == 1


def test_force_dormant_while_dormant_is_noop():
    orch, _, brain = _make()
    orch.force_dormant()
    assert orch.state is StandbyState.DORMANT
    assert brain.down_calls == 0


def test_spindown_exception_still_reaches_dormant():
    orch, _, _ = _make(brain=_Brain(down_raises=True))
    orch.on_wake()
    orch.force_dormant()  # spin_down raises, but finally sets DORMANT
    assert orch.state is StandbyState.DORMANT


# ── observation callbacks ────────────────────────────────────────────── #

def test_state_change_callback_fires_on_transitions():
    seen = []
    orch, clock, _ = _make(idle_timeout_s=60, on_state_change=seen.append)
    orch.on_wake()
    clock.advance(60)
    orch.tick()
    assert seen == [StandbyState.ACTIVE, StandbyState.DORMANT]


def test_raising_state_callback_does_not_break_the_machine():
    def boom(_):
        raise RuntimeError("subscriber blew up")

    orch, _, _ = _make(on_state_change=boom)
    orch.on_wake()  # must not propagate
    assert orch.state is StandbyState.ACTIVE
