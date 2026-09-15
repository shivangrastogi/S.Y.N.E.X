"""Leap-year / days-in-month (pure math) + rhyming words (local LLM). Offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="leap_year_check",
    description="Check whether a year is a leap year (offline).",
    patterns=[
        "leap year hai kya", "2024 leap year hai", "is 2100 a leap year",
        "kya ye leap year hai", "leap year check karo",
        "2000 leap year tha kya",
    ],
    required_entities=[],
)
def leap_year_check(slots: dict) -> str:
    from core.calendar_facts import leap_year
    out = leap_year(slots.get("raw_text") or slots.get("text") or "")
    return out or "Kaunsa saal check karu? Jaise '2024 leap year hai kya'."


@skill(
    name="days_in_month",
    description="How many days are in a given month/year (offline).",
    patterns=[
        "february me kitne din", "march me kitne days", "kitne din hote hain",
        "how many days in february 2024", "is month me kitne din",
        "april me kitne din hote hain",
    ],
    required_entities=[],
)
def days_in_month(slots: dict) -> str:
    from core.calendar_facts import days_in_month as _dim
    out = _dim(slots.get("raw_text") or slots.get("text") or "")
    return out or "Kaunsa month? Jaise 'February 2024 me kitne din'."


@skill(
    name="rhyming_words",
    description="Suggest words that rhyme with a given word, using the local model (offline).",
    patterns=[
        "rhyming words batao", "iske saath rhyme karne wale shabd",
        "kis se rhyme hota hai", "rhyme words do", "tukbandi wale shabd batao",
        "words that rhyme with",
    ],
    required_entities=[],
)
def rhyming_words(slots: dict) -> str:
    from skills.llm_utils_skill import _gen, _drop_words, _NO_MODEL
    raw = slots.get("raw_text") or slots.get("text") or ""
    word = _drop_words(raw, {"rhyming", "words", "batao", "iske", "saath",
                             "rhyme", "karne", "wale", "shabd", "kis", "se",
                             "hota", "hai", "do", "tukbandi", "that", "with",
                             "word", "ke", "ki"})
    if len(word) < 2:
        return "Kaunse word ke rhyming words chahiye? Jaise 'light ke rhyming words'."
    out = _gen(f"List 6-8 words that rhyme with '{word}'.",
               system=("Give ONLY a comma-separated list of real rhyming "
                       "words. No sentences, no preamble."),
               max_tokens=120)
    return out.strip() if out else _NO_MODEL
