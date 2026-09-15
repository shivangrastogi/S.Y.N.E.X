"""Tests for QuietHours — the overnight let-the-machine-sleep window."""

from datetime import datetime

import pytest

from core.standby_quiet import QuietHours


def _at(h, m=0):
    return datetime(2026, 1, 1, h, m)


# ── same-day window ──────────────────────────────────────────────────── #

def test_same_day_window_membership():
    q = QuietHours.parse("09:00", "17:00")
    assert q.is_quiet(_at(8, 59)) is False
    assert q.is_quiet(_at(9, 0)) is True        # inclusive start
    assert q.is_quiet(_at(12, 0)) is True
    assert q.is_quiet(_at(16, 59)) is True
    assert q.is_quiet(_at(17, 0)) is False       # exclusive end


# ── wrap-around midnight ─────────────────────────────────────────────── #

def test_wrap_around_window():
    q = QuietHours.parse("23:00", "07:00")
    assert q.is_quiet(_at(22, 59)) is False
    assert q.is_quiet(_at(23, 0)) is True
    assert q.is_quiet(_at(0, 0)) is True         # past midnight
    assert q.is_quiet(_at(3, 30)) is True
    assert q.is_quiet(_at(6, 59)) is True
    assert q.is_quiet(_at(7, 0)) is False
    assert q.is_quiet(_at(12, 0)) is False


# ── parsing / disabling ──────────────────────────────────────────────── #

def test_parse_valid():
    assert isinstance(QuietHours.parse("23:00", "07:00"), QuietHours)


def test_parse_invalid_returns_none():
    assert QuietHours.parse("25:00", "07:00") is None
    assert QuietHours.parse("23:00", "7") is None
    assert QuietHours.parse("abc", "07:00") is None
    assert QuietHours.parse("", "") is None
    assert QuietHours.parse(None, "07:00") is None


def test_parse_zero_length_window_is_disabled():
    assert QuietHours.parse("07:00", "07:00") is None   # start==end → off


def test_minutes_precision():
    q = QuietHours.parse("22:30", "06:15")
    assert q.is_quiet(_at(22, 29)) is False
    assert q.is_quiet(_at(22, 30)) is True
    assert q.is_quiet(_at(6, 14)) is True
    assert q.is_quiet(_at(6, 15)) is False


def test_describe():
    assert QuietHours.parse("23:00", "07:00").describe() == "23:00–07:00"
