"""Fixed-date holiday countdown + Chinese zodiac. Pure math, offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="festival_countdown",
    description="Days left until a fixed-date holiday like Independence Day or Christmas (offline).",
    patterns=[
        "independence day me kitne din", "christmas kab hai kitne din",
        "republic day countdown", "new year me kitne din baaki",
        "gandhi jayanti kitne din me", "next holiday kitni door",
    ],
    required_entities=[],
)
def festival_countdown(slots: dict) -> str:
    from core.festival_zodiac import festival_countdown as _fc
    return _fc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="chinese_zodiac",
    description="Chinese zodiac animal for a birth year (offline).",
    patterns=[
        "1998 ka chinese zodiac", "mera chinese zodiac kya hai",
        "chinese sign batao saal se", "kaunsa animal year hai mera",
        "chinese zodiac nikaalo", "year of which animal hai 2000",
    ],
    required_entities=[],
)
def chinese_zodiac(slots: dict) -> str:
    from core.festival_zodiac import chinese_zodiac as _cz
    return _cz(slots.get("raw_text") or slots.get("text") or "")
