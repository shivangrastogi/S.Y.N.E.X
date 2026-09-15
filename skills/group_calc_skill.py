"""Team/group splitter + calories-burned estimate. Pure math, offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="team_split",
    description="Split N people into teams or fixed-size groups, fairly (offline).",
    patterns=[
        "10 log 2 teams me baato", "team split karo", "groups bana do",
        "15 log 4 ke groups", "kitni teams banengi", "logo ko baraabar baato",
        "players ko teams me divide karo",
    ],
    required_entities=[],
)
def team_split(slots: dict) -> str:
    from core.group_calc import team_split as _ts
    return _ts(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="calories_burned",
    description="Rough calories burned from steps or distance walked/run (offline).",
    patterns=[
        "8000 steps me kitni calorie", "calories burned nikaalo",
        "kitni calorie burn hui", "5 km walk kitni calorie",
        "steps se calorie batao", "running me kitni calorie jali",
    ],
    required_entities=[],
)
def calories_burned(slots: dict) -> str:
    from core.group_calc import calories_burned as _cb
    return _cb(slots.get("raw_text") or slots.get("text") or "")
