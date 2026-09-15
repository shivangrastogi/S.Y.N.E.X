"""Tests for the Tier-0 ReflexRouter — trivial queries answered without the brain."""

from datetime import datetime

import pytest

from core.standby_reflex import ReflexRouter


def _router(dt=datetime(2026, 8, 16, 15, 45, 0)):  # Sun 16 Aug 2026, 3:45 PM
    return ReflexRouter(now=lambda: dt)


# ── time / date / day ────────────────────────────────────────────────── #

def test_time_variants_match():
    r = _router()
    for phrase in ["what time is it", "what's the time", "time", "kitne baje",
                   "samay kya hai", "What Time Is It?"]:
        assert r.match(phrase) == "It's 3:45 PM."


def test_date_variants_match():
    r = _router()
    for phrase in ["date", "what's the date", "aaj ki tareekh", "todays date"]:
        assert r.match(phrase) == "Today is Sunday, 16 August 2026."


def test_day_variants_match():
    r = _router()
    for phrase in ["what day is it", "which day", "aaj kaunsa din hai"]:
        assert r.match(phrase) == "It's Sunday."


def test_presence_variants_match():
    r = _router()
    for phrase in ["are you there", "you there", "sun rahe ho"]:
        assert r.match(phrase) == "Yes sir, I'm here."


# ── time formatting edges ────────────────────────────────────────────── #

def test_leading_zero_stripped_from_hour():
    r = _router(datetime(2026, 1, 2, 9, 5, 0))
    assert r.match("time") == "It's 9:05 AM."


def test_noon_and_midnight():
    assert _router(datetime(2026, 1, 1, 12, 0)).match("time") == "It's 12:00 PM."
    assert _router(datetime(2026, 1, 1, 0, 30)).match("time") == "It's 12:30 AM."


# ── non-reflexes fall through (safety) ───────────────────────────────── #

def test_longer_question_is_not_a_reflex():
    r = _router()
    assert r.match("what time does the pharmacy close") is None
    assert r.match("remind me at this time tomorrow") is None
    assert r.match("what's the weather") is None


def test_empty_or_none_is_not_a_reflex():
    r = _router()
    assert r.match("") is None
    assert r.match(None) is None
    assert r.match("   ") is None


def test_punctuation_and_case_tolerated():
    r = _router()
    assert r.match("  WHAT TIME IS IT???  ") == "It's 3:45 PM."


# ── control commands ─────────────────────────────────────────────────── #

def test_sleep_commands_map_to_sleep_action():
    r = _router()
    for phrase in ["go to sleep", "sleep now", "so jao", "sona", "Go To Sleep!"]:
        assert r.control(phrase) == "sleep"


def test_wake_commands_map_to_wake_action():
    r = _router()
    for phrase in ["wake up", "jaago", "jag jao", "Wake Up"]:
        assert r.control(phrase) == "wake"


def test_control_returns_none_for_non_command():
    r = _router()
    assert r.control("what time is it") is None      # info, not control
    assert r.control("what's the weather") is None
    assert r.control("") is None
    assert r.control(None) is None


def test_control_and_match_are_disjoint():
    # A control command is not an informational reflex, and vice versa.
    r = _router()
    assert r.match("go to sleep") is None
    assert r.control("what time is it") is None


def test_pause_commands_map_to_pause_action():
    r = _router()
    for phrase in ["pause", "pause listening", "stop listening", "chup ho jao"]:
        assert r.control(phrase) == "pause"


def test_status_commands_map_to_status_action():
    r = _router()
    for phrase in ["status", "system status", "health check", "report"]:
        assert r.control(phrase) == "status"
