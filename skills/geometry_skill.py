"""Geometry — circle + Pythagoras. Pure math, offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="circle_calc",
    description="Circle area, circumference and diameter from radius/diameter (offline).",
    patterns=[
        "radius 5 circle ka area", "circle area circumference nikaalo",
        "diameter 10 ka area", "vritt ka area batao",
        "circle ki circumference kitni", "trijya se area nikaalo",
    ],
    required_entities=[],
)
def circle_calc(slots: dict) -> str:
    from core.geometry import circle_calc as _cc
    return _cc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="pythagoras",
    description="Right-triangle side via Pythagoras: two legs -> hypotenuse or back (offline).",
    patterns=[
        "3 4 ka hypotenuse kya hai", "pythagoras se side nikaalo",
        "hypotenuse 5 leg 3 doosri side", "right triangle ki teesri side",
        "legs 6 8 hypotenuse", "karan nikaalo do bhuja se",
    ],
    required_entities=[],
)
def pythagoras(slots: dict) -> str:
    from core.geometry import pythagoras as _py
    return _py(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="triangle_area",
    description="Triangle area from 3 sides (Heron) or base x height (offline).",
    patterns=[
        "3 4 5 triangle ka area", "triangle area nikaalo",
        "base 10 height 6 triangle area", "teen bhuja se area",
        "tribhuj ka area batao", "heron formula se area",
    ],
    required_entities=[],
)
def triangle_area(slots: dict) -> str:
    from core.geometry import triangle_area as _ta
    return _ta(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="volume_calc",
    description="Volume of a sphere, cube, cylinder or cone from dimensions (offline).",
    patterns=[
        "sphere radius 5 ka volume", "volume nikaalo shape ka",
        "cube side 4 volume", "cylinder radius 3 height 10 volume",
        "gola ka volume batao", "cone ka volume kitna",
    ],
    required_entities=[],
)
def volume_calc(slots: dict) -> str:
    from core.geometry import volume_calc as _vc
    return _vc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="coordinate_distance",
    description="Distance, midpoint and slope between two (x,y) points (offline).",
    patterns=[
        "0 0 se 3 4 distance", "do points ke beech distance",
        "coordinate distance nikaalo", "midpoint aur slope batao",
        "point 1 2 se 4 6 ki doori", "distance between two points",
    ],
    required_entities=[],
)
def coordinate_distance(slots: dict) -> str:
    from core.geometry import coordinate_distance as _cd
    return _cd(slots.get("raw_text") or slots.get("text") or "")
