"""Tests for the Hinglish time-string parser."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from core.time_parser import parse_time_string


# Use a fixed 'base' so tests are deterministic.
_BASE = datetime(2026, 5, 9, 10, 0, 0)  # Saturday 10:00 AM


def _hours_after(base, hours, minutes=0):
    return base.replace(hour=hours, minute=minutes, second=0, microsecond=0)


def test_relative_minutes():
    out = parse_time_string("10 minute mein", base=_BASE)
    assert out == _BASE + timedelta(minutes=10)


def test_relative_hours():
    out = parse_time_string("2 hours", base=_BASE)
    assert out == _BASE + timedelta(hours=2)


def test_explicit_pm():
    out = parse_time_string("5 pm", base=_BASE)
    assert out == _hours_after(_BASE, 17)


def test_explicit_am_today_or_tomorrow():
    out = parse_time_string("9 am", base=_BASE)
    # 9am is past 10am base → should roll to tomorrow
    expected = (_BASE + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    assert out == expected


def test_baje_with_morning_hint():
    out = parse_time_string("subah 7 baje", base=_BASE)
    expected = (_BASE + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
    # 7 am is past 10 am base → tomorrow
    assert out == expected


def test_baje_with_evening_hint():
    out = parse_time_string("shaam 5 baje", base=_BASE)
    assert out == _hours_after(_BASE, 17)


def test_bare_baje_defaults_to_pm_for_low_hours():
    out = parse_time_string("5 baje", base=_BASE)
    assert out == _hours_after(_BASE, 17)


def test_kal_tomorrow():
    out = parse_time_string("kal 9 baje", base=_BASE)
    expected = (_BASE + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    assert out == expected


def test_clock_time_with_minutes():
    out = parse_time_string("5:30 pm", base=_BASE)
    assert out == _hours_after(_BASE, 17, 30)


def test_unparseable_returns_none():
    assert parse_time_string("kabhi bhi", base=_BASE) is None
    assert parse_time_string("", base=_BASE) is None
    assert parse_time_string(None, base=_BASE) is None
