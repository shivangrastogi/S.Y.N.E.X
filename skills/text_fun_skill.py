"""Morse + palindrome + anagram by voice. Offline (core/text_fun).

The payload (text / word(s)) can appear BEFORE or AFTER the command
words, so a `.*?`-prefix regex strip would eat it. We drop command/filler
words instead — robust to word order.
"""
from __future__ import annotations

import re

from core.skill_registry import skill

_MORSE_CMD = {"morse", "code", "me", "mein", "se", "into", "to", "convert",
              "likho", "decode", "encode", "karo", "batao", "ko", "ka", "ki",
              "is", "text", "hai", "kya", "kar", "do", "badlo"}
_PAL_CMD = {"palindrome", "ulta", "hai", "kya", "check", "karo", "padho",
            "same", "is", "word", "ye", "ko", "bhi", "reverse", "kar"}
_ANAG_CMD = {"anagram", "check", "hain", "hai", "karo", "kya", "in", "dono",
             "ka", "ye", "do", "words", "word", "the", "are"}


def _drop(text: str, cmd: set) -> str:
    return " ".join(t for t in (text or "").split()
                    if t.lower().strip(":-?\"'") not in cmd).strip(" :-?\"'")


@skill(
    name="morse_code",
    description="Encode text to Morse or decode Morse to text (auto-detect, offline).",
    patterns=[
        "morse code me convert karo", "morse me likho", "morse decode karo",
        "sos morse me", "ye morse kya hai", "morse me badlo",
        "text ko morse me karo", "morse encode karo",
    ],
    required_entities=[],
)
def morse_code(slots: dict) -> str:
    from core.text_fun import morse
    raw = slots.get("raw_text") or slots.get("text") or ""
    # Keep dots/dashes tokens (morse to decode) AND non-command words.
    tokens = []
    for tok in raw.split():
        low = tok.lower().strip(":-?\"'")
        if set(tok) <= set(".-/") and tok:          # a morse token
            tokens.append(tok)
        elif low and low not in _MORSE_CMD:
            tokens.append(tok)
    body = " ".join(tokens).strip()
    out = morse(body)
    if not out:
        return ("Kya convert karun, sir? Text (→ morse) ya dots-dashes "
                "(→ text) do — jaise 'sos morse me'.")
    return out


_ANAG_SPLIT = re.compile(r"\s+(?:aur|and|,|&)\s+|\s+vs\s+", re.IGNORECASE)


@skill(
    name="palindrome_check",
    description="Check if a word/phrase reads the same backwards (offline).",
    patterns=[
        "palindrome hai kya", "ye palindrome hai", "palindrome check karo",
        "kya ye ulta bhi same hai", "is word ko ulta padho same hai kya",
        "check palindrome",
    ],
    required_entities=[],
)
def palindrome_check(slots: dict) -> str:
    from core.text_fun import is_palindrome
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _drop(raw, _PAL_CMD)
    out = is_palindrome(body)
    return out or ("Kaunsa word ya phrase check karun, sir? Jaise "
                   "'madam palindrome hai kya'.")


@skill(
    name="anagram_check",
    description="Check if two words/phrases are anagrams (offline).",
    patterns=[
        "anagram check karo", "ye do words anagram hain kya",
        "kya ye anagram hain", "in dono ka anagram check karo",
        "anagram hai kya", "check anagram",
    ],
    required_entities=[],
)
def anagram_check(slots: dict) -> str:
    from core.text_fun import are_anagram
    raw = slots.get("raw_text") or slots.get("text") or ""
    # Split on the connector FIRST (so "aur" separates the two words), then
    # drop command words from each side.
    halves = _ANAG_SPLIT.split(raw)
    parts = [_drop(h, _ANAG_CMD) for h in halves]
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return ("Do words do, sir — jaise 'listen aur silent anagram hain "
                "kya'.")
    out = are_anagram(parts[0], parts[1])
    return out or "Dono words theek se samajh nahi aaye, sir."


_XFORM_CMD = {"reverse", "ulta", "ultaa", "karo", "kar", "do", "likho",
              "capital", "uppercase", "upper", "lowercase", "lower", "small",
              "title", "case", "me", "mein", "alternating", "text", "is",
              "ko", "words", "word", "batao", "letters", "bade", "chhote",
              "badi"}

_XFORM_MODES = [
    (("reverse word", "words reverse", "shabd ulta"), "reverse_words"),
    (("reverse", "ulta", "ultaa"), "reverse"),
    (("alternating", "mixed case", "alternate"), "alternating"),
    (("title", "har shabd bada"), "title"),
    (("capital", "uppercase", "upper", "bade letter", "badi"), "upper"),
    (("lowercase", "lower", "small", "chhote"), "lower"),
]


@skill(
    name="text_transform",
    description="Reverse or change the case of given text — inline, not the clipboard (offline).",
    patterns=[
        "reverse karo hello", "ulta karo ye text", "capital letters me likho",
        "uppercase karo is text ko", "title case me karo",
        "is text ko ulta likho", "small letters me karo", "alternating case karo",
    ],
    required_entities=[],
)
def text_transform(slots: dict) -> str:
    from core.text_fun import transform
    raw = slots.get("raw_text") or slots.get("text") or ""
    low = raw.lower()
    mode = "reverse"
    for keys, m in _XFORM_MODES:
        if any(k in low for k in keys):
            mode = m
            break
    body = _drop(raw, _XFORM_CMD)
    out = transform(body, mode)
    if not out:
        return ("Kya transform karun, sir? Text do — jaise 'reverse karo "
                "hello world' ya 'capital letters me likho aeris'.")
    return f"{out}"


@skill(
    name="count_chars",
    description="Count a letter, or vowels/consonants, in given text (offline).",
    patterns=[
        "hello me kitne l hain", "count karo kitne o hain",
        "vowels kitne hain", "kitne a hain word me",
        "is text me kitne letters hain", "consonants kitne hain",
        "kaunsa letter kitni baar",
    ],
    required_entities=[],
)
def count_chars(slots: dict) -> str:
    import re as _re
    from core.text_fun import count_chars as _cc
    raw = slots.get("raw_text") or slots.get("text") or ""
    # "kitne X hain" → target single letter X. Remove the WHOLE matched
    # phrase (incl. the target letter) so it can't leak into the text body.
    target = None
    m = _re.search(r"\bkitne?\s+([a-z])\s+(?:hain|aate|aata|baar)\b", raw, _re.I)
    if m:
        target = m.group(1).lower()
        raw = raw[:m.start()] + " " + raw[m.end():]
    cmd = {"me", "mein", "kitne", "kitna", "hain", "hai", "aate", "aata",
           "baar", "count", "karo", "letters", "letter", "vowels",
           "consonants", "is", "text", "word", "ye", "kaunsa", "kitni",
           # English command/unit words were missing → they leaked into the
           # counted body ("count characters in hello" counted "characters in").
           "characters", "character", "chars", "char", "in", "length", "of",
           "vowel", "consonant", "words"}
    body = _drop(raw, cmd)
    out = _cc(body, target)
    if not out:
        return ("Kis text me ginun, sir? Jaise 'hello world me kitne l "
                "hain' ya 'aeris me vowels kitne'.")
    return out


_ACR_CMD = {"acronym", "short", "form", "initials", "banao", "bana", "do",
            "nikalo", "batao", "iske", "ka", "ke", "ki", "pehle", "letters",
            "kya", "hoga", "lo", "se"}


@skill(
    name="acronym_maker",
    description="Make an acronym from the first letters of a phrase (offline).",
    patterns=[
        "acronym banao", "short form banao", "initials nikalo",
        "iske pehle letters lo", "ready aim fire ka acronym",
        "acronym bana do", "initials batao is phrase ki",
    ],
    required_entities=[],
)
def acronym_maker(slots: dict) -> str:
    from core.text_fun import acronym
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _drop(raw, _ACR_CMD)
    out = acronym(body)
    if not out:
        return ("Kaunsa phrase, sir? Jaise 'ready aim fire ka acronym' = "
                "RAF.")
    return out


@skill(
    name="vowel_consonant",
    description="Count vowels, consonants, digits and spaces in text (offline).",
    patterns=[
        "hello world me kitne vowels", "vowels consonants gino",
        "kitne vowels hain is word me", "consonant count karo",
        "swar vyanjan gino", "vowel consonant nikaalo",
    ],
    required_entities=[],
)
def vowel_consonant(slots: dict) -> str:
    from core.text_fun import vowel_consonant
    return vowel_consonant(slots.get("raw_text") or slots.get("text") or "")
