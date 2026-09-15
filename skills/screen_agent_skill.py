"""Screen-Aware Agent skill — "AERIS, dekh ke bata/kar do".

Routes screen-grounded questions to core.screen_agent, which captures +
OCRs the screen and reasons about it with the local LLM.

    "ye error kya hai"        "is page ko summarise karo"
    "screen pe kya likha hai"  "ye email formal hai kya"
    "iska matlab kya hai"      "screen dekh ke batao"
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)

# Trigger prefixes stripped off to recover the real question. Longest
# first so "screen dekh ke batao" beats "batao".
_STRIP = [
    "screen dekh ke batao", "screen dekh kar batao", "screen dekh ke",
    "screen padh ke batao", "screen ko dekh ke", "dekh ke batao",
    "look at my screen and", "look at the screen and", "read my screen and",
    "screen assist", "screen help", "help me with this screen",
    "screen pe", "screen par", "on my screen", "on screen",
]


def _extract_question(raw: str) -> str:
    q = (raw or "").strip()
    low = q.lower()
    for p in _STRIP:
        if low.startswith(p):
            return q[len(p):].strip(" ,:-") or q
        if low.endswith(p):
            return q[: len(q) - len(p)].strip(" ,:-") or q
    return q


@skill(
    name="screen_assist",
    description="Look at the screen (OCR + vision) and answer/help about "
                "whatever is on it — errors, emails, pages, code, forms.",
    patterns=[
        "screen dekh ke batao", "ye error kya hai", "is error ko theek karo",
        "screen pe kya likha hai iska matlab", "iska matlab kya hai screen pe",
        "is page ko summarise karo", "ye page kya keh raha hai",
        "screen dekh ke help karo", "look at my screen", "read my screen and help",
        "what is on my screen", "explain what is on screen",
        "is email ka reply likho", "ye email kaisa hai",
        "screen samjhao", "ye kya ho raha hai screen pe",
        "screen assist", "help me with this screen",
    ],
    required_entities=[],
)
def screen_assist(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    question = _extract_question(raw)
    try:
        from core import screen_agent
        from core import settings as _settings
        try:
            user = _settings.get("user_name") or _settings.get("name") or "sir"
        except Exception:
            user = "sir"
        return screen_agent.assist(question, user_name=str(user))
    except Exception as e:
        log.warning("[screen_assist] failed: %s", e)
        return f"Screen dekhne mein dikkat: {e}"


@skill(
    name="screen_peek",
    description="Quick note of what app is active and how much text is on "
                "screen (no LLM — instant).",
    patterns=[
        "screen peek", "what app am i on", "screen pe kitna text hai",
        "abhi kya khula hai screen pe",
    ],
    required_entities=[],
)
def screen_peek(_slots: dict) -> str:
    from core import screen_agent
    return screen_agent.peek()
