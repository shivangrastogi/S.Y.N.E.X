"""Laptop sees the PHONE's screen (Phase 3 — bidirectional awareness).

  * phone_screen_show  — "phone screen dikhao" → phone captures + sends
                         its screen; the laptop shows it in the chat.
  * phone_screen_ask   — "phone pe kya notification hai" → same, but the
                         laptop OCRs it + answers your question.

The image arrives asynchronously (the phone captures then sends), so
these skills kick off the request; the GUI's on_phone_screen callback
renders the image / answer when it lands.
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _paired() -> bool:
    try:
        from core.cloud_bridge import get_bridge
        return bool(get_bridge().status().get("paired"))
    except Exception:
        return False


@skill(
    name="phone_screen_show",
    description="Ask the phone to capture and show its screen on the laptop.",
    patterns=[
        "phone screen dikhao", "phone ki screen dikhao",
        "show me my phone screen", "mera phone screen dikhao",
        "phone screen mirror karo", "phone display dikhao",
    ],
    required_entities=[],
)
def phone_screen_show(_slots: dict) -> str:
    if not _paired():
        return "Koi phone paired nahi — pehle 'phone pair karo'."
    from core import phone_screen
    from core.cloud_bridge import get_bridge
    phone_screen.set_pending_question(None)     # just show, don't analyse
    b = get_bridge()
    # Phase 5b: WebRTC first (smooth, like the other direction). Falls back to
    # the old JPEG stream if WebRTC can't start. Stop with "screen share band
    # karo" or the phone's Exit.
    if b.start_phone_webrtc():
        return ("Phone screen live aa rahi hai 📲 (WebRTC — smooth) — ek "
                "window mein dikhegi. Phone pe screen-record permission "
                "allow karna. Rokne ke liye 'screen share band karo'.")
    b.start_phone_stream()
    return ("Phone screen live aa rahi hai 📲 (fallback) — ek window mein "
            "dikhegi. Rokne ke liye 'screen share band karo'.")


@skill(
    name="phone_screen_ask",
    description="Ask a question about what's on the phone screen — laptop "
                "captures the phone screen, OCRs it, and answers.",
    patterns=[
        "phone pe kya notification hai", "phone screen pe kya hai",
        "phone pe kya likha hai", "phone screen padho",
        "what is on my phone screen", "phone pe kya khula hai",
        "phone screen samjhao", "read my phone screen",
    ],
    required_entities=[],
)
def phone_screen_ask(slots: dict) -> str:
    if not _paired():
        return "Koi phone paired nahi — pehle 'phone pair karo'."
    raw = (slots.get("raw_text") or slots.get("text") or "").strip()
    # keep the whole utterance as the question — analyze() handles it.
    from core import phone_screen
    from core.cloud_bridge import get_bridge
    phone_screen.set_pending_question(raw or "Phone pe kya hai?")
    get_bridge().request_phone_screen()
    return ("Phone screen dekh raha hoon 📲 — capture aate hi jawab dunga. "
            "(Phone app khula + capture-permission allowed hona chahiye.)")
