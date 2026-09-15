"""Wind chill + ISO week number (pure math, offline)."""

from __future__ import annotations

import datetime as dt

from core.misc_calc import wind_chill
from core.fun_calc import week_number


class TestWindChill:
    def test_typical(self):
        # 5C 30km/h -> ~0.1C
        out = wind_chill("5 degree 30 kmph wind")
        assert "0.1" in out and "feels like" in out

    def test_negative_temp(self):
        assert "-12" in wind_chill("-5 degree 25 kmph")

    def test_out_of_range(self):
        assert "matter karta" in wind_chill("20 degree 30 kmph")

    def test_prompt(self):
        assert "Temperature aur wind" in wind_chill("thand kaisi hai")


class TestWeekNumber:
    _TODAY = dt.date(2026, 7, 20)

    def test_today(self):
        out = week_number("aaj kaunsa week", self._TODAY)
        assert "week 30" in out and "201/365" in out

    def test_explicit_date(self):
        out = week_number("15/08/2026 week number", self._TODAY)
        assert "week 33" in out

    def test_month_name(self):
        assert "week 1" in week_number("1 january 2026 week", self._TODAY)

    def test_year_end(self):
        assert "365/365" in week_number("31 december 2026", self._TODAY)


class TestSkills:
    def test_wind_skill(self):
        from skills.misc_calc_skill import wind_chill as w
        assert "feels" in w({"raw_text": "5 degree 30 kmph wind feels like"})

    def test_week_skill(self):
        from skills.fun_calc_skill import week_number as wk
        assert "week" in wk({"raw_text": "15 august 2026 ka week number"})
