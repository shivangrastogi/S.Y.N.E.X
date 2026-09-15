"""Fuel/trip cost + water intake (pure math, offline)."""

from __future__ import annotations

from core.misc_calc import fuel_trip_cost, water_intake


class TestFuel:
    def test_full_cost(self):
        # 500/15 = 33.33 L, *100 = 3333.33
        out = fuel_trip_cost("500 km 15 kmpl 100 rupee petrol")
        assert "33.33 litre" in out and "3333.33" in out

    def test_mileage_keyword(self):
        out = fuel_trip_cost("300 km mileage 20 petrol 105")
        assert "15 litre" in out and "1575" in out

    def test_no_price_gives_litres(self):
        out = fuel_trip_cost("400 km 25 kmpl")
        assert "16 litre" in out and "price bhi do" in out

    def test_missing_data(self):
        assert "Distance, mileage" in fuel_trip_cost("kitna kharcha")


class TestWater:
    def test_weight_keyword(self):
        assert "2.5 litre" in water_intake("weight 70 water intake")

    def test_bare_weight(self):
        assert "2.1 litre" in water_intake("60 kg paani kitna piyu")

    def test_active_bump(self):
        out = water_intake("weight 80 active water")
        assert "3.3 litre" in out and "+0.5" in out

    def test_no_weight(self):
        assert "weight batao" in water_intake("paani kitna")


class TestSkills:
    def test_fuel_skill(self):
        from skills.fuel_water_skill import fuel_trip_cost as f
        assert "total" in f({"raw_text": "500 km 15 kmpl 100 rupee"})

    def test_water_skill(self):
        from skills.fuel_water_skill import water_intake as w
        assert "litre" in w({"raw_text": "weight 65 water intake"})
