"""Text fun/utility — Morse code + palindrome + anagram. Pure stdlib, offline."""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional

_MORSE = {
    "a": ".-", "b": "-...", "c": "-.-.", "d": "-..", "e": ".", "f": "..-.",
    "g": "--.", "h": "....", "i": "..", "j": ".---", "k": "-.-", "l": ".-..",
    "m": "--", "n": "-.", "o": "---", "p": ".--.", "q": "--.-", "r": ".-.",
    "s": "...", "t": "-", "u": "..-", "v": "...-", "w": ".--", "x": "-..-",
    "y": "-.--", "z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "'": ".----.", "!": "-.-.--",
    "/": "-..-.", "(": "-.--.", ")": "-.--.-", "&": ".-...", ":": "---...",
    "=": "-...-", "+": ".-.-.", "-": "-....-", "@": ".--.-.",
}
_UNMORSE = {v: k for k, v in _MORSE.items()}


def to_morse(text: str) -> Optional[str]:
    out = []
    for ch in text.lower():
        if ch == " ":
            out.append("/")
        elif ch in _MORSE:
            out.append(_MORSE[ch])
        # unknown chars silently dropped
    return " ".join(out) if out else None


def from_morse(code: str) -> Optional[str]:
    code = code.strip()
    if not re.fullmatch(r"[.\-/ ]+", code):
        return None
    words = re.split(r"\s*/\s*", code)
    out = []
    for word in words:
        letters = [_UNMORSE.get(sym, "?") for sym in word.split() if sym]
        out.append("".join(letters))
    text = " ".join(out).strip()
    return text or None


def morse(text: str) -> Optional[str]:
    """Auto-detect: mostly dots/dashes → decode, else encode."""
    t = (text or "").strip()
    if not t:
        return None
    stripped = re.sub(r"\s", "", t)
    if stripped and set(stripped) <= set(".-/"):
        dec = from_morse(t)
        return f"{dec}" if dec else None
    enc = to_morse(t)
    return enc


# ── palindrome / anagram ─────────────────────────────────────────────── #

def _letters(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def is_palindrome(text: str) -> Optional[str]:
    core = _letters(text or "")
    if not core:
        return None
    rev = core[::-1]
    if core == rev:
        return f"Haan, '{text.strip()}' palindrome hai — ulta bhi wahi."
    return f"Nahi, '{text.strip()}' palindrome nahi ({core} vs {rev})."


def are_anagram(a: str, b: str) -> Optional[str]:
    la, lb = _letters(a), _letters(b)
    if not la or not lb:
        return None
    if Counter(la) == Counter(lb):
        return f"Haan, '{a.strip()}' aur '{b.strip()}' anagram hain."
    return f"Nahi, '{a.strip()}' aur '{b.strip()}' anagram nahi hain."


# ── text transforms (inline given text) ──────────────────────────────── #

def transform(text: str, mode: str) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    if mode == "reverse":
        return text[::-1]
    if mode == "upper":
        return text.upper()
    if mode == "lower":
        return text.lower()
    if mode == "title":
        return text.title()
    if mode == "alternating":
        out = []
        i = 0
        for ch in text:
            if ch.isalpha():
                out.append(ch.upper() if i % 2 == 0 else ch.lower())
                i += 1
            else:
                out.append(ch)
        return "".join(out)
    if mode == "reverse_words":
        return " ".join(text.split()[::-1])
    return None


# ── character counting ───────────────────────────────────────────────── #

def acronym(text: str) -> Optional[str]:
    """First letter of each word, uppercased. Skips tiny joining words."""
    skip = {"a", "an", "the", "of", "and", "or", "for", "to", "in", "on",
            "ka", "ki", "ke", "aur", "ya"}
    words = [w for w in re.findall(r"[A-Za-z]+", text or "")]
    kept = [w for w in words if w.lower() not in skip] or words
    if not kept:
        return None
    letters = "".join(w[0].upper() for w in kept)
    return f"{' '.join(kept)} = {letters}"


_VOWELS = set("aeiou")


def count_chars(text: str, target: Optional[str] = None) -> Optional[str]:
    text = (text or "")
    if not text.strip():
        return None
    if target:
        target = target.lower()[0]
        n = text.lower().count(target)
        return f"'{text.strip()}' mein '{target}' {n} baar aata hai."
    letters = [c for c in text.lower() if c.isalpha()]
    vowels = sum(1 for c in letters if c in _VOWELS)
    cons = len(letters) - vowels
    digits = sum(1 for c in text if c.isdigit())
    return (f"{len(letters)} letters ({vowels} vowels, {cons} consonants)"
            + (f", {digits} digits" if digits else "") + ".")


def vowel_consonant(text: str) -> "Optional[str]":
    """Count vowels, consonants, digits, spaces in the payload text."""
    import re as _re
    t = text or ""
    q = _re.search(r"[\"'“”‘’](.+?)[\"'“”‘’]", t)
    if q:
        payload = q.group(1)
    else:
        payload = _re.sub(
            r"\b(count|gino|ginti|vowel|vowels|consonant|consonants|kitne|"
            r"kitni|hain|is|text|me|mein|in|the|of|batao|nikaalo|swar|vyanjan|"
            r"letters|characters|words)\b",
            " ", t, flags=_re.IGNORECASE)
        payload = payload.strip(" \"'")
    letters = [c for c in payload if c.isalpha()]
    if len(letters) < 1:
        return ("Kaunsa text? Jaise 'hello world me kitne vowels' — main "
                "vowel/consonant gin dunga.")
    vowels = sum(1 for c in payload.lower() if c in "aeiou")
    consonants = sum(1 for c in letters if c.lower() not in "aeiou")
    digits = sum(1 for c in payload if c.isdigit())
    spaces = sum(1 for c in payload if c == " ")
    return (f"'{payload.strip()}' me: {vowels} vowels, {consonants} consonants, "
            f"{len(letters)} letters, {digits} digits, {spaces} spaces.")
