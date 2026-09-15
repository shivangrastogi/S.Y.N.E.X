"""Color + roman numeral conversion by voice. Offline (core/color_roman)."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="color_convert",
    description="Convert colours between hex, rgb, and common names (offline).",
    patterns=[
        "ff5733 ka rgb batao", "hex color to rgb karo",
        "rgb ko hex me convert karo", "is color ka rgb kya hai",
        "255 87 51 ka hex", "red ka hex batao",
        "color convert karo", "#ff5733 rgb me batao",
    ],
    required_entities=[],
)
def color_convert(slots: dict) -> str:
    from core.color_roman import convert_color
    out = convert_color(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Color do, sir — hex (#ff5733), rgb (255 87 51), ya naam "
                   "(red). Main baaki forms bata dunga.")


@skill(
    name="roman_convert",
    description="Convert between numbers and Roman numerals (offline).",
    patterns=[
        "2024 ko roman me likho", "roman numeral batao",
        "roman me convert karo", "MMXXIV kya number hai",
        "ye roman number kya hai", "saal ko roman me batao",
        "49 ko roman me", "roman me kya hoga",
    ],
    required_entities=[],
)
def roman_convert(slots: dict) -> str:
    from core.color_roman import convert_roman
    out = convert_roman(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Number ya roman numeral do, sir — jaise '2024 ko roman "
                   "me' ya 'MMXXIV kya number hai'. (1 se 3999 tak.)")
