"""Travel-time solver + stacked-discount (pure math, offline)."""

from __future__ import annotations

from core.misc_calc import travel_time
from core.finance_math import discount_stack


class TestTravel:
    def test_time_from_dist_speed(self):
        assert "2 hr" in travel_time("120 km 60 kmph kitni der")

    def test_speed_from_dist_time(self):
        assert "60.0 km/h" in travel_time("300 km 5 hours speed")

    def test_dist_from_speed_time(self):
        assert "200 km" in travel_time("80 kmph 2.5 hours distance")

    def test_minutes(self):
        assert "120.0 km/h" in travel_time("90 km 45 min speed")

    def test_needs_two(self):
        assert "Do cheezein" in travel_time("sirf 100 km")


class TestDiscountStack:
    def test_effective_and_price(self):
        out = discount_stack("1000 pe 20% phir 10% off")
        assert "28.00%" in out and "720" in out

    def test_no_price_note(self):
        out = discount_stack("20% then 10% discount")
        assert "28.00%" in out and "galat" in out

    def test_triple(self):
        out = discount_stack("50% and 30% and 10% off on 2000")
        assert "68.50%" in out and "630" in out

    def test_needs_two(self):
        assert "Do ya zyada" in discount_stack("sirf 20% off")


class TestSkills:
    def test_travel_skill(self):
        from skills.misc_calc_skill import travel_time as t
        assert "hr" in t({"raw_text": "120 km 60 kmph kitni der lagegi"})

    def test_discount_skill(self):
        from skills.finance_skill import discount_stack as d
        assert "effective" in d({"raw_text": "1000 pe 20% phir 10% off"})
