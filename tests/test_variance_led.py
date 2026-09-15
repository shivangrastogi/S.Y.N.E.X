"""Variance/std + LED resistor (pure math, offline)."""

from __future__ import annotations

from core.number_props import variance_std
from core.misc_calc import led_resistor


class TestVariance:
    def test_textbook(self):
        # 2,4,4,4,5,5,7,9 -> mean 5, pop var 4, std 2
        out = variance_std("2 4 4 4 5 5 7 9 std deviation")
        assert "mean 5" in out and "std 2" in out

    def test_sample_vs_population(self):
        out = variance_std("variance of 4 8 15 16 23 42")
        assert "population variance" in out and "sample variance" in out

    def test_prompt(self):
        assert "2 numbers" in variance_std("variance batao")


class TestLedResistor:
    def test_basic(self):
        out = led_resistor("5V supply 2V LED 20mA")
        assert "150 ohm" in out and "60 mW" in out

    def test_nearest_standard(self):
        # (12-3)/0.025 = 360 -> nearest E12 330
        out = led_resistor("12 volt supply led 3 volt 25 ma")
        assert "360 ohm" in out and "330 ohm" in out

    def test_prompt(self):
        assert "Supply voltage" in led_resistor("led batao")


class TestSkills:
    def test_variance_skill(self):
        from skills.number_props_skill import variance_std as v
        assert "variance" in v({"raw_text": "variance of 4 8 15 16 23"})

    def test_led_skill(self):
        from skills.misc_calc_skill import led_resistor as l
        assert "ohm" in l({"raw_text": "5V supply 2V LED 20mA resistor"})
