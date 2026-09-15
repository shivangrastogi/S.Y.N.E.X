"""Fractions — convert + arithmetic (pure math, offline)."""

from __future__ import annotations

from core.fractions_calc import fraction_convert, fraction_math


class TestConvert:
    def test_decimal_to_fraction(self):
        assert "3/4" in fraction_convert("0.75 as fraction")

    def test_fraction_to_decimal(self):
        assert "0.75" in fraction_convert("3/4 as decimal")

    def test_percent_to_fraction(self):
        assert "1/4" in fraction_convert("25%")

    def test_simplify(self):
        assert "3/4" in fraction_convert("6/8")

    def test_prompt(self):
        assert "Number ya fraction" in fraction_convert("fraction batao")


class TestMath:
    def test_add(self):
        assert "5/6" in fraction_math("1/2 + 1/3")

    def test_subtract(self):
        assert "1/2" in fraction_math("3/4 - 1/4")

    def test_multiply(self):
        assert "1/2" in fraction_math("2/3 * 3/4")

    def test_divide(self):
        assert fraction_math("1/2 / 1/4").startswith("1/2 / 1/4 = 2 ")

    def test_divide_words(self):
        assert "= 2 " in fraction_math("1/2 divided by 1/4")

    def test_prompt(self):
        assert "Do fractions aur operator" in fraction_math("fraction batao")


class TestSkills:
    def test_convert_skill(self):
        from skills.fractions_skill import fraction_convert as c
        assert "3/4" in c({"raw_text": "0.75 ko fraction me badlo"})

    def test_math_skill(self):
        from skills.fractions_skill import fraction_math as m
        assert "5/6" in m({"raw_text": "1/2 + 1/3 kitna hota hai"})
