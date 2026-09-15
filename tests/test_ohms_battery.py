"""Ohm's law + battery life (pure math, offline)."""

from __future__ import annotations

from core.misc_calc import ohms_law, battery_life


class TestOhmsLaw:
    def test_resistance_from_v_i(self):
        out = ohms_law("5 volt 2 amp")
        assert "Resistance = 2.50 ohm" in out and "Power=10W" in out

    def test_current_from_v_r(self):
        assert "Current = 3 A" in ohms_law("12 volt 4 ohm")

    def test_voltage_from_i_r(self):
        assert "Voltage = 20 V" in ohms_law("2 amp 10 ohm")

    def test_milliamp_conversion(self):
        # 500 mA = 0.5 A, 10 ohm -> V = 5
        assert "Voltage = 5 V" in ohms_law("500 ma 10 ohm")

    def test_needs_two(self):
        assert "Do values" in ohms_law("5 volt")


class TestBatteryLife:
    def test_basic(self):
        # 3000/500 = 6 hr
        assert "6 hr" in battery_life("3000 mAh 500 mA")

    def test_longer(self):
        assert "20 hr" in battery_life("5000 mah 250 ma draw")

    def test_prompt(self):
        assert "capacity" in battery_life("battery kitni")


class TestSkills:
    def test_ohms_skill(self):
        from skills.misc_calc_skill import ohms_law as o
        assert "Power" in o({"raw_text": "12 volt 4 ohm current"})

    def test_battery_skill(self):
        from skills.misc_calc_skill import battery_life as b
        assert "hr" in b({"raw_text": "3000 mah battery 500 ma draw kitne ghante"})
