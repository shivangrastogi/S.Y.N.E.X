"""Text statistics by voice — words, chars, sentences, reading time. Offline.

Analyses the text after the command phrase, or the clipboard when none is
given (distinct from clipboard_stats: this adds sentences + reading time).
"""
from __future__ import annotations

import re

from core.skill_registry import skill

_STRIP = re.compile(
    r".*?(?:kitne\s*words?|word\s*count|text\s*stats?|reading\s*time|"
    r"kitne\s*shabd|padhne\s*me?in?\s*kitna|shabd\s*gino)\s*"
    r"(?:hain|batao|karo|nikalo|of|for|ka|ki|is\s*(?:text|paragraph)\s*ka)?\s*[:\-]?\s*",
    re.IGNORECASE)


@skill(
    name="text_stats",
    description="Count words/chars/sentences + reading time of given text or clipboard (offline).",
    patterns=[
        "is text me kitne words hain", "text stats batao",
        "reading time kitna hai", "word count karo is text ka",
        "kitne words hain", "paragraph me kitne shabd",
        "clipboard ki reading time", "is paragraph ka word count",
    ],
    required_entities=[],
)
def text_stats(slots: dict) -> str:
    from core.text_stats import analyse
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _STRIP.sub("", raw).strip(" :\"'")
    # Short/empty leftover → the user means the clipboard.
    if len(body) < 12:
        try:
            import pyperclip
            body = (pyperclip.paste() or "").strip()
        except Exception:
            body = ""
    out = analyse(body)
    if not out:
        return ("Text do ya kuch copy karke bolo — main words, sentences "
                "aur reading time bata dunga.")
    return out
