"""Fuel/trip cost + daily water intake. Pure math, offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="fuel_trip_cost",
    description="Fuel needed & trip cost from distance + mileage + fuel price (offline).",
    patterns=[
        "500 km 15 kmpl 100 rupee kitna kharcha", "trip ka fuel cost nikaalo",
        "petrol kitna lagega", "fuel cost calculate karo",
        "300 km mileage 20 petrol cost", "kitna petrol lagega trip me",
        "diesel kharcha nikaalo",
    ],
    required_entities=[],
)
def fuel_trip_cost(slots: dict) -> str:
    from core.misc_calc import fuel_trip_cost as _ft
    return _ft(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="water_intake",
    description="Recommended daily water intake from body weight (offline).",
    patterns=[
        "din me kitna paani piyu", "water intake batao", "weight 70 water",
        "daily paani ki zaroorat", "kitna paani peena chahiye",
        "hydration kitni honi chahiye", "paani kitna piyu roz",
    ],
    required_entities=[],
)
def water_intake(slots: dict) -> str:
    from core.misc_calc import water_intake as _wi
    return _wi(slots.get("raw_text") or slots.get("text") or "")
