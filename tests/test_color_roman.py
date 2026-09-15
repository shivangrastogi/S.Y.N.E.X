"""Color + Roman numeral converters (offline)."""

from __future__ import annotations

import pytest

from core.color_roman import (convert_color, convert_roman,
                              to_roman, from_roman)


class TestColor:
    @pytest.mark.parametrize("text,contains", [
        ("ff5733 ka rgb batao", "rgb(255, 87, 51)"),
        ("#ff5733", "rgb(255, 87, 51)"),
        ("255 87 51 ka hex", "#FF5733"),
        ("red ka hex batao", "#FF0000"),
        ("0000ff", "blue"),
        ("fff", "#FFFFFF"),
        ("008080", "teal"),
        ("255,0,100 ka hex", "#FF0064"),
    ])
    def test_conversions(self, text, contains):
        out = convert_color(text)
        assert out and contains in out

    def test_shorthand_expands(self):
        assert "#FFFFFF" in convert_color("fff")

    def test_clamps_out_of_range(self):
        out = convert_color("300 0 0 ka hex")
        assert "#FF0000" in out         # 300 clamped to 255

    def test_none_when_no_color(self):
        assert convert_color("kuch bhi") is None


class TestRoman:
    @pytest.mark.parametrize("n,rom", [
        (4, "IV"), (9, "IX"), (49, "XLIX"), (2024, "MMXXIV"),
        (3999, "MMMCMXCIX"), (1, "I"),
    ])
    def test_to_roman(self, n, rom):
        assert to_roman(n) == rom

    def test_to_roman_out_of_range(self):
        assert to_roman(0) is None and to_roman(4000) is None

    @pytest.mark.parametrize("rom,n", [
        ("IV", 4), ("MMXXIV", 2024), ("XLIX", 49), ("IX", 9),
    ])
    def test_from_roman(self, rom, n):
        assert from_roman(rom) == n

    def test_from_roman_rejects_malformed(self):
        assert from_roman("IIII") is None
        assert from_roman("VX") is None
        assert from_roman("ABC") is None
        assert from_roman("") is None

    def test_roundtrip(self):
        for n in (1, 44, 99, 500, 1994, 3888):
            assert from_roman(to_roman(n)) == n


class TestConvertRoman:
    def test_number_to_roman(self):
        assert "MMXXIV" in convert_roman("2024 ko roman me")

    def test_roman_to_number(self):
        assert "= 2024" in convert_roman("MMXXIV kya number hai")

    def test_out_of_range_message(self):
        assert "1 se 3999" in convert_roman("5000 roman me")

    def test_none_when_empty(self):
        assert convert_roman("hello") is None


class TestSkills:
    def test_color_skill_prompt(self):
        from skills.color_roman_skill import color_convert
        assert "Color do" in color_convert({"raw_text": "color convert karo"})

    def test_roman_skill(self):
        from skills.color_roman_skill import roman_convert
        assert "MMXXIV" in roman_convert({"raw_text": "2024 ko roman me likho"})
