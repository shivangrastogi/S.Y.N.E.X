"""GCD/LCM + ratio simplify + stats + factorial/power. Offline."""
from __future__ import annotations

import re

from core.skill_registry import skill


@skill(
    name="gcd_lcm",
    description="Greatest common divisor (HCF) and least common multiple (offline).",
    patterns=[
        "gcd nikalo 12 aur 18 ka", "lcm batao 4 aur 6", "hcf kya hai",
        "12 aur 18 ka gcd", "gcd lcm nikalo", "lcm kya hoga",
        "in numbers ka hcf", "gcd calculate karo",
    ],
    required_entities=[],
)
def gcd_lcm(slots: dict) -> str:
    from core.number_props import gcd_lcm as _gl
    out = _gl(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Do (ya zyada) numbers do, sir — jaise 'gcd lcm nikalo "
                   "12 aur 18'.")


@skill(
    name="simplify_ratio",
    description="Simplify a ratio to its lowest terms (offline).",
    patterns=[
        "ratio simplify karo 8 12", "8 is to 12 simplify",
        "ratio chhota karo", "simplify ratio 15 25",
        "ye ratio simplest form me karo", "ratio ko lowest terms me",
    ],
    required_entities=[],
)
def simplify_ratio(slots: dict) -> str:
    from core.number_props import simplify_ratio as _sr
    out = _sr(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Do numbers do ratio ke liye — jaise 'ratio simplify "
                   "karo 8 12'.")


@skill(
    name="number_stats",
    description="Average, sum, median, min and max of a list of numbers (offline).",
    patterns=[
        "average nikalo 10 20 30", "in numbers ka average", "mean batao",
        "median kya hai", "sum karo 5 10 15", "max min batao",
        "10 20 30 ka total", "average median batao",
    ],
    required_entities=[],
)
def number_stats(slots: dict) -> str:
    from core.number_props import stats
    out = stats(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Kam se kam do numbers do, sir — jaise 'average nikalo "
                   "10 20 30'.")


@skill(
    name="factorial_power",
    description="Factorial, square, cube, or a power of a number (offline).",
    patterns=[
        "5 factorial", "2 power 10", "5 ka square", "2 ki ghaat 10",
        "3 cube", "factorial nikalo", "square batao", "power calculate karo",
    ],
    required_entities=[],
)
def factorial_power(slots: dict) -> str:
    from core.number_props import factorial, power
    text = slots.get("raw_text") or slots.get("text") or ""
    if re.search(r"factorial|\bfact\b", text, re.I):
        out = factorial(text)
    else:
        out = power(text) or factorial(text)
    return out or ("Kya calculate karun, sir? Jaise '5 factorial', '2 power "
                   "10', ya '5 ka square'.")
