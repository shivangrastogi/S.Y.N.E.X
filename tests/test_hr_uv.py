"""Heart-rate zones + UV index (offline)."""

from __future__ import annotations

from core.health_calc import heart_rate_zones
from core.misc_calc import uv_index


class TestHeartRate:
    def test_max_hr(self):
        assert "max heart rate ~190" in heart_rate_zones("age 30 heart rate zones")

    def test_zones(self):
        assert "aerobic 133-152" in heart_rate_zones("age 30")

    def test_other_age(self):
        assert "~195" in heart_rate_zones("age 25 heart rate")

    def test_prompt(self):
        assert "Apni age batao" in heart_rate_zones("heart rate batao")


class TestUv:
    def test_low(self):
        assert "Low" in uv_index("UV 2")

    def test_very_high(self):
        assert "Very High" in uv_index("uv index 8")

    def test_extreme(self):
        assert "Extreme" in uv_index("uv 11 today")

    def test_prompt(self):
        assert "UV index number" in uv_index("uv batao")


class TestSkills:
    def test_hr_skill(self):
        from skills.health_split_skill import heart_rate_zones as h
        assert "heart rate" in h({"raw_text": "age 30 heart rate zones"})

    def test_uv_skill(self):
        from skills.misc_calc_skill import uv_index as u
        assert "UV index" in u({"raw_text": "uv index 8 kitna khatarnak"})
