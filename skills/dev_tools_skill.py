"""Developer helpers by voice — base conversion + NATO phonetic. Offline."""
from __future__ import annotations

import re

from core.skill_registry import skill


@skill(
    name="base_convert",
    description="Convert a number between binary/octal/decimal/hex (offline).",
    patterns=[
        "255 ko binary me convert karo", "ff ko decimal me batao",
        "10 ko hex me likho", "binary to decimal karo",
        "101 binary kya hai decimal me", "octal me convert karo",
        "hex me badlo", "decimal ko binary me karo",
    ],
    required_entities=[],
)
def base_convert(slots: dict) -> str:
    from core.dev_tools import convert_base
    text = slots.get("raw_text") or slots.get("text") or ""
    out = convert_base(text)
    return out or ("Kya se kya convert karun, sir? Jaise '255 ko hex me' ya "
                   "'ff hex to decimal' ya '10 ko binary me'.")


# The word/code to spell can appear before OR after the command phrase
# ("delta ko phonetic..." vs "phonetic... AB12"), and a regex that strips
# only one command word mistook "spell karo AB12" for the word. Filter out
# every command/filler token; whatever remains is the target.
_PH_CMD = {
    "phonetic", "phonetically", "nato", "me", "mein", "spell", "karo",
    "batao", "kar", "do", "ko", "is", "code", "word", "alphabet", "likho",
    "in", "into", "ka", "it", "this", "the",
}


def _phonetic_target(text: str) -> str:
    toks = [t for t in (text or "").split() if t.lower() not in _PH_CMD]
    return " ".join(toks).strip(" ?\"'")


@skill(
    name="phonetic_spell",
    description="Spell a word/code in NATO phonetic alphabet (offline).",
    patterns=[
        "phonetic me spell karo", "nato phonetic batao",
        "delta ko phonetic me spell karo", "word ko phonetically spell karo",
        "is code ko phonetic me batao", "spell it phonetically",
        "phonetic alphabet me likho",
    ],
    required_entities=[],
)
def phonetic_spell(slots: dict) -> str:
    from core.dev_tools import phonetic
    text = slots.get("raw_text") or slots.get("text") or ""
    word = _phonetic_target(text)
    out = phonetic(word)
    if not out:
        return ("Kaunsa word ya code phonetic me spell karun, sir? Jaise "
                "'delta ko phonetic me spell karo'.")
    return out
