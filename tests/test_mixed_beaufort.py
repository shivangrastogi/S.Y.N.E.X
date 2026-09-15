"""Mixed number + Beaufort scale (offline)."""

from __future__ import annotations

from core.fractions_calc import mixed_number
from core.misc_calc import beaufort_scale


class TestMixedNumber:
    def test_improper_to_mixed(self):
        assert "7/3 = 2 1/3" in mixed_number("7/3 as mixed")

    def test_mixed_to_improper(self):
        assert "2 1/3 = 7/3" in mixed_number("2 1/3 as improper")

    def test_whole(self):
        assert "= 2 (whole number)" in mixed_number("10/5 as mixed")

    def test_prompt(self):
        assert "Fraction do" in mixed_number("mixed batao")


class TestBeaufort:
    def test_strong_breeze(self):
        assert "Beaufort 6" in beaufort_scale("45 kmph wind")

    def test_knots(self):
        assert "Beaufort 5" in beaufort_scale("20 knots")

    def test_hurricane(self):
        assert "Beaufort 12" in beaufort_scale("130 kmph storm")

    def test_light_air(self):
        assert "Beaufort 1" in beaufort_scale("2 kmph")

    def test_prompt(self):
        assert "Wind speed do" in beaufort_scale("hawa kaisi")


class TestSkills:
    def test_mixed_skill(self):
        from skills.fractions_skill import mixed_number as m
        assert "2 1/3" in m({"raw_text": "7/3 ko mixed number me badlo"})

    def test_beaufort_skill(self):
        from skills.misc_calc_skill import beaufort_scale as b
        assert "Beaufort" in b({"raw_text": "45 kmph wind kaunsa beaufort"})
