"""Fixed-date holiday countdown + Chinese zodiac (pure math, offline)."""

from __future__ import annotations

import datetime as dt

from core.festival_zodiac import festival_countdown, chinese_zodiac


_TODAY = dt.date(2026, 7, 20)


class TestFestival:
    def test_future_this_year(self):
        out = festival_countdown("independence day", _TODAY)
        assert "26 din" in out and "15 August 2026" in out

    def test_rolls_to_next_year(self):
        # republic day (Jan 26) already passed in July -> next year
        out = festival_countdown("republic day countdown", _TODAY)
        assert "2027" in out

    def test_today(self):
        assert "Aaj hi" in festival_countdown("christmas", dt.date(2026, 12, 25))

    def test_unknown_prompt(self):
        assert "Fixed-date festival" in festival_countdown("diwali kab hai", _TODAY)


class TestChinese:
    def test_known_years(self):
        assert "Tiger" in chinese_zodiac("1998 ka chinese zodiac")
        assert "Rat" in chinese_zodiac("2020 chinese sign")
        assert "Dragon" in chinese_zodiac("mera saal 2000")
        assert "Horse" in chinese_zodiac("2026")

    def test_prompt(self):
        assert "Janam saal" in chinese_zodiac("chinese zodiac batao")


class TestSkills:
    def test_festival_skill(self):
        from skills.festival_zodiac_skill import festival_countdown as f
        assert "din" in f({"raw_text": "independence day me kitne din"})

    def test_chinese_skill(self):
        from skills.festival_zodiac_skill import chinese_zodiac as c
        assert "Year of" in c({"raw_text": "1998 ka chinese zodiac"})
