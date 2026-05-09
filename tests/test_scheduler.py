"""Tests for the reminder scheduler. Skips cleanly if APScheduler isn't installed."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

apscheduler = pytest.importorskip("apscheduler")

from core.scheduler import ReminderScheduler


def test_schedule_fires_callback():
    fired: list[str] = []

    def _on_fire(msg: str) -> None:
        fired.append(msg)

    sched = ReminderScheduler(_on_fire)
    try:
        fire_at = datetime.now() + timedelta(seconds=1)
        rem = sched.schedule("buy milk", fire_at)
        assert rem.message == "buy milk"
        time.sleep(2)
        assert fired == ["buy milk"]
    finally:
        sched.shutdown()


def test_past_time_raises():
    sched = ReminderScheduler(lambda _msg: None)
    try:
        with pytest.raises(ValueError):
            sched.schedule("late", datetime.now() - timedelta(minutes=1))
    finally:
        sched.shutdown()


def test_list_upcoming_returns_pending_jobs():
    sched = ReminderScheduler(lambda _msg: None)
    try:
        sched.schedule("a", datetime.now() + timedelta(minutes=5))
        sched.schedule("b", datetime.now() + timedelta(minutes=10))
        upcoming = sched.list_upcoming()
        msgs = [r.message for r in upcoming]
        assert msgs == ["a", "b"]
    finally:
        sched.shutdown()


def test_cancel_removes_job():
    sched = ReminderScheduler(lambda _msg: None)
    try:
        rem = sched.schedule("c", datetime.now() + timedelta(minutes=5))
        assert sched.cancel(rem.job_id) is True
        assert sched.list_upcoming() == []
    finally:
        sched.shutdown()
