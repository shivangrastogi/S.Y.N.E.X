"""AQI category + modulo (offline)."""

from __future__ import annotations

from core.misc_calc import aqi_category
from core.number_props import modulo_calc


class TestAqi:
    def test_good(self):
        assert "Good" in aqi_category("AQI 45")

    def test_moderate(self):
        assert "Moderate" in aqi_category("aqi 180 delhi")

    def test_very_poor(self):
        assert "Very Poor" in aqi_category("air quality index 350")

    def test_severe(self):
        assert "Severe" in aqi_category("aqi 480")

    def test_prompt(self):
        assert "AQI number batao" in aqi_category("air quality batao")


class TestModulo:
    def test_basic(self):
        out = modulo_calc("17 mod 5")
        assert "17 mod 5 = 2" in out and "Quotient = 3" in out

    def test_percent(self):
        assert "100 mod 7 = 2" in modulo_calc("100 % 7")

    def test_words(self):
        assert "23 mod 4 = 3" in modulo_calc("remainder of 23 by 4")

    def test_prompt(self):
        assert "Do numbers do" in modulo_calc("mod batao")


class TestSkills:
    def test_aqi_skill(self):
        from skills.misc_calc_skill import aqi_category as a
        assert "AQI" in a({"raw_text": "aqi 180 kaunsi category"})

    def test_modulo_skill(self):
        from skills.number_props_skill import modulo_calc as m
        assert "mod" in m({"raw_text": "17 mod 5 kitna hota hai"})
