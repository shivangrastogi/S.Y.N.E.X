"""Text statistics — words, chars, sentences, reading time. Pure stdlib."""
from __future__ import annotations

import re
from typing import Optional

_WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
_SENT_RE = re.compile(r"[.!?]+(?:\s|$)")
_WPM = 200   # average reading speed


def analyse(text: str) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    words = _WORD_RE.findall(text)
    n_words = len(words)
    n_chars = len(text)
    n_chars_ns = len(re.sub(r"\s", "", text))
    n_sent = max(1, len(_SENT_RE.findall(text))) if n_words else 0
    n_lines = text.count("\n") + 1
    read_s = n_words / _WPM * 60
    if read_s < 60:
        read = f"{int(round(read_s))} sec"
    else:
        read = f"{read_s / 60:.1f} min"
    avg = n_words / n_sent if n_sent else 0
    return (f"{n_words} words · {n_chars} chars ({n_chars_ns} bina space) · "
            f"{n_sent} sentence · {n_lines} line. "
            f"Padhne mein ~{read} (avg {avg:.0f} words/sentence).")
