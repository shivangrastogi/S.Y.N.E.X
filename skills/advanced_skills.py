"""Advanced skills — screen OCR, mood trend, scratchpad summary.

* ``ocr_screen``           — capture the screen, recognise text via
                              Windows' built-in OCR (Windows.Media.Ocr
                              via winrt), fall back to pytesseract,
                              else helpful install hint.
* ``mood_today``           — average sentiment of recent user messages
                              from the feedback DB. Uses the existing
                              VADER+Hinglish SentimentAnalyzer.
* ``scratchpad_summarize`` — read ``data/scratch.md`` and feed it to
                              the brain as an ai_prompt asking for a
                              3-bullet summary. Useful at end of day.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── ocr_screen ─────────────────────────────────────────────────────── #

def _grab_screen_png() -> Optional[bytes]:
    """Full virtual-screen capture as PNG bytes. Returns None if the
    capture stack is unavailable (rare; needs Pillow ImageGrab).
    """
    try:
        from PIL import ImageGrab
        import io
        img = ImageGrab.grab(all_screens=True)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        log.debug("[ocr] screen grab failed: %s", e)
        return None


def _ocr_via_pytesseract(png: bytes) -> Optional[str]:
    try:
        import pytesseract
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(png))
        return pytesseract.image_to_string(img)
    except Exception as e:
        log.debug("[ocr] pytesseract failed: %s", e)
        return None


def _ocr_via_winrt(png: bytes) -> Optional[str]:
    """Windows.Media.Ocr — bundled with Windows 10/11, supports many
    languages without external installs. Requires the ``winrt`` package.
    """
    if sys.platform != "win32":
        return None
    try:
        import asyncio
        from winrt.windows.media.ocr import OcrEngine  # type: ignore
        from winrt.windows.graphics.imaging import BitmapDecoder  # type: ignore
        from winrt.windows.storage.streams import (  # type: ignore
            InMemoryRandomAccessStream, DataWriter,
        )
    except Exception as e:
        log.debug("[ocr] winrt missing: %s", e)
        return None

    async def _run() -> str:
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(list(png))
        await writer.store_async()
        await writer.flush_async()
        writer.detach_stream()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            return ""
        result = await engine.recognize_async(bitmap)
        return result.text or ""

    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as e:
        log.debug("[ocr] winrt run failed: %s", e)
        return None


@skill(
    name="ocr_screen",
    description="Read the text currently on screen (full virtual screen OCR)",
    patterns=[
        "ocr screen", "read screen", "what's on my screen",
        "screen text", "extract text from screen",
        "screen padho", "screen me kya likha hai",
        "scan screen", "ocr capture",
    ],
)
def ocr_screen(_slots: dict) -> str:
    png = _grab_screen_png()
    if png is None:
        return "Screen capture fail ho gaya. 'pip install pillow' check karo."
    # Prefer winrt (no install needed on modern Win 11) → pytesseract → noop
    text = _ocr_via_winrt(png) or _ocr_via_pytesseract(png)
    if not text:
        return ("OCR backend missing. Options:\n"
                "  - 'pip install winrt' (uses Windows built-in OCR), OR\n"
                "  - install Tesseract + 'pip install pytesseract'")
    text = text.strip()
    if len(text) > 1800:
        text = text[:1800] + f"\n... [truncated, {len(text)} chars total]"
    try:
        import pyperclip
        pyperclip.copy(text)
        copied = " (copied to clipboard)"
    except Exception:
        copied = ""
    return f"Screen text ({len(text)} chars){copied}:\n\n{text}"


# ── mood_today ─────────────────────────────────────────────────────── #

@skill(
    name="mood_today",
    description="Average sentiment of recent user messages (positive/negative trend)",
    patterns=[
        "mood today", "my mood", "sentiment today",
        "kaisa hoon", "mood kaisa hai", "mood check",
        "today's mood", "how am i feeling",
    ],
)
def mood_today(_slots: dict) -> str:
    """The feedback DB already stores ``sentiment_score`` per utterance
    (set by the brain at predict time), so we just average those — no
    need to re-run the analyzer.
    """
    try:
        import sqlite3
        db = os.path.join(_ROOT, "data", "feedback_log.sqlite")
        if not os.path.exists(db):
            return "Feedback DB nahi hai abhi — kuch messages bhej do pehle."
        with sqlite3.connect(db) as conn:
            cur = conn.execute(
                "SELECT sentiment_score FROM utterances "
                "WHERE timestamp >= datetime('now', '-24 hours') "
                "  AND sentiment_score IS NOT NULL "
                "ORDER BY id DESC LIMIT 200"
            )
            scores = [float(r[0]) for r in cur.fetchall() if r and r[0] is not None]
    except Exception as e:
        return f"Feedback DB read fail: {e}"
    if not scores:
        return ("Pichhle 24 ghante me koi scored messages nahi mile — "
                "either kuch bhej do, ya sentiment analyzer disabled hai.")
    avg = sum(scores) / len(scores)
    pos = sum(1 for s in scores if s > 0.1)
    neg = sum(1 for s in scores if s < -0.1)
    neu = len(scores) - pos - neg
    label = "positive" if avg > 0.15 else ("negative" if avg < -0.15 else "neutral")
    bar_width = 16
    # Visual sparkline: latest 16 scores mapped to ▁▂▃▄▅▆▇█
    latest = scores[-bar_width:][::-1]
    blocks = "▁▂▃▄▅▆▇█"
    spark = "".join(blocks[min(7, max(0, int((s + 1) / 2 * 8)))] for s in latest)
    return (f"Mood ({len(scores)} messages, last 24h): {label}  ·  "
            f"avg {avg:+.2f}  ·  {pos}↑ {neu}— {neg}↓\n"
            f"trend: {spark}")


# ── scratchpad_summarize ───────────────────────────────────────────── #

@skill(
    name="scratchpad_summarize",
    description="Summarise data/scratch.md into 3 bullets via the brain",
    patterns=[
        "summarize scratch", "summarise scratchpad", "scratch summary",
        "summarize my notes", "notes summary",
        "scratch summarize karo", "notes summarize karo",
    ],
)
def scratchpad_summarize(_slots: dict) -> str:
    path = os.path.join(_ROOT, "data", "scratch.md")
    if not os.path.exists(path):
        return "scratch.md nahi mila. 'note this: …' se pehle kuch likho."
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
    except Exception as e:
        return f"Read fail: {e}"
    if not text:
        return "scratch.md khaali hai."
    if len(text) > 6000:
        text = text[-6000:]   # keep the most recent context
    # Hand off to the brain via the automation engine's ai_prompt path so
    # the answer lands in the chat panel like any other AI reply.
    prompt = (
        "Here are my recent scratchpad notes:\n\n" + text +
        "\n\nGive me a 3-bullet summary of what I've been thinking about. "
        "Be concise."
    )
    try:
        from core.automation import get_engine
        eng = get_engine()
        if eng._ai_prompt_handler:
            eng._ai_prompt_handler(prompt)
            return f"Summarising {len(text)} chars of scratchpad — answer coming in chat."
    except Exception:
        pass
    return ("Brain handler not wired (headless mode). "
            f"Scratchpad has {len(text)} chars — prompt prepared.")
