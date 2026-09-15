"""Tests for the standby control surface (pause/resume/status/quit) and the
daemon pause behaviour it drives. The tray rendering itself isn't tested (needs
a desktop) — its menu contents come from the tested ``menu_spec``."""

import pytest

from core.standby_daemon import StandbyDaemon
from core.standby_controls import StandbyControls
from core.standby_orchestrator import StandbyState
from core.standby_stats import StandbyStats


class _Ctl:
    def __init__(self, state=StandbyState.DORMANT):
        self.state = state
        self.handle_wake_calls = 0

    def handle_wake(self, stt):
        self.handle_wake_calls += 1
        return "hi"

    def tick(self):
        pass

    def on_power_change(self, *a):
        pass


class _Wake:
    def __init__(self):
        self.paused = 0
        self.resumed = 0
        self.stopped = 0

    def listen_async(self, cb):
        self.cb = cb

    def pause(self):
        self.paused += 1

    def resume(self):
        self.resumed += 1

    def stop(self):
        self.stopped += 1


def _daemon(state=StandbyState.DORMANT):
    ctl = _Ctl(state)
    wake = _Wake()
    d = StandbyDaemon(controller=ctl, wake_detector=wake, stt=lambda: "x", tts=None)
    return d, ctl, wake


# ── daemon pause / resume ────────────────────────────────────────────── #

def test_daemon_pause_and_resume():
    d, _, wake = _daemon()
    assert d.is_paused is False
    d.pause_listening()
    assert d.is_paused is True
    assert wake.paused == 1
    d.resume_listening()
    assert d.is_paused is False
    assert wake.resumed == 1


def test_on_wake_ignored_while_paused():
    d, ctl, _ = _daemon()
    d.pause_listening()
    assert d.on_wake() is None
    assert ctl.handle_wake_calls == 0  # never dispatched while paused


def test_on_wake_works_when_listening():
    d, ctl, _ = _daemon()
    assert d.on_wake() == "hi"
    assert ctl.handle_wake_calls == 1


# ── controls: actions ────────────────────────────────────────────────── #

def test_toggle_pause_flips():
    d, _, wake = _daemon()
    c = StandbyControls(d)
    assert c.toggle_pause() is True     # now paused
    assert wake.paused == 1
    assert c.toggle_pause() is False    # now listening
    assert wake.resumed == 1


def test_quit_stops_the_daemon():
    d, _, wake = _daemon()
    StandbyControls(d).quit()
    assert wake.stopped == 1


# ── controls: observation ────────────────────────────────────────────── #

def test_status_reflects_state():
    d, _, _ = _daemon(state=StandbyState.ACTIVE)
    s = StandbyControls(d).status()
    assert s["listening"] is True
    assert s["paused"] is False
    assert s["brain"] == "active"


def test_status_line_changes_with_pause():
    d, _, _ = _daemon()
    c = StandbyControls(d)
    assert "listening" in c.status_line()
    assert "dormant" in c.status_line()
    c.pause()
    assert "paused" in c.status_line()


# ── controls: menu spec + dispatch ───────────────────────────────────── #

def test_menu_spec_toggle_label_follows_state():
    d, _, _ = _daemon()
    c = StandbyControls(d)
    ids = [m["id"] for m in c.menu_spec()]
    assert ids == ["toggle", "status", "quit"]
    assert c.menu_spec()[0]["label"] == "Pause listening"
    c.pause()
    assert c.menu_spec()[0]["label"] == "Resume listening"


def test_menu_status_item_is_disabled():
    d, _, _ = _daemon()
    status_item = next(m for m in StandbyControls(d).menu_spec()
                       if m["id"] == "status")
    assert status_item.get("enabled") is False


def test_invoke_toggle_and_quit():
    d, _, wake = _daemon()
    c = StandbyControls(d)
    c.invoke("toggle")
    assert d.is_paused is True
    c.invoke("status")            # inert — no crash, no state change
    assert d.is_paused is True
    c.invoke("quit")
    assert wake.stopped == 1


# ── stats integration ────────────────────────────────────────────────── #

def test_status_includes_duty_cycle_when_stats_given():
    d, _, _ = _daemon()
    c = StandbyControls(d, stats=StandbyStats())
    s = c.status()
    assert "duty" in s
    assert "dormant_pct" in s["duty"]


def test_status_line_shows_dormant_pct_with_stats():
    d, _, _ = _daemon()
    c = StandbyControls(d, stats=StandbyStats())
    assert "dormant" in c.status_line()


def test_status_has_no_duty_without_stats():
    d, _, _ = _daemon()
    assert "duty" not in StandbyControls(d).status()


# ── health integration ───────────────────────────────────────────────── #

class _Health:
    def __init__(self, line="AERIS OK · brain dormant", report=None):
        self._line = line
        self._report = report or {"healthy": True, "brain": {"state": "dormant"}}

    def report(self):
        return self._report

    def report_line(self):
        return self._line


def test_status_includes_health_report():
    d, _, _ = _daemon()
    c = StandbyControls(d, health=_Health())
    assert "health" in c.status()
    assert c.status()["health"]["healthy"] is True


def test_status_line_prefers_health_line():
    d, _, _ = _daemon()
    c = StandbyControls(d, health=_Health(line="AERIS DEGRADED · breaker open"))
    assert c.status_line() == "AERIS DEGRADED · breaker open"


def test_status_line_marks_paused_even_with_health():
    d, _, _ = _daemon()
    c = StandbyControls(d, health=_Health())
    c.pause()
    assert "paused" in c.status_line()
