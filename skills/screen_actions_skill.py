"""Screen ACTIONS skills — scroll / type / smart-click on what's visible.

Companion to click_text (which now uses core.screen_actions too). These
let AERIS act on the screen it can see:

    "neeche scroll karo"          → scroll down
    "type karo hello@example.com" → type into the focused field
    "jahan se send kar sakta hoon wahan click karo" → LLM picks + clicks
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="screen_scroll",
    description="Scroll the current window up or down.",
    patterns=[
        "neeche scroll karo", "upar scroll karo", "scroll down karo",
        "scroll up karo", "page neeche karo", "page upar karo",
        "thoda neeche scroll", "thoda upar scroll", "scroll down", "scroll up",
    ],
    required_entities=[],
)
def screen_scroll(slots: dict) -> str:
    raw = (slots.get("raw_text") or slots.get("text") or "").lower()
    direction = "up" if ("upar" in raw or "up" in raw) and \
        not ("neeche" in raw or "down" in raw or "niche" in raw) else "down"
    from core.screen_actions import scroll
    return scroll(direction)


@skill(
    name="type_on_screen",
    description="Type text into the currently focused field.",
    patterns=[
        "type karo", "ye likho", "yeh type karo", "screen pe likho",
        "field mein likho", "type this", "keyboard se likho",
    ],
    required_entities=[],
)
def type_on_screen(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    text = raw
    for kw in ("type karo", "yeh type karo", "ye likho", "screen pe likho",
               "field mein likho", "type this", "keyboard se likho", "likho"):
        m = re.search(re.escape(kw), text, re.IGNORECASE)
        if m:
            text = text[m.end():].strip(" :,-")
            break
    if not text:
        return "Kya type karna hai? 'type karo <text>' bolo."
    from core.screen_actions import type_text
    return type_text(text)


@skill(
    name="smart_click",
    description="Click the on-screen element that matches a described "
                "intent (LLM decides which, then clicks).",
    patterns=[
        "jahan se message bhej sakta hoon wahan click karo",
        "jo button send karta hai wo dabao",
        "click the button that lets me continue",
        "screen pe jo relevant hai wahan click karo",
        "samajh ke click karo",
    ],
    required_entities=[],
)
def smart_click(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    from core.screen_actions import smart_click as _sc
    return _sc(raw)
