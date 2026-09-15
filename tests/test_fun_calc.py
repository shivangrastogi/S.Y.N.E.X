"""Weekend countdown + Scrabble score (pure math, offline)."""

from __future__ import annotations

import datetime as dt

from core.fun_calc import weekend_countdown, scrabble_score


class TestWeekend:
    def test_weekday(self):
        # Monday 2026-07-20 -> 5 days to Saturday
        out = weekend_countdown("weekend me kitne din", dt.date(2026, 7, 20))
        assert "5 din" in out and "Monday" in out

    def test_friday_one_day(self):
        assert "1 din" in weekend_countdown("weekend", dt.date(2026, 7, 24))

    def test_saturday(self):
        assert "shuru" in weekend_countdown("weekend", dt.date(2026, 7, 25))

    def test_sunday(self):
        assert "aakhri din" in weekend_countdown("weekend", dt.date(2026, 7, 26))


class TestScrabble:
    def test_quiz(self):
        assert "22" in scrabble_score("scrabble score of quiz")

    def test_quartz(self):
        assert "24" in scrabble_score("QUARTZ ka scrabble score")

    def test_hello(self):
        assert "8" in scrabble_score("hello ki value")

    def test_no_word_prompt(self):
        assert "Kaunsa word" in scrabble_score("scrabble score nikaalo")


class TestSkills:
    def test_weekend_skill(self):
        from skills.fun_calc_skill import weekend_countdown as w
        assert isinstance(w({"raw_text": "weekend me kitne din"}), str)

    def test_scrabble_skill(self):
        from skills.fun_calc_skill import scrabble_score as s
        assert "22" in s({"raw_text": "scrabble score of quiz"})
