"""Overtime pay + dew point (pure math, offline)."""

from __future__ import annotations

from core.finance_math import overtime_pay
from core.misc_calc import dew_point


class TestOvertime:
    def test_1_5x(self):
        # 8 * 200 * 1.5 = 2400
        assert "2,400" in overtime_pay("8 hours 200 per hour 1.5x overtime")

    def test_double(self):
        # 5 * 300 * 2 = 3000
        assert "3,000" in overtime_pay("5 ghante 300 rupee per hour double")

    def test_default_multiplier(self):
        # 10 * 150 * 1.5 = 2250
        assert "2,250" in overtime_pay("10 hours 150 hourly")

    def test_prompt(self):
        assert "Overtime hours" in overtime_pay("overtime batao")


class TestDewPoint:
    def test_typical(self):
        # 30C 70% -> ~23.9C
        out = dew_point("30 degree 70% humidity")
        assert "23.9" in out

    def test_comfortable(self):
        assert "comfortable" in dew_point("25 celsius humidity 50")

    def test_humidity_after_keyword(self):
        # regression: 'humidity 50' must not grab temp
        assert "50% humidity" in dew_point("temp 25 humidity 50")

    def test_prompt(self):
        assert "Temperature aur humidity" in dew_point("mausam kaisa")


class TestSkills:
    def test_overtime_skill(self):
        from skills.finance_skill import overtime_pay as o
        assert "overtime pay" in o({"raw_text": "8 hours 200 per hour overtime"})

    def test_dew_skill(self):
        from skills.misc_calc_skill import dew_point as d
        assert "dew point" in d({"raw_text": "30 degree 70% humidity dew point"})
