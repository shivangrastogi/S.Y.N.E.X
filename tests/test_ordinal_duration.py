"""Ordinal number + duration humanize (pure math, offline)."""

from __future__ import annotations

from core.fun_calc import ordinal_number, duration_humanize


class TestOrdinal:
    def test_basic_suffixes(self):
        assert "1st" in ordinal_number("1 ka ordinal")
        assert "2nd" in ordinal_number("2 ka ordinal")
        assert "3rd" in ordinal_number("3 ka ordinal")
        assert "4th" in ordinal_number("4 ka ordinal")

    def test_teens_are_th(self):
        assert "11th" in ordinal_number("11 ordinal")
        assert "13th" in ordinal_number("13 ordinal")

    def test_twenties(self):
        assert "21st" in ordinal_number("21 ordinal")
        assert "23rd" in ordinal_number("23 ka ordinal")

    def test_hundreds(self):
        assert "101st" in ordinal_number("101 ordinal")
        assert "113th" in ordinal_number("113 ordinal")

    def test_prompt(self):
        assert "Kaunsa number" in ordinal_number("ordinal batao")


class TestDuration:
    def test_seconds(self):
        assert "2 hr 30 min" in duration_humanize("9000 seconds")

    def test_minutes(self):
        assert "2 hr 30 min" in duration_humanize("150 minutes")

    def test_hours_to_days(self):
        assert "3 days 18 hr" in duration_humanize("90 hours")

    def test_fractional_days(self):
        assert "2 days 12 hr" in duration_humanize("2.5 days")

    def test_prompt(self):
        assert "Number aur unit" in duration_humanize("kitna time")


class TestSkills:
    def test_ordinal_skill(self):
        from skills.fun_calc_skill import ordinal_number as o
        assert "23rd" in o({"raw_text": "23 ka ordinal kya hai"})

    def test_duration_skill(self):
        from skills.fun_calc_skill import duration_humanize as d
        assert "hr" in d({"raw_text": "9000 seconds kitne ghante"})
