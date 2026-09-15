"""Tests for core.routine_learner — suggests routines from presence history."""
from datetime import datetime, timedelta

import core.routine_learner as rl


_NOW = datetime(2026, 6, 22, 12, 0, 0)   # a Monday noon, fixed reference


def _arrival(day_offset, hour, minute, profile="CODING"):
    """A weekday morning arrival record N days before _NOW."""
    dt = _NOW - timedelta(days=day_offset)
    dt = dt.replace(hour=hour, minute=minute, second=0)
    return {"t": "state", "ts": dt.isoformat(), "prev": "away",
            "state": "active", "profile": profile}


def _leave(day_offset, hour, minute):
    dt = _NOW - timedelta(days=day_offset)
    dt = dt.replace(hour=hour, minute=minute, second=0)
    return {"t": "state", "ts": dt.isoformat(), "prev": "focus",
            "state": "away", "profile": "IDLE"}


def test_no_suggestion_without_enough_days():
    recs = [_arrival(d, 10, 0) for d in (1, 2)]      # only 2 days
    assert rl.learn_from_journal(recs, now=_NOW) == []


def test_stable_arrival_is_suggested():
    # 5 weekdays (offsets 0,3,4,5,6 are Mon,Fri,Thu,Wed,Tue), all ~10:00
    recs = [_arrival(d, 10, m) for d, m in
            [(0, 2), (3, 0), (4, 5), (5, 1), (6, 3)]]
    sugg = rl.learn_from_journal(recs, now=_NOW)
    arr = [s for s in sugg if s.key.startswith("arrival:CODING")]
    assert arr, "expected a CODING arrival suggestion"
    s = arr[0]
    assert s.confidence > 0.7
    assert s.routine_spec["enabled"] is False        # never auto-enabled
    assert s.routine_spec["trigger"]["params"]["cron"].endswith("1-5")


def test_scattered_arrivals_not_suggested():
    # same count (weekday offsets) but wildly spread (8:00 .. 14:00)
    recs = [_arrival(d, h, 0) for d, h in
            [(0, 8), (3, 14), (4, 9), (5, 13), (6, 11)]]
    arr = [s for s in rl.learn_from_journal(recs, now=_NOW)
           if s.key.startswith("arrival")]
    assert arr == []


def test_old_records_ignored():
    recs = [_arrival(d, 10, 0) for d in (30, 32, 34, 36, 38)]  # >21 days old
    assert rl.learn_from_journal(recs, now=_NOW) == []


def test_winddown_suggested_from_evening_leaves():
    recs = [_leave(d, 22, m) for d, m in
            [(1, 30), (2, 25), (3, 35), (4, 28), (7, 32)]]
    wd = [s for s in rl.learn_from_journal(recs, now=_NOW)
          if s.key.startswith("winddown")]
    assert wd and wd[0].routine_spec["name"] == "auto_wind_down"


def test_idle_profile_never_suggested():
    recs = [_arrival(d, 10, 0, profile="IDLE") for d in (1, 2, 3, 4, 7)]
    assert [s for s in rl.learn_from_journal(recs, now=_NOW)
            if s.key.startswith("arrival")] == []
