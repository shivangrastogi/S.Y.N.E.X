"""Marks-percentage + sleep-cycle bedtime calculator. Pure math, offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="marks_percentage",
    description="Percentage and grade from marks obtained out of total (offline).",
    patterns=[
        "450 out of 500 percentage", "marks ka percentage nikaalo",
        "500 me se 450 kitne percent", "percentage kitna bana",
        "72 out of 80 kitne percent", "mere marks ka percent batao",
        "grade kya banega marks se",
    ],
    required_entities=[],
)
def marks_percentage(slots: dict) -> str:
    from core.life_calc import marks_percentage as _mp
    return _mp(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="sleep_cycle",
    description="Best bedtime/wake times using 90-min sleep cycles (offline).",
    patterns=[
        "raat 11 baje soun to kab uthu", "sleep cycle calculate karo",
        "6 baje uthna hai to kab soun", "kitne baje sona chahiye",
        "best wake up time batao sleep cycle", "achhi neend ke liye kab uthu",
        "kab soun ki fresh uthu",
    ],
    required_entities=[],
)
def sleep_cycle(slots: dict) -> str:
    from core.life_calc import sleep_cycle as _sc
    return _sc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="cgpa_percentage",
    description="Convert CGPA to percentage or back (CBSE 9.5 formula, offline).",
    patterns=[
        "8.5 cgpa to percentage", "cgpa ko percentage me convert karo",
        "76 percent to cgpa", "mera cgpa percentage kitna hoga",
        "gpa se percentage nikaalo", "percentage ko cgpa me badlo",
    ],
    required_entities=[],
)
def cgpa_percentage(slots: dict) -> str:
    from core.life_calc import cgpa_percentage as _cp
    return _cp(slots.get("raw_text") or slots.get("text") or "")
