"""Hex encode-decode + reading-time estimate. Pure stdlib, offline.

(Base64 already lives in compute_skills; this module owns hex + reading-time.)
"""
from __future__ import annotations

import re
from typing import Optional

_CMD = (r"\b(base64|b64|hex|hexadecimal|encode|decode|karo|kar|do|me|mein|"
        r"into|to|banao|nikaalo|convert|kardo|the|this|text|string)\b")


def _payload(text: str) -> str:
    q = re.search(r"[\"'](.+?)[\"']", text or "")
    if q:
        return q.group(1)
    p = re.sub(_CMD, " ", text or "", flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", p).strip(" \"'")


def _is_decode(text: str) -> bool:
    return bool(re.search(r"\bdecode\b|\bwaapas\b|\bwapas\b", text or "",
                          re.IGNORECASE))


def hex_convert(text: str) -> Optional[str]:
    payload = _payload(text)
    if not payload:
        return "Kya hex karu? Jaise 'hex encode karo hello'."
    if _is_decode(text):
        clean = payload.replace(" ", "").replace("0x", "")
        try:
            raw = bytes.fromhex(clean)
            return f"Hex decode: {raw.decode('utf-8', 'replace')}"
        except ValueError:
            return "Ye valid hex nahi lag raha — sirf 0-9 a-f rakho."
    # A bare number ("42 in hexadecimal") means the NUMBER 42 → 0x2a, not
    # hex-encoding the ASCII bytes of "42". Strip filler and check.
    _num = re.sub(r"\b(in|into|to|me|mein|ko|as|of|number)\b", "", payload,
                  flags=re.IGNORECASE).strip()
    if re.fullmatch(r"-?\d+", _num):
        n = int(_num)
        sign = "-" if n < 0 else ""
        return f"{n} = {sign}0x{abs(n):x} (hex)"
    return f"Hex: {payload.encode('utf-8').hex()}"


_READ_WPM = 200      # silent reading
_SPEAK_WPM = 130     # spoken aloud


def _fmt_min(words: int, wpm: int) -> str:
    secs = round(words / wpm * 60)
    if secs < 60:
        return f"{secs} sec"
    m, s = divmod(secs, 60)
    return f"{m} min {s} sec" if s else f"{m} min"


def reading_time(text: str) -> Optional[str]:
    p = re.sub(r"\b(reading time|padhne|padne|me kitna|kitna time|lagega|"
               r"batao|is text|estimate|read time|kitni der)\b", " ",
               text or "", flags=re.IGNORECASE)
    words = [w for w in re.split(r"\s+", p.strip()) if w]
    n = len(words)
    if n < 10:
        return ("Poora text paste karo — main word count se padhne/bolne ka "
                "time bata dunga.")
    return (f"{n} words. Padhne me ~{_fmt_min(n, _READ_WPM)}, "
            f"bolne me ~{_fmt_min(n, _SPEAK_WPM)}.")


def ascii_value(text: str) -> Optional[str]:
    """Char <-> ASCII/Unicode code point. 'A ka ascii' / '65 ka character'."""
    t = text or ""
    tl = t.lower()
    want_char = bool(re.search(r"\b(char|character|letter|symbol|akshar)\b", tl))
    num = re.search(r"\b(\d{1,7})\b", t)
    if want_char and num:
        code = int(num.group(1))
        if 0 <= code <= 0x10FFFF:
            try:
                ch = chr(code)
                shown = ch if ch.isprintable() else f"(non-printable {code})"
                return f"Code {code} = '{shown}'."
            except ValueError:
                return "Code 0-1114111 ke beech do."
        return "Code 0-1114111 ke beech do."
    # quoted char / single letter -> code
    q = re.search(r"[\"'“”‘’](.)[\"'“”‘’]", t)
    if q:
        ch = q.group(1)
    else:
        # a word to spell out, minus command words
        cmd = {"ascii", "value", "code", "of", "ka", "ki", "ke", "nikaalo",
               "nikalo", "batao", "kya", "hai", "for", "char", "character",
               "unicode", "letter", "the"}
        toks = [w for w in re.findall(r"[A-Za-z0-9!-~]+", t) if w.lower() not in cmd]
        if not toks:
            return ("Kaunsa character ya code? Jaise 'A ka ascii' ya "
                    "'65 ka character'.")
        word = toks[0]
        if len(word) == 1:
            ch = word
        else:
            codes = " ".join(f"{c}={ord(c)}" for c in word)
            return f"'{word}' ASCII codes: {codes}."
    return f"'{ch}' = ASCII/Unicode {ord(ch)}."
