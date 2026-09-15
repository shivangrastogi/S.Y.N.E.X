"""Hex codec + reading-time (pure stdlib, offline)."""

from __future__ import annotations

from core.codec_tools import hex_convert, reading_time


class TestHex:
    def test_encode(self):
        assert b"hello".hex() in hex_convert("hex encode karo hello")

    def test_decode_roundtrip(self):
        assert "hello" in hex_convert("hex decode karo 68656c6c6f")

    def test_invalid_decode(self):
        assert "valid hex nahi" in hex_convert("hex decode karo zzzz")


class TestReadingTime:
    def test_estimate(self):
        out = reading_time("reading time batao " + "word " * 250)
        assert "250 words" in out and "min" in out

    def test_too_short_prompts(self):
        assert "paste" in reading_time("padhne me kitna time hi")


class TestSkills:
    def test_hex_skill(self):
        from skills.codec_tools_skill import hex_convert as h
        assert "Hex" in h({"raw_text": "hex encode karo hi"})

    def test_reading_skill(self):
        from skills.codec_tools_skill import reading_time as r
        out = r({"raw_text": "reading time batao " + "x " * 60})
        assert "words" in out
