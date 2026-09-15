"""Reverse GST + ASCII value (offline)."""

from __future__ import annotations

from core.finance_math import gst_inclusive
from core.codec_tools import ascii_value


class TestGstInclusive:
    def test_extract(self):
        # 1180 @ 18% -> base 1000, gst 180
        out = gst_inclusive("1180 me se 18% gst nikaalo")
        assert "base price 1,000" in out and "GST 180" in out

    def test_cgst_sgst_split(self):
        assert "CGST 90" in gst_inclusive("1180 me se 18% gst")

    def test_prompt(self):
        assert "Total (GST included)" in gst_inclusive("gst nikaalo")


class TestAscii:
    def test_char_to_code(self):
        assert "ASCII/Unicode 65" in ascii_value("A ka ascii value")

    def test_code_to_char(self):
        assert "'A'" in ascii_value("65 ka character kya hai")

    def test_word_codes(self):
        out = ascii_value("Hi ka ascii")
        assert "H=72" in out and "i=105" in out

    def test_prompt(self):
        assert "Kaunsa character" in ascii_value("ascii nikaalo")


class TestSkills:
    def test_gst_skill(self):
        from skills.finance_skill import gst_inclusive as g
        assert "base price" in g({"raw_text": "1180 me se 18% gst nikaalo"})

    def test_ascii_skill(self):
        from skills.codec_tools_skill import ascii_value as a
        assert "65" in a({"raw_text": "A ka ascii value kya hai"})
