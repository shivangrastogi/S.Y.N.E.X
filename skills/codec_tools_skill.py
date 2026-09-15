"""Hex encode-decode + reading-time. Pure stdlib, offline.

(Base64 already lives in compute_skills; here we add hex + reading-time.)
"""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="hex_convert",
    description="Encode or decode text to/from hexadecimal (offline).",
    patterns=[
        "hex encode karo", "hex me convert karo", "hex decode karo",
        "isko hex me badlo", "hexadecimal nikaalo", "hex se wapas karo",
        "text ko hex banao",
    ],
    required_entities=[],
)
def hex_convert(slots: dict) -> str:
    from core.codec_tools import hex_convert as _hex
    return _hex(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="reading_time",
    description="Estimate reading/speaking time for a block of text (offline).",
    patterns=[
        "reading time batao", "is text ko padhne me kitna time",
        "padhne me kitni der lagegi", "read time estimate karo",
        "bolne me kitna time lagega", "kitni der me padh lunga",
    ],
    required_entities=[],
)
def reading_time(slots: dict) -> str:
    from core.codec_tools import reading_time as _rt
    return _rt(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="ascii_value",
    description="Convert a character to its ASCII/Unicode code or back (offline).",
    patterns=[
        "A ka ascii value kya hai", "ascii code nikaalo",
        "65 ka character kya hai", "is letter ka ascii",
        "character ka unicode batao", "code se character nikaalo",
    ],
    required_entities=[],
)
def ascii_value(slots: dict) -> str:
    from core.codec_tools import ascii_value as _av
    return _av(slots.get("raw_text") or slots.get("text") or "")
