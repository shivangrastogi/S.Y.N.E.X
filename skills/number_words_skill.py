"""Number → words by voice — Indian (lakh/crore) or international. Offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="number_to_words",
    description="Spell a number in words — Indian lakh/crore or international (offline).",
    patterns=[
        "1234 ko words me batao", "number ko words me likho",
        "is number ko shabdon me batao", "1500000 words me",
        "number spell karo", "ye number english me likho",
        "digits to words karo", "number ko english words me batao",
    ],
    required_entities=[],
)
def number_to_words(slots: dict) -> str:
    from core.number_words import parse_and_spell
    text = slots.get("raw_text") or slots.get("text") or ""
    out = parse_and_spell(text)
    return out or ("Kaunsa number, sir? Jaise '1234567 ko words me batao'. "
                   "('international' bolo to million/billion me.)")
