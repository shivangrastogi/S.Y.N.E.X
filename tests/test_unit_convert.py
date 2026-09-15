"""Offline unit converter — accuracy + dimension safety + parsing."""

from __future__ import annotations

import math

import pytest

from core.unit_convert import convert, parse_and_convert


class TestAccuracy:
    @pytest.mark.parametrize("v,src,dst,expect", [
        (10, "km", "mile", 6.21371),
        (1, "mile", "km", 1.609344),
        (100, "celsius", "fahrenheit", 212.0),
        (32, "fahrenheit", "celsius", 0.0),
        (0, "celsius", "kelvin", 273.15),
        (1, "kg", "pound", 2.20462),
        (1, "pound", "g", 453.59237),
        (1, "gb", "mb", 1024.0),
        (1, "gallon", "litre", 3.785411784),
        (12, "inch", "cm", 30.48),
        (60, "kmph", "mph", 37.2823),
        (1, "kg", "g", 1000.0),
    ])
    def test_convert(self, v, src, dst, expect):
        assert math.isclose(convert(v, src, dst), expect, rel_tol=1e-4)


class TestDimensionSafety:
    def test_length_to_weight_none(self):
        assert convert(5, "km", "kg") is None

    def test_temp_mixed_with_linear_none(self):
        assert convert(30, "celsius", "km") is None
        assert convert(30, "km", "celsius") is None

    def test_unknown_unit_none(self):
        assert convert(1, "km", "furlong") is None
        assert convert(1, "wibble", "m") is None


class TestParsing:
    @pytest.mark.parametrize("text,contains", [
        ("10 km me kitne mile", "6.214 mile"),
        ("5 kg to pound", "11.02 pound"),
        ("100 f in c", "37.78 c"),
        ("2 mile kitne km hote hain", "3.219 km"),
        ("10 gb me kitne mb", "10240 mb"),
    ])
    def test_parse_forms(self, text, contains):
        out = parse_and_convert(text)
        assert out and contains in out

    def test_aliases(self):
        assert parse_and_convert("5 kilo me kitne pound") is not None
        assert parse_and_convert("2 metre in feet") is not None

    def test_dimension_mismatch_message(self):
        out = parse_and_convert("5 km me kitne kg")
        assert "aapas mein convert nahi" in out

    def test_unparseable_none(self):
        assert parse_and_convert("bakwaas hai ye") is None
        assert parse_and_convert("") is None

    def test_integer_formatting(self):
        # exact integers shouldn't show decimals
        assert "1000 g" in parse_and_convert("1 kg me kitne g")

    def test_skill_wrapper_prompts_on_fail(self):
        from skills.unit_convert_skill import unit_convert
        assert "convert karun" in unit_convert({"raw_text": "convert karo"})
