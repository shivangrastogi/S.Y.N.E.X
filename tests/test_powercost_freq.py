"""Appliance power cost + frequency/wavelength (pure math, offline)."""

from __future__ import annotations

from core.finance_math import appliance_power_cost
from core.misc_calc import frequency_wavelength


class TestApplianceCost:
    def test_full(self):
        # 1500*8*30/1000 = 360 units, *8 = 2880
        out = appliance_power_cost("1500 watt 8 hours daily 30 days 8 rupee")
        assert "360 units" in out and "2,880" in out

    def test_kw(self):
        # 2kW = 2000W, 1hr, 30d = 60 units, *7 = 420
        out = appliance_power_cost("2 kw geyser 1 hour daily 30 days 7 rupee")
        assert "60 units" in out and "420" in out

    def test_no_rate(self):
        assert "Rate do" in appliance_power_cost("1000 watt 5 hours")

    def test_prompt(self):
        assert "Wattage aur daily hours" in appliance_power_cost("bill batao")


class TestFrequencyWavelength:
    def test_mhz_to_metres(self):
        assert "3 m" in frequency_wavelength("100 MHz wavelength")

    def test_ghz(self):
        assert "12.5 cm" in frequency_wavelength("2.4 GHz ka wavelength")

    def test_wavelength_to_freq(self):
        assert "MHz" in frequency_wavelength("3 m wavelength ki frequency")

    def test_nm_to_thz(self):
        assert "THz" in frequency_wavelength("500 nm light frequency")

    def test_prompt(self):
        assert "Frequency ya wavelength" in frequency_wavelength("wave batao")


class TestSkills:
    def test_power_skill(self):
        from skills.finance_skill import appliance_power_cost as a
        assert "units" in a({"raw_text": "1500 watt 8 hours daily kitna bill"})

    def test_freq_skill(self):
        from skills.misc_calc_skill import frequency_wavelength as f
        assert "wavelength" in f({"raw_text": "100 MHz ka wavelength kitna"})
