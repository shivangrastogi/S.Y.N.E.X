"""Idle animation profile — stop painting 30 FPS at an empty chair.

The animation bus had AC (33 ms) and battery (66 ms) profiles, and its
docstring promised an idle one too ("raised to 66 ms on battery / when the
user is idle") that was never implemented. AERIS is designed to sit open all
day, so for most of that day the reactor and particle field were repainting
30 times a second for nobody.

IMPORTANT: this file imports `ui.jarvis_v31.anim_policy`, which is Qt-free —
never `animation_bus`. Test files are collected alphabetically and this one
sorts near the front, so importing PyQt5 here pulls Qt into the pytest process
ahead of torch and every later torch import dies with
`OSError: [WinError 1114] ... c10.dll` (CLAUDE.md, "Boot order is
load-bearing"). That is exactly how the first draft of this file broke the
whole suite. Qt-level verification of the same behaviour lives in a
scratchpad script instead.
"""

from __future__ import annotations

import pytest

from ui.jarvis_v31.anim_policy import FrameRatePolicy, should_be_idle

AC, BATTERY, IDLE, AFTER = 33, 66, 125, 45.0


@pytest.fixture
def policy():
    return FrameRatePolicy(ac_ms=AC, battery_ms=BATTERY, idle_ms=IDLE,
                           idle_after_s=AFTER)


# --------------------------------------------------------------------- #
#  The threshold                                                         #
# --------------------------------------------------------------------- #

def test_idle_after_the_threshold():
    assert should_be_idle(now=100.0, last_activity=40.0, idle_after_s=45.0) is True


def test_active_before_the_threshold():
    assert should_be_idle(now=100.0, last_activity=70.0, idle_after_s=45.0) is False


def test_boundary_is_inclusive():
    assert should_be_idle(now=145.0, last_activity=100.0, idle_after_s=45.0) is True
    assert should_be_idle(now=144.9, last_activity=100.0, idle_after_s=45.0) is False


@pytest.mark.parametrize("disabled", [0, 0.0, -1, -30.0])
def test_non_positive_threshold_disables_idling(disabled):
    """Turning idling off must never drop the UI to 8 FPS, however long the
    user has been away."""
    assert should_be_idle(now=10_000.0, last_activity=0.0,
                          idle_after_s=disabled) is False


def test_future_last_activity_reads_as_active():
    """A clock jump must not be read as an enormous idle span."""
    assert should_be_idle(now=100.0, last_activity=500.0, idle_after_s=45.0) is False


# --------------------------------------------------------------------- #
#  Power and idle are two axes, not one                                  #
# --------------------------------------------------------------------- #

def test_starts_on_ac_and_active(policy):
    assert policy.is_idle is False
    assert policy.interval_ms == AC


def test_idle_drops_the_frame_rate(policy):
    assert policy.check_idle(now=policy._last_activity + AFTER + 1) == IDLE
    assert policy.is_idle is True


def test_waking_on_battery_returns_to_battery_not_ac(policy):
    """The bug this composition prevents: waking from idle while on battery
    must not jump to the 30 FPS AC rate."""
    policy.use_battery()
    assert policy.interval_ms == BATTERY

    policy.check_idle(now=policy._last_activity + AFTER + 1)
    assert policy.interval_ms == IDLE

    assert policy.note_activity() == BATTERY
    assert policy.is_idle is False


def test_power_change_while_idle_is_remembered(policy):
    """Plugging in while idle must not yank the frame rate up — but the next
    interaction should land on AC."""
    policy.use_battery()
    policy.check_idle(now=policy._last_activity + AFTER + 1)
    assert policy.interval_ms == IDLE

    assert policy.use_ac() == IDLE, "idle should still win while idle"
    assert policy.note_activity() == AC


def test_check_idle_is_idempotent(policy):
    t = policy._last_activity + AFTER + 1
    assert policy.check_idle(now=t) == IDLE
    assert policy.check_idle(now=t + 1) == IDLE
    assert policy.is_idle is True


def test_activity_then_waiting_goes_idle_again(policy):
    """Idle -> active -> idle, not a one-shot latch."""
    policy.check_idle(now=policy._last_activity + AFTER + 1)
    assert policy.is_idle is True

    policy.note_activity(now=1000.0)
    assert policy.is_idle is False
    assert policy.check_idle(now=1000.0 + AFTER + 1) == IDLE


def test_note_activity_while_active_is_a_noop(policy):
    before = policy.interval_ms
    assert policy.note_activity() == before
    assert policy.is_idle is False


def test_idle_interval_is_actually_cheaper():
    """Guards the constants themselves — an idle profile that paints more
    than the battery profile would be worse than none."""
    from ui.jarvis_v31 import anim_policy  # noqa: F401  (Qt-free import)
    assert IDLE > BATTERY > AC
