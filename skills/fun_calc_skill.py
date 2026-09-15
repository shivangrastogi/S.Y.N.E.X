"""Days-until-weekend + Scrabble word score. Pure math, offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="weekend_countdown",
    description="How many days until the weekend (Saturday) (offline).",
    patterns=[
        "weekend me kitne din baaki", "weekend kab hai",
        "kitne din me weekend aayega", "saturday me kitne din",
        "chutti me kitne din", "next weekend kitni door",
    ],
    required_entities=[],
)
def weekend_countdown(slots: dict) -> str:
    from core.fun_calc import weekend_countdown as _wc
    return _wc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="scrabble_score",
    description="Scrabble points for a word (letter values summed, offline).",
    patterns=[
        "scrabble score of quiz", "is word ka scrabble score",
        "scrabble points nikaalo", "word ka scrabble value batao",
        "kitne points milenge scrabble me", "scrabble me iska score",
    ],
    required_entities=[],
)
def scrabble_score(slots: dict) -> str:
    from core.fun_calc import scrabble_score as _ss
    return _ss(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="week_number",
    description="ISO week number and day-of-year for a date or today (offline).",
    patterns=[
        "aaj saal ka kaunsa week hai", "week number batao",
        "aaj kaunsa hafta chal raha hai", "saal ka kaunsa din hai aaj",
        "day of year kya hai", "15 august 2026 ka week number",
    ],
    required_entities=[],
)
def week_number(slots: dict) -> str:
    from core.fun_calc import week_number as _wn
    return _wn(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="ordinal_number",
    description="Turn a number into its ordinal form, e.g. 23 -> 23rd (offline).",
    patterns=[
        "23 ka ordinal kya hai", "ordinal number banao",
        "101 ko ordinal me likho", "iska ordinal form batao",
        "number ka ordinal nikaalo", "21 ka ordinal",
    ],
    required_entities=[],
)
def ordinal_number(slots: dict) -> str:
    from core.fun_calc import ordinal_number as _on
    return _on(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="duration_humanize",
    description="Break a raw duration into days/hours/minutes/seconds (offline).",
    patterns=[
        "9000 seconds kitne ghante", "duration humanize karo",
        "150 minutes ko hours me todo", "itne seconds me kitna time",
        "90 hours kitne din", "seconds ko ghante minute me badlo",
    ],
    required_entities=[],
)
def duration_humanize(slots: dict) -> str:
    from core.fun_calc import duration_humanize as _dh
    return _dh(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="next_birthday",
    description="Days until your next birthday (and the age you'll turn) (offline).",
    patterns=[
        "meri birthday me kitne din baaki", "next birthday kab hai",
        "15 august ko birthday kitne din me", "birthday countdown batao",
        "kitne din me birthday aayegi", "mera janamdin kab aayega",
    ],
    required_entities=[],
)
def next_birthday(slots: dict) -> str:
    from core.fun_calc import next_birthday as _nb
    return _nb(slots.get("raw_text") or slots.get("text") or "")
