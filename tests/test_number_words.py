"""Number → words — Indian + international numbering, edge cases."""

from __future__ import annotations

import pytest

from core.number_words import number_to_words, parse_and_spell


class TestIndian:
    @pytest.mark.parametrize("n,expect", [
        ("0", "zero"),
        ("7", "seven"),
        ("42", "forty-two"),
        ("100", "one hundred"),
        ("1234", "one thousand two hundred thirty-four"),
        ("150000", "one lakh fifty thousand"),
        ("1234567", "twelve lakh thirty-four thousand five hundred sixty-seven"),
        ("10000000", "one crore"),
        ("70000000", "seven crore"),
    ])
    def test_indian(self, n, expect):
        assert number_to_words(n, "indian") == expect


class TestInternational:
    @pytest.mark.parametrize("n,expect", [
        ("1234567", "one million two hundred thirty-four thousand "
                    "five hundred sixty-seven"),
        ("1000000000", "one billion"),
        ("5000000", "five million"),
    ])
    def test_international(self, n, expect):
        assert number_to_words(n, "international") == expect


class TestEdgeCases:
    def test_negative(self):
        assert number_to_words("-45").startswith("minus")

    def test_decimal(self):
        assert number_to_words("1500000.5").endswith("point five")

    def test_commas_stripped(self):
        assert number_to_words("12,34,567") == number_to_words("1234567")

    def test_too_big_none(self):
        assert number_to_words("99999999999999") is None

    def test_non_numeric_none(self):
        assert number_to_words("abc") is None
        assert number_to_words("12.3.4") is None


class TestParseAndSpell:
    def test_indian_default(self):
        out = parse_and_spell("1234567 ko words me batao")
        assert "twelve lakh" in out

    def test_international_hint(self):
        out = parse_and_spell("5000000 international words me")
        assert "five million" in out

    def test_no_number(self):
        assert parse_and_spell("koi number nahi") is None

    def test_skill_prompt(self):
        from skills.number_words_skill import number_to_words as skill
        assert "Kaunsa number" in skill({"raw_text": "number spell karo"})
