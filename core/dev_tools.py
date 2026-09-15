"""Developer helpers — number-base conversion + NATO phonetic spelling.

Pure stdlib, offline. Aimed at a dev's daily "255 in hex?" / "spell that
code phonetically" needs.
"""
from __future__ import annotations

import re
from typing import Optional

_BASE_ALIAS = {
    "binary": 2, "bin": 2, "base2": 2, "base 2": 2,
    "octal": 8, "oct": 8, "base8": 8, "base 8": 8,
    "decimal": 10, "dec": 10, "base10": 10, "base 10": 10,
    "hex": 16, "hexadecimal": 16, "base16": 16, "base 16": 16,
}

_PREFIX = {"0x": 16, "0b": 2, "0o": 8}


def _to_int(token: str, base: Optional[int]) -> Optional[int]:
    token = token.strip().lower()
    for p, b in _PREFIX.items():
        if token.startswith(p):
            try:
                return int(token[2:], b)
            except ValueError:
                return None
    try:
        return int(token, base or 10)
    except ValueError:
        return None


def _render(n: int, base: int) -> str:
    if base == 2:
        return bin(n)[2:] if n >= 0 else "-" + bin(-n)[2:]
    if base == 8:
        return oct(n)[2:] if n >= 0 else "-" + oct(-n)[2:]
    if base == 16:
        return (hex(n)[2:] if n >= 0 else "-" + hex(-n)[2:]).upper()
    return str(n)


def convert_base(text: str) -> Optional[str]:
    """'255 to hex', 'ff hex to decimal', '10 ko binary me', '0b101 decimal'."""
    t = (text or "").strip().lower()
    bases = [(m.start(), _BASE_ALIAS[m.group(0)])
             for m in re.finditer(r"base\s?\d+|binary|bin|octal|oct|decimal|"
                                  r"dec|hexadecimal|hex", t)]
    # value token: a WHOLE token (\b…\b) so a stray hex letter inside a word
    # ("c" in "convert", "e" in "hex") never gets mistaken for the value.
    token = None
    vm = None
    for m in re.finditer(r"\b(0x[0-9a-f]+|0b[01]+|0o[0-7]+|[0-9a-f]+)\b", t):
        cand = m.group(0)
        if cand in _BASE_ALIAS or cand in ("to", "in", "me", "ko"):
            continue
        token, vm = cand, m
        break
    if not token:
        return None

    # Base words in reading order. The TARGET is the rightmost base word
    # (it follows "to"/"me"/"in ... me"). When TWO base words trail the
    # value ("VALUE SRCBASE to DSTBASE" → "ff hex to decimal"), the first
    # is the source, the last the target.
    src_base = None
    dst_base = None
    after = [b for pos, b in bases if pos > vm.start()]
    before = [b for pos, b in bases if pos < vm.start()]
    if len(after) >= 2:
        src_base, dst_base = after[0], after[-1]
    elif len(after) == 1:
        dst_base = after[0]
        if before:
            src_base = before[-1]
    elif before:
        dst_base = before[-1]                    # "hex me 255 karo" (rare)
    if dst_base is None:
        return None
    if src_base is None:
        if any(token.startswith(p) for p in _PREFIX):
            src_base = None                      # prefix decides
        elif re.search(r"[a-f]", token):
            src_base = 16
        else:
            src_base = 10
    n = _to_int(token, src_base)
    if n is None:
        return None
    out = _render(n, dst_base)
    name = {2: "binary", 8: "octal", 10: "decimal", 16: "hex"}[dst_base]
    return f"{token} = {out} ({name})."


# ── NATO phonetic ────────────────────────────────────────────────────── #

_NATO = {
    "a": "Alpha", "b": "Bravo", "c": "Charlie", "d": "Delta", "e": "Echo",
    "f": "Foxtrot", "g": "Golf", "h": "Hotel", "i": "India", "j": "Juliett",
    "k": "Kilo", "l": "Lima", "m": "Mike", "n": "November", "o": "Oscar",
    "p": "Papa", "q": "Quebec", "r": "Romeo", "s": "Sierra", "t": "Tango",
    "u": "Uniform", "v": "Victor", "w": "Whiskey", "x": "X-ray",
    "y": "Yankee", "z": "Zulu",
    "0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four",
    "5": "Five", "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine",
}


def phonetic(word: str) -> Optional[str]:
    word = (word or "").strip()
    if not word:
        return None
    out = []
    for ch in word:
        low = ch.lower()
        if low in _NATO:
            tag = _NATO[low]
            out.append(tag.upper() if ch.isupper() and ch.isalpha() else tag)
        elif ch == " ":
            out.append("(space)")
        else:
            out.append(ch)
    return " - ".join(out)
