"""Tests for the standby Windows power policy (pure flag logic) and the daemon's
execution-state management (with a fake SetThreadExecutionState)."""

import pytest

from core.standby_power import (
    StandbyPowerPolicy,
    ES_CONTINUOUS,
    ES_SYSTEM_REQUIRED,
    ES_DISPLAY_REQUIRED,
)
from core.standby_daemon import StandbyDaemon
from core.standby_quiet import QuietHours
from datetime import datetime


# ── policy: flag selection ───────────────────────────────────────────── #

def test_ac_keeps_system_awake_but_not_display():
    p = StandbyPowerPolicy()
    flags = p.flags_for(on_battery=False, percent=100)
    assert flags & ES_CONTINUOUS
    assert flags & ES_SYSTEM_REQUIRED           # stay awake to listen
    assert not (flags & ES_DISPLAY_REQUIRED)    # but let the display sleep


def test_battery_healthy_still_listens():
    p = StandbyPowerPolicy(keep_awake_on_battery=True, critical_pct=15)
    flags = p.flags_for(on_battery=True, percent=50)
    assert flags & ES_SYSTEM_REQUIRED


def test_battery_critical_lets_the_system_sleep():
    p = StandbyPowerPolicy(critical_pct=15)
    flags = p.flags_for(on_battery=True, percent=10)
    assert flags == ES_CONTINUOUS               # no SYSTEM_REQUIRED → may sleep


def test_opt_out_of_listening_on_battery():
    p = StandbyPowerPolicy(keep_awake_on_battery=False)
    flags = p.flags_for(on_battery=True, percent=90)
    assert flags == ES_CONTINUOUS


def test_keep_system_awake_predicate():
    p = StandbyPowerPolicy(critical_pct=15)
    assert p.keep_system_awake(False, 5) is True     # AC always
    assert p.keep_system_awake(True, 50) is True
    assert p.keep_system_awake(True, 15) is False    # at threshold → sleep
    assert p.keep_system_awake(True, 16) is True


def test_describe_is_human():
    p = StandbyPowerPolicy()
    assert "listen" in p.describe(False, 100).lower()
    assert "sleep" in p.describe(True, 5).lower()


# ── daemon: execution-state management ───────────────────────────────── #

class _FakeController:
    def __init__(self):
        self.tick_calls = 0

    def handle_wake(self, stt):
        return None

    def tick(self):
        self.tick_calls += 1

    def on_power_change(self, *a):
        pass


class _FakeWake:
    def listen_async(self, cb):
        self.cb = cb

    def stop(self):
        pass


class _FakePowerSnap:
    def __init__(self, on_battery, percent):
        self.on_battery = on_battery
        self.percent = percent


class _FakePower:
    def __init__(self, snap):
        self._snap = snap
        self.cb = None

    def on_power_change(self, cb):
        self.cb = cb

    def snapshot(self):
        return self._snap

    def fire(self, on_battery, percent, plugged):
        self.cb(on_battery, percent, plugged)


def _daemon_with_policy(snap=None, stop_after=1):
    exec_calls = []
    box = {}

    def sleeper(_dt):
        box["n"] = box.get("n", 0) + 1
        if box["n"] >= stop_after:
            box["d"]._stop.set()

    power = _FakePower(snap) if snap is not None else None
    d = StandbyDaemon(
        controller=_FakeController(),
        wake_detector=_FakeWake(),
        power_monitor=power,
        stt=lambda: None,
        sleep=sleeper,
        power_policy=StandbyPowerPolicy(critical_pct=15),
        set_execution_state=exec_calls.append,
    )
    box["d"] = d
    return d, exec_calls, power


def test_start_applies_initial_hold_from_snapshot_ac():
    d, exec_calls, _ = _daemon_with_policy(snap=_FakePowerSnap(False, 100))
    d.start()
    d.stop()
    # first call is the initial hold: AC → SYSTEM_REQUIRED
    assert exec_calls[0] & ES_SYSTEM_REQUIRED


def test_tick_reasserts_the_hold():
    d, exec_calls, _ = _daemon_with_policy(snap=_FakePowerSnap(False, 100),
                                           stop_after=1)
    d.start()
    d.stop()
    # initial hold + at least one tick re-assert happened
    assert len([f for f in exec_calls if f & ES_SYSTEM_REQUIRED]) >= 2


def test_power_change_to_critical_drops_the_system_hold():
    d, exec_calls, power = _daemon_with_policy(snap=_FakePowerSnap(False, 100),
                                               stop_after=999)
    d.start()
    power.fire(on_battery=True, percent=5, plugged=False)
    # the recomputed flags no longer request SYSTEM_REQUIRED
    assert not (d._exec_flags & ES_SYSTEM_REQUIRED)
    d.stop()


def test_stop_releases_the_hold():
    d, exec_calls, _ = _daemon_with_policy(snap=_FakePowerSnap(False, 100))
    d.start()
    d.stop()
    assert exec_calls[-1] == ES_CONTINUOUS   # released → machine free to sleep


def test_no_policy_never_touches_execution_state():
    exec_calls = []
    d = StandbyDaemon(
        controller=_FakeController(),
        wake_detector=_FakeWake(),
        power_monitor=None,
        stt=lambda: None,
        sleep=lambda _dt: d._stop.set(),
        power_policy=None,
        set_execution_state=exec_calls.append,
    )
    d.start()
    d.stop()
    assert exec_calls == []


# ── quiet hours: release the system hold overnight ───────────────────── #

def _quiet_daemon(exec_calls, *, quiet, at):
    return StandbyDaemon(
        controller=_FakeController(),
        wake_detector=_FakeWake(),
        stt=lambda: None,
        power_policy=StandbyPowerPolicy(critical_pct=15),
        set_execution_state=exec_calls.append,
        quiet_hours=quiet,
        now_dt=lambda: at,
    )


def test_quiet_hours_releases_system_hold():
    calls = []
    d = _quiet_daemon(calls, quiet=QuietHours.parse("23:00", "07:00"),
                      at=datetime(2026, 1, 1, 2, 0))     # 2am → quiet
    d._exec_flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED   # normally holding awake
    d._reassert_exec()
    assert calls[-1] == ES_CONTINUOUS                    # dropped → machine may sleep
    assert d.in_quiet_hours() is True


def test_outside_quiet_hours_keeps_hold():
    calls = []
    d = _quiet_daemon(calls, quiet=QuietHours.parse("23:00", "07:00"),
                      at=datetime(2026, 1, 1, 14, 0))    # 2pm → not quiet
    d._exec_flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    d._reassert_exec()
    assert calls[-1] & ES_SYSTEM_REQUIRED               # hold preserved
    assert d.in_quiet_hours() is False


def test_no_quiet_hours_keeps_hold():
    calls = []
    d = _quiet_daemon(calls, quiet=None, at=datetime(2026, 1, 1, 2, 0))
    d._exec_flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    d._reassert_exec()
    assert calls[-1] & ES_SYSTEM_REQUIRED
    assert d.in_quiet_hours() is False
