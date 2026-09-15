"""Tests for core.cognition — the Cognition Loop (Sentient-Partner Phase 6)."""
from __future__ import annotations

import core.anticipation as ANT
from core.cognition import CognitionLoop
from core.context_bus import ContextSnapshot


def _snap(**kw):
    base = dict(
        ts=0.0, hour=14, time_of_day="afternoon", is_quiet_hours=False,
        active_app=None, active_title=None, recent_commands=(), recent_intents=(),
        mood="neutral", presence="active", idle_seconds=0.0, battery_pct=None,
        next_event=None, summary="",
    )
    base.update(kw)
    return ContextSnapshot(**base)


def _cog(**kw):
    return CognitionLoop(enabled=True, cooldown_s=1200.0, **kw)


# ── battery ───────────────────────────────────────────────────────────────
def test_low_battery_nudge():
    t = _cog().reflect(_snap(battery_pct=15), now=1000.0)
    assert t and t.kind == "battery" and "15%" in t.message


def test_healthy_battery_no_nudge():
    assert _cog().reflect(_snap(battery_pct=80), now=1000.0) is None


# ── mood awareness ─────────────────────────────────────────────────────────
def test_frustrated_mood_suppresses_soft_thoughts():
    # a habit would normally surface, but a frustrated user only gets urgent nudges
    c = _cog()
    t = c.reflect(_snap(mood="frustrated", next_event="3pm standup"), now=1000.0)
    assert t is None                     # calendar (prio 70) < urgent (80) → dropped


def test_frustrated_still_gets_battery():
    t = _cog().reflect(_snap(mood="frustrated", battery_pct=10), now=1000.0)
    assert t and t.kind == "battery"


# ── quiet hours ────────────────────────────────────────────────────────────
def test_quiet_hours_rest_nudge():
    t = _cog().reflect(_snap(is_quiet_hours=True, hour=1, time_of_day="night",
                             presence="active"), now=1000.0)
    assert t and t.kind == "rest"


def test_quiet_hours_suppresses_calendar():
    # at night, even with an event, only rest/battery — no calendar chatter
    t = _cog().reflect(_snap(is_quiet_hours=True, presence="active",
                             next_event="tomorrow 9am review"), now=1000.0)
    assert t and t.kind == "rest"


# ── calendar ───────────────────────────────────────────────────────────────
def test_calendar_reminder_deduped():
    c = _cog()
    t1 = c.reflect(_snap(next_event="3pm standup"), now=1000.0)
    assert t1 and t1.kind == "calendar"
    # same event later → not repeated
    t2 = c.reflect(_snap(next_event="3pm standup"), now=1000.0 + 5000.0)
    assert t2 is None


# ── habit (proactive anticipation) ─────────────────────────────────────────
def _learn(tmp_path, monkeypatch):
    a = ANT.Anticipator(path=str(tmp_path / "a.json"), enabled=True, min_support=3)
    for _ in range(5):
        a.observe("get_time", "gmail kholo", "open_app", "afternoon")
    monkeypatch.setattr(ANT, "_DEFAULT", a)


def test_habit_thought_from_anticipation(tmp_path, monkeypatch):
    _learn(tmp_path, monkeypatch)
    t = _cog().reflect(_snap(recent_intents=("get_time",)), now=1000.0)
    assert t and t.kind == "habit" and "gmail kholo" in t.message


def test_manual_autonomy_silences_habit(tmp_path, monkeypatch):
    _learn(tmp_path, monkeypatch)
    monkeypatch.setenv("AERIS_AUTONOMY_LEVEL", "0")
    assert _cog().reflect(_snap(recent_intents=("get_time",)), now=1000.0) is None


# ── rate limit + kill switch ───────────────────────────────────────────────
def test_cooldown_blocks_second():
    c = _cog()
    assert c.reflect(_snap(battery_pct=10), now=1000.0) is not None
    assert c.reflect(_snap(battery_pct=10), now=1000.0 + 60) is None     # within 20 min


def test_kill_switch():
    c = CognitionLoop(enabled=False)
    assert c.reflect(_snap(battery_pct=5), now=1000.0) is None
