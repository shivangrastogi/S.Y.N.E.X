"""Leap-year + days-in-month (pure math, offline)."""

from __future__ import annotations

from core.calendar_facts import is_leap, leap_year, days_in_month


class TestLeap:
    def test_century_rules(self):
        assert is_leap(2000) and not is_leap(1900) and not is_leap(2100)
        assert is_leap(2024) and not is_leap(2023)

    def test_leap_message(self):
        out = leap_year("2024 leap year hai kya")
        assert "Haan" in out and "2028" in out

    def test_non_leap_message(self):
        out = leap_year("is 2100 a leap year")
        assert "Nahi" in out and "2104" in out

    def test_no_year_none(self):
        assert leap_year("leap year hai kya") is None


class TestDaysInMonth:
    def test_fixed_month(self):
        assert "31 din" in days_in_month("march me kitne din")
        assert "30 din" in days_in_month("april me kitne days")

    def test_feb_leap(self):
        assert "29 din" in days_in_month("february 2024 me kitne din")

    def test_feb_nonleap(self):
        assert "28 din" in days_in_month("how many days in february 2023")

    def test_feb_no_year(self):
        out = days_in_month("february me kitne din")
        assert "28" in out and "29" in out

    def test_no_month_none(self):
        assert days_in_month("kitne din hote hain") is None


class TestSkills:
    def test_leap_skill(self):
        from skills.calendar_word_skill import leap_year_check
        assert "Haan" in leap_year_check({"raw_text": "2024 leap year hai kya"})

    def test_leap_skill_prompt(self):
        from skills.calendar_word_skill import leap_year_check
        assert "Kaunsa saal" in leap_year_check({"raw_text": "leap year hai kya"})

    def test_days_skill(self):
        from skills.calendar_word_skill import days_in_month
        assert "31" in days_in_month({"raw_text": "march me kitne din"})
