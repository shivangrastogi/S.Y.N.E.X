"""Tests for core.eternal_presence — the always-on ambient presence layer.

No camera / torch / Qt required: signal sources are absent in the test
environment, so the engine falls back to idle + clock and we drive the
state machine by poking ``_cam_present`` and a fake clock. We exercise the
decision/cooldown logic directly via ``_fuse`` + ``_decide`` rather than the
real heartbeat thread so the tests are deterministic.
"""
from datetime import datetime

import core.eternal_presence as ep


def _engine(hour=10):
    """Engine pinned to a non-quiet hour with a fixed clock."""
    clk = lambda: datetime(2026, 6, 22, hour, 0, 0)
    e = ep.EternalPresence(heartbeat_s=1.0, clock=clk)
    return e


def _collect(e):
    out = []
    e.add_listener(out.append)
    return out


def test_time_of_day_buckets():
    f = ep._time_of_day
    assert f(datetime(2026, 6, 22, 7, 0)) == "morning"
    assert f(datetime(2026, 6, 22, 14, 0)) == "afternoon"
    assert f(datetime(2026, 6, 22, 19, 0)) == "evening"
    assert f(datetime(2026, 6, 22, 2, 0)) == "night"


def test_quiet_hours_wrap_past_midnight():
    assert ep._is_quiet(datetime(2026, 6, 22, 2, 0)) is True
    assert ep._is_quiet(datetime(2026, 6, 22, 23, 30)) is True
    assert ep._is_quiet(datetime(2026, 6, 22, 10, 0)) is False


def test_greeting_on_arrival():
    e = _engine()
    got = _collect(e)
    e._cam_present = True
    ctx = e._fuse()                       # AWAY -> ACTIVE
    for m in e._decide(ctx):
        e._emit(m)
    kinds = [m.kind for m in got]
    assert "greeting" in kinds
    assert got[0].state == ep.STATE_ACTIVE


def test_greeting_not_repeated_same_time_of_day():
    e = _engine()
    got = _collect(e)
    e._cam_present = True
    for m in e._decide(e._fuse()):
        e._emit(m)
    # bounce away and back within the same time-of-day bucket
    e._cam_present = False
    list(e._decide(e._fuse()))
    e._cam_present = True
    second = list(e._decide(e._fuse()))
    assert all(m.kind != "greeting" for m in second)


def test_farewell_on_leaving_is_low_priority():
    e = _engine()
    e._cam_present = True
    list(e._decide(e._fuse()))            # arrive
    e._cam_present = False
    moments = list(e._decide(e._fuse()))  # leave
    fare = [m for m in moments if m.kind == "farewell"]
    assert fare and fare[0].priority == 0


def test_privacy_mode_suppresses(monkeypatch):
    e = _engine()
    monkeypatch.setattr(e, "_suppressed", lambda: True)
    e._cam_present = True
    assert e._decide(e._fuse()) == []


def test_quiet_hours_suppress_everything():
    e = _engine(hour=2)                   # 02:00 → quiet
    e._cam_present = True
    assert e._decide(e._fuse()) == []


def test_cooldown_blocks_repeat():
    e = _engine()
    assert e._cool("battery_low") is True
    e._last_moment_at["battery_low"] = __import__("time").monotonic()
    assert e._cool("battery_low") is False


def test_context_shape():
    e = _engine()
    e._cam_present = True
    ctx = e._fuse()
    assert ctx.state in ep._ALL_STATES
    assert ctx.time_of_day == "morning"
    assert isinstance(ctx.battery_pct, int)
