"""Tests for StandbyHealth — the aggregated standby diagnostic.

Uses light fakes for the controller/stats/store/config plus a real SpinUpBreaker
so the verdict logic (healthy vs degraded) and the report assembly — including
partial wirings — are checked deterministically.
"""

import pytest

from core.standby_health import StandbyHealth
from core.standby_orchestrator import StandbyState
from core.standby_breaker import SpinUpBreaker


class _Clock:
    def __init__(self, t=1000.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class _Ctl:
    def __init__(self, state=StandbyState.DORMANT, crashes=0, breaker=None):
        self.state = state
        self.crashes = crashes
        self.breaker = breaker


class _Stats:
    def __init__(self, snap):
        self._snap = snap

    def snapshot(self):
        return self._snap


class _Lifetime:
    def __init__(self, snap):
        self._snap = snap

    def snapshot(self):
        return self._snap


class _Store:
    def __init__(self, snap):
        self._snap = snap

    def merged(self, session):
        return _Lifetime(self._snap)

    @property
    def baseline(self):
        return _Lifetime(self._snap)


class _Config:
    def summary(self):
        return "idle 180s · critical 15%"


_SESSION = {"uptime_s": 100.0, "active_s": 1.0, "dormant_s": 99.0,
            "dormant_pct": 99.0, "wakes": 2, "spinups": 1, "avg_active_s": 1.0}
_LIFETIME = {"lifetime_active_s": 5.0, "lifetime_dormant_s": 495.0,
             "lifetime_dormant_pct": 99.0, "lifetime_wakes": 10,
             "lifetime_spinups": 4, "sessions": 3}


def _open_breaker():
    b = SpinUpBreaker(threshold=1, base_cooldown_s=10.0)
    b.record_failure()          # trip → OPEN
    return b


# ── verdict ──────────────────────────────────────────────────────────── #

def test_healthy_when_breaker_closed():
    h = StandbyHealth(controller=_Ctl(breaker=SpinUpBreaker()))
    assert h.healthy() is True
    assert h.degraded_message() is None


def test_degraded_when_breaker_open():
    h = StandbyHealth(controller=_Ctl(breaker=_open_breaker()))
    assert h.healthy() is False
    assert "unavailable" in h.degraded_message()


def test_half_open_is_not_degraded():
    clk = _Clock()
    b = SpinUpBreaker(threshold=1, base_cooldown_s=10.0, now=clk)
    b.record_failure()
    clk.advance(10)             # OPEN → HALF_OPEN
    h = StandbyHealth(controller=_Ctl(breaker=b))
    assert h.healthy() is True  # recovering, not degraded


def test_no_breaker_is_healthy():
    h = StandbyHealth(controller=_Ctl(breaker=None))
    assert h.healthy() is True


# ── report assembly ──────────────────────────────────────────────────── #

def test_full_report_structure():
    h = StandbyHealth(controller=_Ctl(crashes=2, breaker=SpinUpBreaker()),
                      stats=_Stats(_SESSION), store=_Store(_LIFETIME),
                      config=_Config())
    r = h.report()
    assert r["healthy"] is True
    assert r["brain"]["state"] == "dormant"
    assert r["brain"]["crashes"] == 2
    assert r["brain"]["breaker"] == "closed"
    assert r["session"]["dormant_pct"] == 99.0
    assert r["lifetime"]["sessions"] == 3
    assert "idle" in r["config"]


def test_report_omits_missing_pieces():
    h = StandbyHealth(controller=_Ctl(breaker=SpinUpBreaker()))
    r = h.report()
    assert r["session"] is None
    assert r["lifetime"] is None
    assert r["config"] is None
    assert r["brain"]["state"] == "dormant"   # still valid


def test_lifetime_from_baseline_when_no_stats():
    # store present but no stats → lifetime comes from the persisted baseline.
    h = StandbyHealth(controller=_Ctl(breaker=SpinUpBreaker()),
                      store=_Store(_LIFETIME))
    assert h.report()["lifetime"]["sessions"] == 3


def test_report_survives_broken_store():
    class _BadStore:
        def merged(self, s):
            raise RuntimeError("disk gone")
        @property
        def baseline(self):
            raise RuntimeError("disk gone")
    h = StandbyHealth(controller=_Ctl(breaker=SpinUpBreaker()),
                      stats=_Stats(_SESSION), store=_BadStore())
    assert h.report()["lifetime"] is None    # swallowed, report still built


# ── human-readable ───────────────────────────────────────────────────── #

def test_report_line_ok():
    h = StandbyHealth(controller=_Ctl(breaker=SpinUpBreaker()), stats=_Stats(_SESSION))
    line = h.report_line()
    assert "OK" in line
    assert "99% dormant" in line


def test_report_line_degraded_shows_breaker():
    h = StandbyHealth(controller=_Ctl(crashes=1, breaker=_open_breaker()),
                      stats=_Stats(_SESSION))
    line = h.report_line()
    assert "DEGRADED" in line
    assert "breaker open" in line
    assert "1 recovered" in line


def test_spoken_summary_healthy():
    h = StandbyHealth(controller=_Ctl(breaker=SpinUpBreaker()), stats=_Stats(_SESSION))
    line = h.spoken_summary()
    assert line.startswith("I'm healthy")
    assert "the brain is dormant" in line
    assert "dormant 99 percent of the time" in line
    assert line.endswith("sir.")


def test_spoken_summary_degraded_and_crashes():
    h = StandbyHealth(controller=_Ctl(crashes=2, breaker=_open_breaker()),
                      stats=_Stats(_SESSION))
    line = h.spoken_summary()
    assert line.startswith("I'm degraded")
    assert "self-healed 2 times" in line


def test_spoken_summary_singular_crash():
    h = StandbyHealth(controller=_Ctl(crashes=1, breaker=SpinUpBreaker()))
    assert "self-healed 1 time" in h.spoken_summary()
    assert "1 times" not in h.spoken_summary()


def test_format_report_is_multiline():
    h = StandbyHealth(controller=_Ctl(crashes=0, breaker=SpinUpBreaker()),
                      stats=_Stats(_SESSION), store=_Store(_LIFETIME),
                      config=_Config())
    text = h.format_report()
    assert "brain:" in text
    assert "breaker:" in text
    assert "session:" in text
    assert "lifetime:" in text
    assert "config:" in text
