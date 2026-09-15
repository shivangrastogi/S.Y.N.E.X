"""Next birthday + Luhn checksum (offline)."""

from __future__ import annotations

import datetime as dt

from core.fun_calc import next_birthday
from core.dev_format import luhn_check


_TODAY = dt.date(2026, 7, 20)


class TestNextBirthday:
    def test_future_with_age(self):
        out = next_birthday("15 august 1998", _TODAY)
        assert "26 din" in out and "28 saal" in out

    def test_rolls_next_year(self):
        out = next_birthday("10/07/2000", _TODAY)
        assert "2027" in out

    def test_today(self):
        assert "Aaj hi" in next_birthday("20 july", _TODAY)

    def test_feb29_fallback(self):
        # 2027 is non-leap -> celebrate 28 Feb
        assert "28 February" in next_birthday("29/02/2000", _TODAY)

    def test_prompt(self):
        assert "janam-tareekh" in next_birthday("birthday kab", _TODAY)


class TestLuhn:
    def test_valid(self):
        assert "PASS" in luhn_check("79927398713 luhn valid")

    def test_invalid(self):
        assert "FAIL" in luhn_check("79927398710")

    def test_valid_test_card(self):
        assert "PASS" in luhn_check("4539 1488 0343 6467")

    def test_prompt(self):
        assert "Number do" in luhn_check("luhn check")


class TestSkills:
    def test_birthday_skill(self):
        from skills.fun_calc_skill import next_birthday as n
        assert isinstance(n({"raw_text": "meri birthday me kitne din baaki"}), str)

    def test_luhn_skill(self):
        from skills.dev_format_skill import luhn_check as l
        assert "PASS" in l({"raw_text": "79927398713 luhn valid hai kya"})
