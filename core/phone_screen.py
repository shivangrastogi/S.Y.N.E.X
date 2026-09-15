"""Laptop-side handling of the PHONE's screen (Phase 3 — bidirectional).

The phone captures its own screen (MediaProjection) and sends it as a
JPEG over the bridge. This module:

  * holds the pending question ("phone pe kya notification hai") so when
    the async image arrives we know what to answer;
  * ``analyze(jpeg_bytes, question)`` — OCRs the phone image (tesseract)
    and answers with the local LLM, exactly like the laptop screen agent
    but on the phone's pixels.

The GUI registers a bridge ``on_phone_screen`` callback that shows the
image AND, if a question is pending, runs ``analyze`` and surfaces the
answer.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

log = logging.getLogger(__name__)

_lock = threading.Lock()
_pending_q: Optional[str] = None


def set_pending_question(q: Optional[str]) -> None:
    global _pending_q
    with _lock:
        _pending_q = (q or "").strip() or None


def pop_pending_question() -> Optional[str]:
    global _pending_q
    with _lock:
        q, _pending_q = _pending_q, None
        return q


def _ocr_jpeg(jpeg: bytes) -> str:
    try:
        import io
        from PIL import Image
        import pytesseract
        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        # Phone screens are tall/narrow with small text — upscale helps.
        if img.width < 1400:
            f = 1400 / img.width
            img = img.resize((int(img.width * f), int(img.height * f)),
                             Image.LANCZOS)
        try:
            return pytesseract.image_to_string(img, lang="eng+hin").strip()
        except Exception:
            return pytesseract.image_to_string(img, lang="eng").strip()
    except Exception as e:
        log.info("[phone_screen] OCR failed: %s", e)
        return ""


_SYSTEM = (
    "You are AERIS. You are shown the OCR'd text of the user's PHONE "
    "screen. Answer the user's question about it in 1-2 short sentences, "
    "grounded ONLY in that text. If it's not there, say so. Warm "
    "desi-English."
)


def analyze(jpeg: bytes, question: str, user_name: str = "sir") -> str:
    """OCR the phone screen JPEG + answer ``question`` via the local LLM."""
    text = _ocr_jpeg(jpeg)
    if not text:
        return "Phone screen padh nahi paaya (OCR khali)."
    if len(text) > 1600:
        text = text[:1600] + " …[trimmed]"
    try:
        from core import local_llm
        llm = local_llm.get()
        if not llm.available():
            return f"Phone screen pe ye dikha:\n{text[:500]}"
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content":
                f"--- PHONE SCREEN (OCR) ---\n{text}\n--- END ---\n\n"
                f"Question: {question or 'Phone screen pe kya hai?'}"},
        ]
        return llm.chat(messages, max_tokens=140) or \
            f"Phone screen pe:\n{text[:400]}"
    except Exception as e:
        log.warning("[phone_screen] analyze failed: %s", e)
        return f"Phone screen samajhne mein error: {e}"
