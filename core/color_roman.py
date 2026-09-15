"""Color (hex↔rgb + name) and Roman numeral conversion. Pure stdlib, offline."""
from __future__ import annotations

import re
from typing import Optional

# A small set of common CSS colour names → hex, for "red ka hex batao".
_NAMES = {
    "red": "FF0000", "green": "008000", "blue": "0000FF", "white": "FFFFFF",
    "black": "000000", "yellow": "FFFF00", "orange": "FFA500",
    "purple": "800080", "pink": "FFC0CB", "gray": "808080", "grey": "808080",
    "cyan": "00FFFF", "magenta": "FF00FF", "brown": "A52A2A",
    "lime": "00FF00", "navy": "000080", "teal": "008080", "gold": "FFD700",
    "silver": "C0C0C0", "maroon": "800000", "olive": "808000",
}
_HEX_TO_NAME = {v: k for k, v in _NAMES.items()}


def _clamp(v: int) -> int:
    return max(0, min(255, v))


def convert_color(text: str) -> Optional[str]:
    """hex→rgb, rgb→hex, or name→both."""
    t = (text or "").lower()

    # rgb triple: "255 87 51" or "rgb(255,87,51)" or "255,0,100"
    rgbm = re.search(r"(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})", t)
    hexm = re.search(r"#?\b([0-9a-f]{6}|[0-9a-f]{3})\b", t)
    name = next((n for n in _NAMES if re.search(rf"\b{n}\b", t)), None)

    # Prefer an explicit rgb triple → hex
    if rgbm and "hex" in t or (rgbm and not hexm and not name):
        r, g, b = (_clamp(int(rgbm.group(i))) for i in (1, 2, 3))
        hx = f"{r:02X}{g:02X}{b:02X}"
        nm = _HEX_TO_NAME.get(hx)
        return (f"rgb({r}, {g}, {b}) = #{hx}"
                + (f" ({nm})" if nm else "") + ".")

    if name and not hexm:
        hx = _NAMES[name]
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
        return f"{name} = #{hx} = rgb({r}, {g}, {b})."

    if hexm:
        hx = hexm.group(1)
        if len(hx) == 3:                          # expand shorthand fff→ffffff
            hx = "".join(ch * 2 for ch in hx)
        hx = hx.upper()
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
        nm = _HEX_TO_NAME.get(hx)
        return (f"#{hx} = rgb({r}, {g}, {b})"
                + (f" ({nm})" if nm else "") + ".")

    if rgbm:
        r, g, b = (_clamp(int(rgbm.group(i))) for i in (1, 2, 3))
        hx = f"{r:02X}{g:02X}{b:02X}"
        return f"rgb({r}, {g}, {b}) = #{hx}."
    return None


# ── Roman numerals ───────────────────────────────────────────────────── #

_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
          (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
          (5, "V"), (4, "IV"), (1, "I")]
_ROMAN_VAL = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def to_roman(n: int) -> Optional[str]:
    if not (1 <= n <= 3999):
        return None
    out = []
    for val, sym in _ROMAN:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def from_roman(s: str) -> Optional[int]:
    s = s.strip().upper()
    if not s or any(c not in _ROMAN_VAL for c in s):
        return None
    total, prev = 0, 0
    for c in reversed(s):
        v = _ROMAN_VAL[c]
        total += v if v >= prev else -v
        prev = max(prev, v)
    # round-trip guard rejects malformed strings like "IIII" or "VX"
    if to_roman(total) != s:
        return None
    return total


def convert_roman(text: str) -> Optional[str]:
    t = (text or "").strip()
    rm = re.search(r"\b([MDCLXVI]{1,15})\b", t.upper())
    nm = re.search(r"\b(\d{1,4})\b", t)
    # If a roman-looking token is present AND the intent is decode-ish, decode.
    want_decode = bool(rm) and (not nm or re.search(
        r"kya|decimal|number|value|kitna", t, re.I))
    if rm and want_decode:
        val = from_roman(rm.group(1))
        if val is not None:
            return f"{rm.group(1)} = {val}."
    if nm:
        val = int(nm.group(1))
        rom = to_roman(val)
        if rom:
            return f"{val} = {rom} (roman)."
        return "Roman numerals sirf 1 se 3999 tak hote hain, sir."
    if rm:
        val = from_roman(rm.group(1))
        if val is not None:
            return f"{rm.group(1)} = {val}."
    return None
