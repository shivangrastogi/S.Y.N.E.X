"""Inflation adjust + Rule of 72 (pure finance math, offline)."""

from __future__ import annotations

from core.finance_math import inflation_adjust, rule_of_72


class TestInflation:
    def test_future_and_worth(self):
        # 1 lakh, 6%, 10y -> future ~1,79,085 ; worth today ~55,839
        out = inflation_adjust("1 lakh 10 saal 6% inflation")
        assert "179,084" in out or "179,085" in out
        assert "55,839" in out

    def test_default_rate(self):
        out = inflation_adjust("500000 5 saal baad mehngai")
        assert "maana 6%" in out

    def test_prompt(self):
        assert "Amount aur saal" in inflation_adjust("mehngai kitni")


class TestRule72:
    def test_years_from_rate(self):
        assert "9.0 saal" in rule_of_72("8% pe paisa kab double hoga")

    def test_rate_from_years(self):
        assert "14.4%" in rule_of_72("5 saal me double kaunsa rate")

    def test_prompt(self):
        assert "Rate ya time" in rule_of_72("rule of 72 batao")


class TestSkills:
    def test_inflation_skill(self):
        from skills.finance_skill import inflation_adjust as i
        assert "saal baad" in i({"raw_text": "1 lakh 10 saal baad kitne"})

    def test_rule72_skill(self):
        from skills.finance_skill import rule_of_72 as r
        assert "double" in r({"raw_text": "8% pe paisa kab double hoga"})
