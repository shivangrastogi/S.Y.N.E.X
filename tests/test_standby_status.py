"""Tests for the offline standby status reporter (used by --standby-status)."""

import pytest

from core.standby_status import offline_status, format_offline_status
from core.standby_persist import LifetimeStats


class _Config:
    def summary(self):
        return "idle 180s (away 30s) · critical 15%"


def _lifetime(sessions=3):
    # 5s active / 495s dormant across `sessions` sessions.
    return LifetimeStats(active_s=5.0, dormant_s=495.0, wakes=10,
                         spinups=4, sessions=sessions)


# ── readiness ────────────────────────────────────────────────────────── #

def test_ready_when_wake_model_present():
    s = offline_status(config=_Config(), wake_model_present=True)
    assert s["ready"] is True


def test_not_ready_when_wake_model_missing():
    s = offline_status(config=_Config(), wake_model_present=False)
    assert s["ready"] is False
    assert s["wake_model_present"] is False


def test_autostart_flag_surfaced():
    assert offline_status(config=_Config(), autostart_enabled=True)["autostart"] is True
    assert offline_status(config=_Config(), autostart_enabled=False)["autostart"] is False


# ── lifetime reporting ───────────────────────────────────────────────── #

def test_lifetime_reported_when_sessions_exist():
    s = offline_status(config=_Config(), lifetime=_lifetime(3))
    assert s["lifetime"]["sessions"] == 3
    assert s["lifetime"]["lifetime_dormant_pct"] == 99.0


def test_lifetime_omitted_when_no_sessions():
    s = offline_status(config=_Config(), lifetime=_lifetime(0))
    assert s["lifetime"] is None       # nothing banked yet


def test_lifetime_omitted_when_none():
    s = offline_status(config=_Config(), lifetime=None)
    assert s["lifetime"] is None


def test_config_omitted_when_absent():
    s = offline_status(config=None)
    assert s["config"] is None


# ── formatting ───────────────────────────────────────────────────────── #

def test_format_ready_and_history():
    text = format_offline_status(
        offline_status(config=_Config(), lifetime=_lifetime(3),
                       autostart_enabled=True, wake_model_present=True),
        name="AERIS")
    assert "ready" in text
    assert "autostart at login: on" in text
    assert "present" in text
    assert "99.0% dormant across 3 session(s)" in text


def test_format_not_ready_and_no_history():
    text = format_offline_status(
        offline_status(config=_Config(), lifetime=_lifetime(0),
                       autostart_enabled=False, wake_model_present=False))
    assert "NOT ready" in text
    assert "MISSING" in text
    assert "autostart at login: off" in text
    assert "no history yet" in text


# ── recent activity (journal) ────────────────────────────────────────── #

def test_recent_events_included():
    s = offline_status(config=_Config(),
                       recent_events=["  5s ago  wake", " 12s ago  spinup"])
    assert s["recent"] == ["  5s ago  wake", " 12s ago  spinup"]


def test_recent_events_default_empty():
    assert offline_status(config=_Config())["recent"] == []


def test_format_shows_recent_activity():
    text = format_offline_status(
        offline_status(config=_Config(), wake_model_present=True,
                       recent_events=["  5s ago  wake", " 30s ago  crash (brain died)"]))
    assert "recent activity:" in text
    assert "5s ago  wake" in text
    assert "crash (brain died)" in text


def test_format_omits_activity_when_none():
    text = format_offline_status(
        offline_status(config=_Config(), wake_model_present=True))
    assert "recent activity:" not in text
