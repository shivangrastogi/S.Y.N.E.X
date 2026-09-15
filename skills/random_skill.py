"""Decision + randomness toolkit — coin, dice, numbers, pick-one.

Pure stdlib ``random`` (via secrets for fairness). Zero network — a
JARVIS should be able to flip a coin without the internet.
"""
from __future__ import annotations

import re
import secrets

from core.skill_registry import skill

_rng = secrets.SystemRandom()


@skill(
    name="coin_toss",
    description="Flip a coin — heads or tails (local).",
    patterns=[
        "sikka uchalo", "coin toss karo", "heads ya tails", "toss karo",
        "sikka phenko", "coin flip karo", "chit ya pat",
    ],
    required_entities=[],
)
def coin_toss(_slots: dict) -> str:
    return f"{_rng.choice(['Heads', 'Tails'])} aaya, sir."


@skill(
    name="dice_roll",
    description="Roll one or more dice (local). '2 dice' / 'd20' supported.",
    patterns=[
        "dice roll karo", "pasa feko", "dice feko", "pasa phenko",
        "ek dice roll karo", "do dice feko", "dice throw karo",
    ],
    required_entities=[],
)
def dice_roll(slots: dict) -> str:
    text = (slots.get("raw_text") or "").lower()
    # dN sided dice ("d20"), else 6-sided
    sides = 6
    m = re.search(r"\bd\s?(\d{1,3})\b", text)
    if m:
        sides = max(2, min(1000, int(m.group(1))))
    # count of dice
    count = 1
    words = {"do": 2, "teen": 3, "char": 4, "paanch": 5, "panch": 5}
    cm = re.search(r"\b(\d{1,2})\s*(?:dice|pase|pasa)\b", text)
    if cm:
        count = max(1, min(10, int(cm.group(1))))
    else:
        for w, n in words.items():
            if re.search(rf"\b{w}\b", text):
                count = n
                break
    rolls = [_rng.randint(1, sides) for _ in range(count)]
    if count == 1:
        return f"{rolls[0]} aaya (d{sides})."
    return f"{' + '.join(map(str, rolls))} = {sum(rolls)}  ({count}×d{sides})."


@skill(
    name="random_number",
    description="Pick a random number, default 1-100 or a spoken range (local).",
    patterns=[
        "ek random number do", "koi number bolo", "random number generate karo",
        "1 se 100 ke beech number", "koi number socho", "random number do",
        "ek number chuno", "lucky number do",
    ],
    required_entities=[],
)
def random_number(slots: dict) -> str:
    text = (slots.get("raw_text") or "").lower()
    m = re.search(r"(\d+)\s*(?:se|to|-|and|aur)\s*(\d+)", text)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
    else:
        lo, hi = 1, 100
    if lo == hi:
        return f"{lo} (range ek hi number tha, sir)."
    return f"{_rng.randint(lo, hi)}  (range {lo}-{hi})."


_PICK_SPLIT = re.compile(r"\s*(?:,|/| ya | or | aur )\s*", re.IGNORECASE)
_PICK_STRIP = re.compile(
    r"^(?:in\s*me\s*se|inme\s*se|in\s*mein\s*se|inmein\s*se)?\s*"
    r"(?:koi\s*)?(?:ek\s*)?(?:chuno|pick\s*karo|select\s*karo|decide\s*karo|"
    r"batao|choose)?\s*[:\-]?\s*",
    re.IGNORECASE)


@skill(
    name="random_pick",
    description="Pick one option from a spoken list (local).",
    patterns=[
        "in me se ek chuno", "inme se koi ek pick karo", "in me se decide karo",
        "in options me se ek chuno", "mere liye choose karo",
        "in me se koi ek batao", "decide karo mere liye",
    ],
    required_entities=[],
)
def random_pick(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    body = _PICK_STRIP.sub("", text).strip(" ?.")
    options = [o.strip() for o in _PICK_SPLIT.split(body) if o.strip()]
    # keep only real options (drop a trailing verb-only fragment)
    options = [o for o in options if len(o) <= 40]
    if len(options) < 2:
        return ("Options do, sir — jaise 'chai ya coffee' me se ek chuno', "
                "toh main decide kar doon.")
    return f"Main kahta hoon: {_rng.choice(options)}."
