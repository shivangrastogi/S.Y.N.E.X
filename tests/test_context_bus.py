"""Tests for core.context_bus — the unified Context Bus (Sentient-Partner Phase 2).

Pure/near-pure: inject `hour`/`mood` so nothing depends on the wall clock, timezone,
or the affect singleton.
"""
from __future__ import annotations

from core.context_bus import (
    ContextBus, _time_of_day, _in_quiet_hours,
)


def test_time_of_day_buckets():
    assert _time_of_day(7) == "morning"
    assert _time_of_day(14) == "afternoon"
    assert _time_of_day(19) == "evening"
    assert _time_of_day(2) == "night"
    assert _time_of_day(23) == "night"


def test_quiet_hours_wrap_past_midnight():
    assert _in_quiet_hours(2) is True
    assert _in_quiet_hours(23) is True
    assert _in_quiet_hours(10) is False


def test_record_command_rolls():
    b = ContextBus(max_recent=3)
    for t in ["a", "b", "c", "d"]:
        b.record_command(t, intent=f"i_{t}")
    snap = b.snapshot(hour=10, mood="neutral")
    assert snap.recent_commands == ("b", "c", "d")      # oldest dropped
    assert snap.recent_intents == ("i_b", "i_c", "i_d")


def test_record_ignores_blank():
    b = ContextBus()
    b.record_command("   ")
    b.record_command("")
    assert b.snapshot(hour=10).recent_commands == ()


def test_pushed_signals_appear_in_snapshot():
    b = ContextBus()
    b.set_active_window("Chrome", "Gmail — Inbox")
    b.set_presence("idle", idle_seconds=42.0)
    b.set_battery(87)
    b.set_next_event("Standup at 10:30")
    b.record_command("volume tez karo", "volume_up")
    s = b.snapshot(hour=9, mood="content")
    assert s.active_app == "Chrome" and s.active_title == "Gmail — Inbox"
    assert s.presence == "idle" and s.idle_seconds == 42.0
    assert s.battery_pct == 87 and s.next_event == "Standup at 10:30"
    assert s.time_of_day == "morning" and s.is_quiet_hours is False
    assert s.mood == "content"


def test_summary_is_useful():
    b = ContextBus()
    b.set_active_window("Code", None)
    b.record_command("build the project", "run")
    s = b.snapshot(hour=14, mood="frustrated")
    assert "afternoon" in s.summary
    assert "Code" in s.summary
    assert "mood:frustrated" in s.summary
    assert "build the project" in s.summary


def test_subscribe_fires_on_push():
    b = ContextBus()
    seen = []
    b.subscribe(lambda snap: seen.append(snap))
    b.record_command("hello", "greet")
    b.set_active_window("Notepad")
    assert len(seen) == 2
    assert seen[-1].active_app == "Notepad"


def test_snapshot_is_immutable():
    import dataclasses
    b = ContextBus()
    s = b.snapshot(hour=10, mood="neutral")
    try:
        s.mood = "excited"          # frozen dataclass → should raise
        raised = False
    except dataclasses.FrozenInstanceError:
        raised = True
    assert raised
