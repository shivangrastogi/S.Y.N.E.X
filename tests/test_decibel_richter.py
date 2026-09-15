"""Decibel loudness + Richter magnitude (offline reference)."""

from __future__ import annotations

from core.misc_calc import decibel_scale, richter_scale


class TestDecibel:
    def test_loud_with_exposure(self):
        out = decibel_scale("85 dB")
        assert "loud" in out and "8" in out

    def test_moderate(self):
        assert "moderate" in decibel_scale("60 decibel")

    def test_100_db_15_min(self):
        # NIOSH: 100 dB -> 15 min safe
        assert "15 min" in decibel_scale("100 db")

    def test_prompt(self):
        assert "dB level batao" in decibel_scale("sound batao")


class TestRichter:
    def test_strong(self):
        assert "strong" in richter_scale("richter 6.5")

    def test_minor(self):
        assert "minor" in richter_scale("magnitude 3")

    def test_great(self):
        assert "great" in richter_scale("8.2 earthquake")

    def test_prompt(self):
        assert "Magnitude batao" in richter_scale("earthquake batao")


class TestSkills:
    def test_db_skill(self):
        from skills.misc_calc_skill import decibel_scale as d
        assert "dB" in d({"raw_text": "85 db kitna loud hota hai"})

    def test_richter_skill(self):
        from skills.misc_calc_skill import richter_scale as r
        assert "Magnitude" in r({"raw_text": "richter 6.5 kitna khatarnak"})
