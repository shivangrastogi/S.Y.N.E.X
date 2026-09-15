"""Screen-Aware Agent — AERIS sees your screen, understands it, helps.

The thing generic assistants can't do: look at whatever is ON your
screen (any app, any window), read it (OCR), and reason about it with the
local LLM — fully offline, Hinglish-native.

    "ye error kya hai?"          → reads the actual error on screen, explains
    "is email ka reply likho"    → reads the email, drafts a reply
    "ye page summarise karo"     → reads the article, 3-bullet summary
    "screen pe kya ho raha hai"  → describes what you're looking at

Pipeline:
    capture full screen → OCR (eng+hin) → + active window (app/title)
    → local LLM with a screen-grounded prompt → answer.

Everything local: mss/pytesseract for sight, core.local_llm for thought.
No screenshot ever leaves the machine.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

# OCR can be long + noisy; cap what we feed the small local model. Smaller
# = much faster prefill on CPU (the 1.5B model's prompt-read dominates
# latency). ~1200 chars keeps the salient text while staying snappy.
_MAX_SCREEN_CHARS = 1200

_SYSTEM = (
    "You are AERIS, {user}'s desktop assistant with EYES — you see the "
    "user's screen (OCR text below) and the active app. Answer ONLY the "
    "user's question, grounded in the screen text. Rules: max 2 sentences; "
    "do NOT restate the question; do NOT invent text not in the OCR; if the "
    "OCR lacks the answer, say 'screen pe ye clearly nahi dikh raha'. Warm "
    "desi-English (sir/yaar ok)."
)


def _grab_screen_text() -> str:
    """Full-screen OCR text, or '' if capture/OCR unavailable."""
    try:
        from skills.snip_ocr import _capture_full_screen, _ocr
        img = _capture_full_screen()
        if img is None:
            return ""
        return _ocr(img) or ""
    except Exception as e:
        log.info("[screen_agent] OCR unavailable: %s", e)
        return ""


def _active_app() -> str:
    try:
        from skills.windows_power_utils import _foreground_info
        title, proc, _pid = _foreground_info()
        proc = (proc or "").replace(".exe", "")
        if title and proc:
            return f"{proc} — “{title[:80]}”"
        return proc or title or "unknown"
    except Exception:
        return "unknown"


def _clean_ocr(text: str) -> str:
    # Collapse blank lines / stray whitespace the OCR leaves behind.
    lines = [ln.strip() for ln in (text or "").splitlines()]
    lines = [ln for ln in lines if ln]
    joined = "\n".join(lines)
    if len(joined) > _MAX_SCREEN_CHARS:
        # Keep the head (usually the meaningful content) + note the trim.
        joined = joined[:_MAX_SCREEN_CHARS] + "\n…[screen text trimmed]"
    return joined


def assist(question: str, user_name: str = "sir") -> str:
    """Answer ``question`` grounded in what's currently on screen.

    Returns a user-facing string. Degrades gracefully: no OCR → says it
    can't see; no LLM → returns the raw screen text so it's still useful.
    """
    screen = _clean_ocr(_grab_screen_text())
    app = _active_app()

    if not screen:
        return ("Screen padh nahi paaya — OCR available nahi hai (Tesseract "
                "install/PATH check karo). Tab tak main sun ke madad kar "
                "sakta hoon.")

    try:
        from core import local_llm
        llm = local_llm.get()
        if not llm.available():
            # No model — still useful: hand back what we saw.
            return (f"[{app}] screen pe ye dikha:\n\n{screen[:600]}"
                    "\n\n(Poora samajhne ke liye local LLM chahiye — "
                    "data/models/llm/ mein .gguf daalo.)")
        messages = [
            {"role": "system", "content": _SYSTEM.format(user=user_name)},
            {"role": "user", "content":
                f"Active app: {app}\n\n"
                f"--- SCREEN TEXT (OCR) ---\n{screen}\n--- END SCREEN ---\n\n"
                f"Question: {question.strip() or 'Screen pe kya ho raha hai?'}"},
        ]
        reply = llm.chat(messages, max_tokens=140)
        return reply or "Screen dekh liya par jawab banane mein dikkat aa gayi."
    except Exception as e:
        log.warning("[screen_agent] assist failed: %s", e)
        return f"Screen samajhne mein error: {e}"


def peek() -> str:
    """One-liner: what app + how much text is visible (cheap, no LLM)."""
    txt = _grab_screen_text()
    return (f"Active: {_active_app()} · {len(txt.split())} words visible"
            if txt else f"Active: {_active_app()} · screen OCR unavailable")
