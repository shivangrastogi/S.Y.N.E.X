"""Base converter + NATO phonetic (offline dev helpers)."""

from __future__ import annotations

import pytest

from core.dev_tools import convert_base, phonetic


class TestBaseConvert:
    @pytest.mark.parametrize("text,contains", [
        ("255 ko hex me", "FF"),
        ("255 ko binary me", "11111111"),
        ("ff hex to decimal", "255"),
        ("101 binary to decimal", "5"),
        ("abc hex to decimal", "2748"),
        ("1010 binary to hex", "A"),
        ("100 decimal to octal", "144"),
        ("0xff decimal me", "255"),
        ("0b101 ko decimal me", "5"),
        ("64 ko octal me", "100"),
    ])
    def test_conversions(self, text, contains):
        out = convert_base(text)
        assert out and contains in out

    def test_target_named(self):
        assert "(hex)" in convert_base("255 to hex")

    def test_no_target_none(self):
        assert convert_base("255 kya hai") is None

    def test_no_value_none(self):
        assert convert_base("hex me convert karo") is None

    def test_hex_guessed_when_letters(self):
        # "abc to decimal" — no explicit source, letters ⇒ hex
        assert "2748" in convert_base("abc to decimal")


class TestPhonetic:
    def test_word(self):
        assert phonetic("delta") == "Delta - Echo - Lima - Tango - Alpha"

    def test_digits_and_case(self):
        out = phonetic("aB3")
        assert out == "Alpha - BRAVO - Three"

    def test_symbols_passthrough(self):
        assert phonetic("x9!") == "X-ray - Nine - !"

    def test_space_marked(self):
        assert "(space)" in phonetic("a b")

    def test_empty_none(self):
        assert phonetic("") is None


class TestSkills:
    def test_base_skill_prompt(self):
        from skills.dev_tools_skill import base_convert
        assert "convert karun" in base_convert({"raw_text": "convert karo"})

    def test_phonetic_skill_strips_command(self):
        from skills.dev_tools_skill import phonetic_spell
        out = phonetic_spell({"raw_text": "phonetic me spell karo AB12"})
        assert out.startswith("ALPHA - BRAVO")

    def test_phonetic_skill_last_token_fallback(self):
        from skills.dev_tools_skill import phonetic_spell
        out = phonetic_spell({"raw_text": "delta ko phonetic me spell karo"})
        assert "Delta" in out


class TestTextStats:
    def test_counts(self):
        from core.text_stats import analyse
        out = analyse("Hello world. This is AERIS! Fully offline.")
        assert "7 words" in out and "3 sentence" in out

    def test_reading_time(self):
        from core.text_stats import analyse
        out = analyse("word " * 400)
        assert "min" in out

    def test_empty_none(self):
        from core.text_stats import analyse
        assert analyse("") is None and analyse("   ") is None
