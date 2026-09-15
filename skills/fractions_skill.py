"""Fractions — decimal<->fraction + fraction arithmetic. Offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="fraction_convert",
    description="Convert decimal/percent to fraction, or a fraction to decimal (offline).",
    patterns=[
        "0.75 ko fraction me badlo", "fraction convert karo",
        "3/4 ko decimal me", "25 percent ko fraction me",
        "decimal se fraction nikaalo", "is fraction ko simplest form me",
    ],
    required_entities=[],
)
def fraction_convert(slots: dict) -> str:
    from core.fractions_calc import fraction_convert as _fc
    return _fc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="fraction_math",
    description="Add, subtract, multiply or divide two fractions (offline).",
    patterns=[
        "1/2 + 1/3 kitna hota hai", "fractions add karo",
        "2/3 * 3/4 solve karo", "fraction subtract karo",
        "do fractions ka jod", "1/2 divided by 1/4",
    ],
    required_entities=[],
)
def fraction_math(slots: dict) -> str:
    from core.fractions_calc import fraction_math as _fm
    return _fm(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="mixed_number",
    description="Convert an improper fraction to a mixed number or back (offline).",
    patterns=[
        "7/3 ko mixed number me badlo", "mixed number banao",
        "2 1/3 ko improper fraction me", "improper fraction me convert karo",
        "mixed fraction nikaalo", "whole number aur fraction alag karo",
    ],
    required_entities=[],
)
def mixed_number(slots: dict) -> str:
    from core.fractions_calc import mixed_number as _mn
    return _mn(slots.get("raw_text") or slots.get("text") or "")
