"""Leetspeak encoder — turn text into 1337 5p34k (offline, no deps).

Follows the text_fun convention: the payload (the text to convert) can appear
BEFORE or AFTER the command words, so we DROP command/filler words rather than
regex-slicing (which would eat a payload that precedes the command).
"""
from __future__ import annotations

from core.skill_registry import skill

_LEET_CMD = {"leetspeak", "leet", "1337", "l33t", "speak", "me", "mein", "into",
             "to", "convert", "likho", "likh", "karo", "kar", "do", "badlo",
             "ko", "ka", "ki", "text", "is", "hai", "kya", "banao", "bana",
             "translate", "in", "5p34k"}

# Classic basic leet substitutions (case-folded to the digit/symbol form).
_MAP = str.maketrans({
    "a": "4", "A": "4", "e": "3", "E": "3", "i": "1", "I": "1",
    "o": "0", "O": "0", "s": "5", "S": "5", "t": "7", "T": "7",
    "l": "1", "L": "1", "g": "9", "G": "9", "b": "8", "B": "8",
})


def _drop(text: str, cmd: set) -> str:
    return " ".join(t for t in (text or "").split()
                    if t.lower().strip(":-?\"'") not in cmd).strip(" :-?\"'")


@skill(
    name="leetspeak",
    description="Turn text into leetspeak / 1337 5p34k (offline, no deps).",
    patterns=[
        "leetspeak me convert karo", "leet me likho", "1337 speak banao",
        "ye text leetspeak me karo", "convert to leetspeak", "leet karo",
        "l33t speak me badlo", "hello ko leetspeak me likho",
        "text ko 1337 me convert karo", "leetspeak translate", "make it leet",
    ],
    required_entities=[],
)
def leetspeak(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _drop(raw, _LEET_CMD)
    if not body:
        return ("Kaunsa text leetspeak me convert karun, sir? "
                "Jaise 'hello world ko leetspeak me likho'.")
    return body.translate(_MAP)
