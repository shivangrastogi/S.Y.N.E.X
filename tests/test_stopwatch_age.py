"""Count-up stopwatch + age calculator (fast lane, injected clock)."""

from __future__ import annotations

import datetime as dt

import pytest

from core.stopwatch import Stopwatch, fmt_elapsed
from core.datetime_tools import age_from


class TestStopwatch:
    def _sw(self):
        self.t = [1000.0]
        return Stopwatch(now_fn=lambda: self.t[0])

    def test_start_stop_cycle(self):
        sw = self._sw()
        assert sw.start() is True and sw.is_running()
        self.t[0] += 95
        assert abs(sw.stop() - 95) < 0.01
        assert not sw.is_running()

    def test_double_start_guard(self):
        sw = self._sw()
        sw.start()
        assert sw.start() is False       # already running, kept

    def test_lap_totals_and_deltas(self):
        sw = self._sw()
        sw.start()
        self.t[0] += 60
        assert sw.lap() == (60, 60)
        self.t[0] += 25
        assert sw.lap() == (85, 25)

    def test_ops_when_not_running(self):
        sw = self._sw()
        assert sw.stop() is None
        assert sw.lap() is None
        assert sw.elapsed() is None

    @pytest.mark.parametrize("secs,expect", [
        (5, "5s"), (95, "1m 35s"), (3725, "1h 2m 5s"), (0, "0s"),
    ])
    def test_format(self, secs, expect):
        assert fmt_elapsed(secs) == expect

    def test_stop_clears_laps(self):
        sw = self._sw()
        sw.start()
        self.t[0] += 10
        sw.lap()
        sw.stop()
        sw.start()                       # fresh — no leftover laps
        self.t[0] += 5
        assert sw.lap() == (5, 5)


class TestAge:
    BASE = dt.date(2026, 7, 21)

    def test_bare_year(self):
        out = age_from("main 1995 me paida hua", self.BASE)
        assert "31 saal" in out

    def test_full_date(self):
        out = age_from("15 august 2000 ko born hua", self.BASE)
        assert "25 saal" in out and "born 15 August 2000" in out

    def test_numeric_date(self):
        out = age_from("01/08/2000", self.BASE)
        assert "25 saal" in out

    def test_birthday_today(self):
        out = age_from("born 21 july 2000", self.BASE)
        assert "happy birthday" in out.lower()

    def test_future_bare_year_none(self):
        # a bare year in the future can't be a birthdate → graceful None
        assert age_from("2050 me paida hua", self.BASE) is None

    def test_future_full_date_flagged(self):
        out = age_from("15 august 2030 ko born hua", self.BASE)
        assert out is not None and "future" in out

    def test_unparseable_none(self):
        assert age_from("kuch nahi", self.BASE) is None

    def test_skill_prompt(self):
        from skills.datetime_skill import age_calc
        assert "birthdate" in age_calc({"raw_text": "umar batao"})


class TestStopwatchSkills:
    def test_full_flow(self, monkeypatch):
        import core.stopwatch as sw_mod
        t = [500.0]
        fresh = sw_mod.Stopwatch(now_fn=lambda: t[0])
        monkeypatch.setattr(sw_mod, "get_stopwatch", lambda: fresh)
        from skills.stopwatch_skill import (stopwatch_start, stopwatch_check,
                                           stopwatch_stop)
        assert "chalu" in stopwatch_start({})
        t[0] += 42
        assert "42s" in stopwatch_check({})
        assert "total" in stopwatch_stop({})
        assert "chal hi nahi" in stopwatch_stop({})   # already stopped
