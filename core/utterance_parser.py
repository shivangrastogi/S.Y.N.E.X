"""Smart utterance parsing — multi-command splitter + subspan scanner.

Two brain-native techniques that let JarvisMainEngine handle:

  1. Filler words ("bhai", "ek kam karo", "please", "jarvis", "yaar")
     The encoder gets confused when noise words pull cosine similarity toward
     the wrong intent. We try several trimmed variants and let the brain pick
     the highest-confidence interpretation. No hand-curated stopword list.

  2. Multi-command utterances ("brave aur chrome aur file explorer open karo")
     Split the utterance on conjunctions and dispatch each segment separately.
     If only the LAST segment carries the verb ("open karo"), the verb is
     re-attached to the earlier verb-less segments by re-running the brain on
     "<segment> <tail-verb>" and keeping it if confidence improves.

Public surface:
    split_into_segments(text)            -> list[str]
    find_best_interpretation(text, brain) -> (Prediction, str)
    parse(text, brain)                    -> list[(Prediction, str)]
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from core.intent_classifier import Prediction

log = logging.getLogger(__name__)


# Conjunctions that separate independent commands.
# Order matters: longer multiword joiners checked first via regex alternation.
_SPLIT_PATTERN = re.compile(
    r"\s*(?:,|\bphir\b|\bthen\b|\bafter that\b|\bbaad mein\b|\baur\b|\band\b)\s+",
    re.IGNORECASE,
)

# Maximum subspan variants we try per segment. Each variant is one extra
# encoder call (~10ms), so 6 variants ≈ +60ms per utterance — imperceptible.
_MAX_VARIANTS = 6

# Minimum confidence floor below which a "winning" subspan is treated as
# garbage (so a filler-only segment like "bhai" gets dropped, not executed).
_MIN_VIABLE_CONFIDENCE = 0.45


# ---------------------------------------------------------------------- #
#  Multi-command splitter                                                 #
# ---------------------------------------------------------------------- #

def split_into_segments(text: str) -> list[str]:
    """Split utterance on conjunctions; reattach trailing verb to verb-less heads.

    Examples:
        "chrome kholo aur notepad band karo"
            -> ["chrome kholo", "notepad band karo"]

        "brave aur chrome aur file explorer open karo"
            -> ["brave open karo", "chrome open karo", "file explorer open karo"]

        "weather batao"
            -> ["weather batao"]                # single command, untouched

        "bhai weather batao"
            -> ["bhai weather batao"]           # filler stays; subspan scanner
                                                # will trim it during prediction
    """
    if not text or not text.strip():
        return []

    raw_segments = [s.strip() for s in _SPLIT_PATTERN.split(text.strip()) if s.strip()]
    if len(raw_segments) <= 1:
        return raw_segments or [text.strip()]

    tail_verb = _trailing_verb_phrase(raw_segments[-1])
    if not tail_verb:
        return raw_segments

    # Heuristic: if an earlier segment is short and doesn't already contain a
    # verb-like word, it's a bare noun ("brave", "chrome") — graft the tail
    # verb onto it so the brain can recognise it as the same kind of command.
    rebuilt: list[str] = []
    for seg in raw_segments[:-1]:
        if _looks_like_bare_noun(seg):
            rebuilt.append(f"{seg} {tail_verb}")
        else:
            rebuilt.append(seg)
    rebuilt.append(raw_segments[-1])
    return rebuilt


# A small list of imperative verb roots commonly used in Hinglish commands.
# Used only to detect whether a segment already carries a verb — NOT to drive
# intent classification (the brain still does that semantically).
_VERB_HINTS = (
    "kholo", "kholna", "khol", "open", "launch",
    "band", "close", "hatao", "stop", "ruko", "rok",
    "chala", "chalu", "chalao", "chal", "play", "bajao",
    "batao", "bata", "tell", "dikhao", "dikha", "show",
    "lo", "le", "lelo", "take", "capture",
    "karo", "kar", "kardo", "do",
    "search", "dhundo", "dhund", "find",
    "lock", "shutdown", "restart", "reboot",
    "increase", "badhao", "badha", "decrease", "kam", "ghata",
    "mute", "unmute",
    "set", "lagao", "laga",
    "schedule", "book", "fix",
    "calculate", "compute", "solve",
    "remind", "yaad",
    "save", "likh", "write", "note",
)


def _trailing_verb_phrase(segment: str) -> Optional[str]:
    """Extract the contiguous trailing run of verb-like words.

    Walks backward from the end of the segment and stops at the first word
    that ISN'T verb-like, so for "file explorer open karo" we return just
    "open karo" — not "explorer open karo". Critical for verb-grafting:
    if we leak nouns into the tail, they pollute every earlier segment.
    """
    tokens = segment.split()
    if not tokens:
        return None

    tail: list[str] = []
    for tok in reversed(tokens):
        if tok.lower() in _VERB_HINTS:
            tail.insert(0, tok)
        else:
            break

    if not tail:
        return None
    # Cap at 3 words — anything longer is probably overcapture.
    return " ".join(tail[-3:])


def _looks_like_bare_noun(segment: str) -> bool:
    """True if segment has no verb-like word — so it needs a verb grafted on."""
    tokens = [t.lower() for t in segment.split()]
    if not tokens:
        return False
    if len(tokens) > 4:
        return False
    return not any(t in _VERB_HINTS for t in tokens)


# ---------------------------------------------------------------------- #
#  Subspan scanner                                                        #
# ---------------------------------------------------------------------- #

def _candidate_spans(text: str) -> list[str]:
    """Generate up to _MAX_VARIANTS subspans of `text` to try against the brain.

    Strategy: keep the full text plus aggressive trims of leading/trailing
    fillers. Word-bounded, never goes below 1 token.
    """
    tokens = text.split()
    n = len(tokens)
    if n <= 2:
        return [text]

    seen: list[str] = []

    def add(words: list[str]) -> None:
        if not words:
            return
        s = " ".join(words).strip()
        if s and s not in seen:
            seen.append(s)

    add(tokens)                       # full
    add(tokens[1:])                   # drop 1 leading
    if n >= 4:
        add(tokens[2:])               # drop 2 leading
    add(tokens[:-1])                  # drop 1 trailing
    if n >= 4:
        add(tokens[:-2])              # drop 2 trailing
    if n >= 5:
        add(tokens[1:-1])             # drop 1 each side

    return seen[:_MAX_VARIANTS]


def find_best_interpretation(text: str, brain) -> tuple[Prediction, str]:
    """Try several subspans of `text`; return (best Prediction, winning span).

    "Best" = highest top-1 cosine confidence. Threshold is 0 here — we're
    just picking the strongest interpretation. The caller (main_engine) still
    applies the per-intent bandit threshold to decide whether to act on it.
    """
    if not text or not text.strip():
        return brain.predict(text, threshold=0.0), text

    candidates = _candidate_spans(text.strip())
    best_pred: Optional[Prediction] = None
    best_span: str = text.strip()

    for span in candidates:
        pred = brain.predict(span, threshold=0.0)
        if best_pred is None or pred.confidence > best_pred.confidence:
            best_pred = pred
            best_span = span

    assert best_pred is not None
    return best_pred, best_span


# ---------------------------------------------------------------------- #
#  Top-level convenience                                                  #
# ---------------------------------------------------------------------- #

def parse(text: str, brain) -> list[tuple[Prediction, str]]:
    """End-to-end: split into segments, pick best subspan per segment.

    Drops segments where every subspan stays below _MIN_VIABLE_CONFIDENCE —
    those are pure filler ("bhai", "haan", "hmm") and shouldn't trigger any
    intent execution.

    Returns a list of (Prediction, winning_span_text) pairs, one per
    surviving segment, in the same order they were spoken.
    """
    segments = split_into_segments(text)
    out: list[tuple[Prediction, str]] = []
    for seg in segments:
        pred, span = find_best_interpretation(seg, brain)
        if pred.confidence >= _MIN_VIABLE_CONFIDENCE:
            out.append((pred, span))
    return out


if __name__ == "__main__":
    # Smoke test (requires brain — slow first time due to encoder load).
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from core.brain import JarvisBrain

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    brain = JarvisBrain()

    cases = [
        "chrome kholo",
        "ek kam karo notepad open karo",
        "open notepad bhai",
        "bhai jarvis weather batao please",
        "brave aur chrome aur file explorer open karo",
        "chrome kholo aur notepad band karo",
        "weather batao aur time batao",
        "haan bhai",  # pure filler — should drop out
    ]
    for t in cases:
        print(f"\nINPUT: {t!r}")
        print(f"  segments: {split_into_segments(t)}")
        results = parse(t, brain)
        for pred, span in results:
            print(f"    -> span={span!r}  intent={pred.intent}  conf={pred.confidence:.3f}")
        if not results:
            print("    -> (no viable segment — dropped)")
