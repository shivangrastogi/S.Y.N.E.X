"""Voice-capture gating + processing-watchdog policy.

Two robustness problems with always-on voice:

  1. **Noise enters processing.** A half-heard / garbled capture is non-empty
     but meaningless ("uh", "mm", a one-letter blip). Sending it to the brain
     flips the UI into PROCESSING for nothing. ``is_meaningful_capture`` is the
     filter: junk stays in LISTENING, the mic keeps streaming.

  2. **Processing can hang.** If ``process_text`` blocks (slow LLM, agentic
     loop, a wedged skill) with no timeout, the UI is stranded in PROCESSING and
     the user can't talk again. ``processing_timeout_s`` is the watchdog budget
     after which the GUI force-resets to LISTENING.

Pure functions — no Qt, no mic — so the policy is unit-testable. The GUI wires
them into ``_on_voice_captured`` (filter) and a ``QTimer`` (watchdog).
"""
from __future__ import annotations

import re

# Words that, if they're *all* a capture contains, mean "nothing was really
# said" — disfluencies and mic blips in English + common Hinglish.
_FILLER = {
    "uh", "uhh", "um", "umm", "hmm", "hm", "mm", "mmm", "ah", "ahh", "er",
    "err", "eh", "oh", "huh", "haa", "ha", "haan", "han", "haa", "arre",
    "aa", "aaa", "the", "a", "so", "like",
}

_TOKEN_RE = re.compile(r"[a-z0-9ऀ-ॿ]+")   # latin + devanagari runs

DEFAULT_PROCESSING_TIMEOUT_S = 12.0
_MIN_CHARS = 2


def is_meaningful_capture(text: str | None, min_chars: int = _MIN_CHARS) -> bool:
    """True if a capture is worth sending to the brain.

    Rejects empty strings, sub-``min_chars`` blips, and captures made up
    *entirely* of filler/disfluency tokens. A capture that mixes filler with
    a real word ("um open chrome") passes — the brain handles the filler.
    """
    if not text:
        return False
    t = text.strip().lower()
    if len(t) < min_chars:
        return False
    words = _TOKEN_RE.findall(t)
    if not words:
        return False
    if all(w in _FILLER for w in words):
        return False
    return True


def processing_timeout_s(
    text: str | None = None,
    *,
    base: float = DEFAULT_PROCESSING_TIMEOUT_S,
    llm_possible: bool = True,
) -> float:
    """Watchdog budget (seconds) for a single PROCESSING turn.

    Longer utterances and LLM-eligible ones (multi-step / chit-chat) get more
    headroom; a short command that should resolve via a local skill gets the
    base. Always bounded so the UI can never hang indefinitely.
    """
    budget = base
    if text and len(text) > 60:
        budget += 4.0            # long phrase → likely a heavier request
    if not llm_possible:
        budget = min(budget, 6.0)  # no LLM path → local skills are fast
    # Screen-aware assist runs full-screen OCR + a local-LLM pass over the
    # screen text — ~60-90s on CPU. Give it a big budget so the watchdog
    # doesn't reset the UI mid-think.
    low = (text or "").lower()
    if any(k in low for k in ("screen", "error kya", "is page",
                              "email ka reply", "iska matlab", "samjhao")):
        return 120.0
    return max(3.0, min(budget, 30.0))
