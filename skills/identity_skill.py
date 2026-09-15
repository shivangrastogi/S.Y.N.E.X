"""AERIS's own identity — a fast, offline, consistent answer to "who are you",
"what is your name", "tell me about yourself" etc.

Before this, identity questions scattered: "who are you" hit the system whoami
(User/Host/IP), "what is your name" hit get_preference (the USER's name), and
"tell me about yourself" hit a KG recall. This gives one clean self-description
with no LLM dependency and no mis-route.
"""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="who_are_you",
    description="AERIS's own identity — who/what it is and its name (offline).",
    patterns=[
        "who are you", "what are you", "what is your name", "what's your name",
        "tumhara naam kya hai", "tum kaun ho", "aap kaun ho", "tera naam kya hai",
        "tell me about yourself", "introduce yourself", "apne bare me batao",
        "khud ke bare me batao", "tumhare bare me batao", "who is aeris",
        "tum kya ho", "aap kya ho", "your name kya hai",
    ],
    required_entities=[],
)
def who_are_you(_slots: dict) -> str:
    try:
        from core import settings as _s
        name = _s.assistant_name()
    except Exception:
        name = "AERIS"
    return (
        f"Main {name} hoon — Shivang ka fully-offline Hinglish desktop assistant. "
        f"Type ya bol ke diye commands samajhta hoon, screen padh sakta hoon, "
        f"cheezein yaad rakhta hoon, aur 570+ kaam kar sakta hoon — sab kuch "
        f"aapke apne PC pe local, bina internet ke. 'What can you do' bolo to "
        f"poora ability catalog dikhaunga."
    )
