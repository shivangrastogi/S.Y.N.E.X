"""Learn from a rephrase, in the same session (P3 "Self-correction").

The routing audit measured that only ~50% of natural core-command phrasings
reach the right intent. The structural fix is a corpus trim + retrain, which is
the user's call and takes a training run. This module fixes a different half of
the same problem, and fixes it *immediately*:

    "chrome band karo"   → samajh nahi paaya          (miss)
    "close chrome"       → Chrome band kar diya       (hit)
    ‹later, same session or next week›
    "chrome band karo"   → Chrome band kar diya       ← learned

Today AERIS already notices corrections (`core/feedback.py`), but what it does
with them is (a) nudge a per-intent acceptance *threshold* and (b) queue the
utterance for manual approval into `intents.json`, which only takes effect
**on the next boot** after a human approves it. Neither makes the failed
phrasing work now. That gap is exactly what P3 asks for, and it is what this
module closes: a phrase→intent alias consulted at the very top of the router.

### Precision is the whole design

A learned alias is a permanent, exact-match reroute. A wrong one doesn't
degrade gracefully — it silently sends a phrase to the wrong skill forever,
which is strictly worse than the miss it replaced. So every rule here is biased
toward *not* learning:

* the previous turn must have actually **missed** — not merely be the previous turn;
* the repair must **succeed confidently** (``min_conf``), and not itself be a repair;
* it must arrive **soon** (``window_s``) — a rephrase is immediate, and anything
  later is the user moving on to something else;
* the two phrasings must be **related** (share a content word) — unless the user
  said "galat"/"wrong" in between, which is an unambiguous repair marker and
  buys back the recall the overlap test costs;
* the phrase must be **reusable at all** — no digits, not too long.

That last one matters more than it looks. "remind me at 4:30 to call mom" is
not a phrasing, it is a one-off; and learning "2 plus 2 → calculate" would be
useless next time the user says "5 plus 7". Volatile utterances are exactly the
ones an alias table cannot help, so it declines them rather than filling up
with garbage. Math routing is a corpus problem and stays one.

The cost of this bias is real and worth naming: a translation-style rephrase
("mausam kaisa hai" → "weather batao") shares no token and will be **declined**
unless the user explicitly said "galat" first. Missing a learnable alias is a
recoverable disappointment. Learning a wrong one is not.

### Self-repairing

An alias that leads to a miss is deleted on the spot (``from_alias=True`` on
the next ``note_turn``). So a rule that was right once and wrong later removes
itself rather than needing a human to notice.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

log = logging.getLogger(__name__)

SCHEMA = 1
DEFAULT_PATH = os.path.join("data", "repair_memory.json")

WINDOW_S = 90.0         # a rephrase is immediate; later is a new topic
MIN_CONF = 0.65         # the repair must be a confident route, not a guess
MAX_ALIASES = 200       # bounded, LRU by last use
MIN_TOKENS = 2          # one word is too ambiguous to alias
MAX_TOKENS = 8          # longer than this is an utterance, not a phrasing

# Words that carry no topic. Overlap on these would let "chrome band karo" and
# "gaana chala do" look related through "karo"/"do".
_FILLER = {
    "karo", "kar", "kro", "do", "de", "dedo", "dena", "please", "plz", "pls",
    "aeris", "jarvis", "hey", "ok", "okay", "the", "a", "an", "to", "for",
    "me", "my", "mujhe", "mera", "meri", "ye", "yeh", "wo", "woh", "is", "us",
    "hai", "he", "ho", "hu", "hun", "na", "ab", "zara", "bhai", "sir", "ji",
    "please", "can", "you", "could", "would", "will", "just", "now", "abhi",
    "and", "or", "of", "it", "this", "that", "kya", "kaise", "kar", "bhi",
}

# Unambiguous "that was wrong" markers. Kept in sync with main_engine's
# _CORRECTION_KEYWORDS in spirit, but matched as a substring-free exact phrase
# so a sentence merely containing "wrong" isn't treated as a correction.
_CORRECTION_MARKERS = {
    "galat", "galat hai", "yeh galat hai", "ye galat hai", "wrong",
    "that's wrong", "thats wrong", "no that's wrong", "nahi", "nahi nahi",
    "undo", "wapas", "galti", "not that", "yeh nahi", "ye nahi",
}


# Process-wide handle on the engine's RepairMemory, mirroring
# `core.conversation.set_active`. The `learned_phrasings` skill consults it at
# handler time; it stays None when self-correction is off or no engine is
# attached (pytest), and skills must degrade cleanly rather than assume it.
_ACTIVE: Optional["RepairMemory"] = None


def set_active(mem: Optional["RepairMemory"]) -> None:
    global _ACTIVE
    _ACTIVE = mem


def get_active() -> Optional["RepairMemory"]:
    return _ACTIVE


@dataclass
class Alias:
    intent: str
    slots: dict = field(default_factory=dict)
    learned_at: float = 0.0
    source: str = "implicit"      # "implicit" | "explicit"
    hits: int = 0
    last_used: float = 0.0


def _fallback_clean(text: str) -> str:
    import re
    t = (text or "").strip().lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _default_normalizer() -> Callable[[str], str]:
    """The repo's canonical cleaner, with a local fallback.

    Using `HinglishNormalizer` matters for correctness, not tidiness: the
    router normalises before matching, so an alias table keyed on anything else
    would miss on exactly the shorthand ("plz", repeated letters) the
    normaliser exists to fold together.
    """
    try:
        from core.normalizer import HinglishNormalizer
        return HinglishNormalizer().clean
    except Exception:            # pragma: no cover - normaliser is always there
        return _fallback_clean


def is_correction_marker(text: str) -> bool:
    return _fallback_clean(text) in _CORRECTION_MARKERS


def content_tokens(text: str) -> set:
    return {t for t in _fallback_clean(text).split()
            if len(t) > 2 and t not in _FILLER}


def related(a: str, b: str) -> bool:
    """Do two phrasings talk about the same thing? One shared content word.

    A deliberately low bar with a deliberately hard floor: it exists to reject
    "chrome band karo" followed by "what's the weather", not to judge how good
    a rephrase is.
    """
    ta, tb = content_tokens(a), content_tokens(b)
    return bool(ta and tb and (ta & tb))


def learnable(text: str) -> bool:
    """Is this phrase worth aliasing at all?"""
    clean = _fallback_clean(text)
    if not clean or is_correction_marker(clean):
        return False
    toks = clean.split()
    if not (MIN_TOKENS <= len(toks) <= MAX_TOKENS):
        return False
    if any(ch.isdigit() for ch in clean):
        return False             # times, amounts, math — one-offs, not phrasings
    return True


class RepairMemory:
    def __init__(self, path: Optional[str] = DEFAULT_PATH, *,
                 window_s: float = WINDOW_S, min_conf: float = MIN_CONF,
                 max_aliases: int = MAX_ALIASES,
                 clock: Callable[[], float] = time.time,
                 normalizer: Optional[Callable[[str], str]] = None,
                 autosave: bool = True):
        self.path = path
        self.window_s = window_s
        self.min_conf = min_conf
        self.max_aliases = max_aliases
        self._clock = clock
        self._clean = normalizer or _default_normalizer()
        self._autosave = autosave
        self._aliases: dict[str, Alias] = {}
        self._last_miss: Optional[tuple] = None    # (raw_text, ts)
        self._explicit = False
        self._last_learned: Optional[str] = None
        self.learned = 0
        self.forgotten = 0
        self.declined = 0
        if path:
            self.load()

    # ── the one call the engine makes ────────────────────────────────
    def note_turn(self, text: str, *, intent: Optional[str] = None,
                  confidence: float = 0.0, ok: bool = True,
                  from_alias: bool = False) -> Optional[str]:
        """Record how a turn went; learn an alias when this turn repairs the
        last one. Returns the phrase learned, or ``None``.

        ``ok`` is "did AERIS actually do the thing" — an executed skill or a
        slot question, not a fallback, an error, or a chat deflection.
        ``from_alias`` says this turn was routed BY a learned alias, which is
        what lets a bad alias delete itself.
        """
        if is_correction_marker(text):
            # The correction utterance is not a turn in its own right: it must
            # not overwrite the miss it is complaining about.
            self.note_correction(text, from_alias=from_alias)
            return None

        now = self._clock()
        if not (ok and intent and float(confidence or 0.0) >= self.min_conf):
            if from_alias:
                self.forget(text)       # the alias sent us wrong — drop it
            self._last_miss = (text, now)
            self._explicit = False
            return None

        learned = self._maybe_learn(text, intent, now)
        self._last_miss = None
        self._explicit = False
        return learned

    def note_correction(self, text: str = "", *, from_alias: bool = False) -> None:
        """The user said "galat"/"wrong". Marks the pending miss as an
        *explicit* repair (which waives the relatedness test) and drops the
        alias that caused it, if one did."""
        self._explicit = True
        if from_alias and self._last_miss:
            self.forget(self._last_miss[0])

    def _maybe_learn(self, repair_text: str, intent: str,
                     now: float) -> Optional[str]:
        if not self._last_miss:
            return None
        missed, ts = self._last_miss
        if (now - ts) > self.window_s:
            return None
        if not learnable(missed):
            self.declined += 1
            return None
        key = self._key(missed)
        if not key or key == self._key(repair_text):
            return None                 # same phrase — nothing was rephrased
        if not (self._explicit or related(missed, repair_text)):
            # Unrelated: the user gave up and moved on, they did not rephrase.
            self.declined += 1
            return None
        self._aliases[key] = Alias(
            intent=intent, slots={}, learned_at=now,
            source="explicit" if self._explicit else "implicit",
            last_used=now)
        self._last_learned = key
        self.learned += 1
        self._evict()
        log.info("[repair] learned %r → %s (%s)", key, intent,
                 self._aliases[key].source)
        self._save_if_auto()
        return key

    def remember_slots(self, phrase: str, slots: dict) -> None:
        """Attach the repair turn's slots to a just-learned alias.

        Separate from ``note_turn`` because the engine knows the intent before
        it knows the filled slots, and an alias is more useful with them: an
        exact phrase repeat should reproduce the exact action.
        """
        key = self._key(phrase)
        a = self._aliases.get(key)
        if a is not None and isinstance(slots, dict):
            a.slots = {str(k): v for k, v in slots.items()}
            self._save_if_auto()

    # ── the router's question ────────────────────────────────────────
    def lookup(self, text: str) -> Optional[Alias]:
        """Has the user taught us this exact phrasing? Consult this at the TOP
        of the router — it is an exact-match tier, cheaper than every other
        one, and it encodes something the user told us directly."""
        a = self._aliases.get(self._key(text))
        if a is None:
            return None
        a.hits += 1
        a.last_used = self._clock()
        return a

    # ── forgetting ───────────────────────────────────────────────────
    def forget(self, text: str) -> bool:
        if self._aliases.pop(self._key(text), None) is None:
            return False
        self.forgotten += 1
        self._save_if_auto()
        return True

    def forget_last(self) -> Optional[str]:
        """Undo the most recent thing learned — the "nahi, ye mat seekho" path."""
        if not self._last_learned:
            return None
        key, self._last_learned = self._last_learned, None
        return key if self.forget(key) else None

    def clear(self) -> None:
        self._aliases.clear()
        self._last_learned = None
        self._save_if_auto()

    # ── plumbing ─────────────────────────────────────────────────────
    def _key(self, text: str) -> str:
        try:
            return (self._clean(text) or "").strip()
        except Exception:
            return _fallback_clean(text)

    def _evict(self) -> None:
        if len(self._aliases) <= self.max_aliases:
            return
        # LRU by last use, so a phrasing the user actually relies on outlives
        # one they taught once and never repeated.
        for key, _ in sorted(self._aliases.items(),
                             key=lambda kv: kv[1].last_used)[
                :len(self._aliases) - self.max_aliases]:
            self._aliases.pop(key, None)

    def __len__(self) -> int:
        return len(self._aliases)

    def items(self) -> list:
        """``[(phrase, Alias), ...]``, most-used first — for the inspection
        skill, so it doesn't have to reach into `_aliases`."""
        return sorted(self._aliases.items(), key=lambda kv: (-kv[1].hits, kv[0]))

    def stats(self) -> dict:
        return {"aliases": len(self._aliases), "learned": self.learned,
                "forgotten": self.forgotten, "declined": self.declined,
                "explicit": sum(1 for a in self._aliases.values()
                                if a.source == "explicit")}

    # ── persistence ──────────────────────────────────────────────────
    def load(self) -> int:
        if not self.path or not os.path.exists(self.path):
            return 0
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                blob = json.load(fh)
        except Exception as e:
            log.warning("[repair] could not read %s: %s", self.path, e)
            return 0
        got = 0
        for key, raw in (blob.get("aliases") or {}).items():
            if not isinstance(raw, dict) or not raw.get("intent"):
                continue
            try:
                self._aliases[key] = Alias(
                    intent=str(raw["intent"]),
                    slots=dict(raw.get("slots") or {}),
                    learned_at=float(raw.get("learned_at") or 0.0),
                    source=str(raw.get("source") or "implicit"),
                    hits=int(raw.get("hits") or 0),
                    last_used=float(raw.get("last_used") or 0.0))
                got += 1
            except Exception:
                continue        # one bad row must not lose the whole table
        return got

    def save(self) -> bool:
        if not self.path:
            return False
        blob = {"v": SCHEMA,
                "aliases": {k: asdict(a) for k, a in self._aliases.items()}}
        try:
            parent = os.path.dirname(self.path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(blob, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)      # atomic: never a half-written table
            return True
        except Exception as e:
            log.warning("[repair] could not save %s: %s", self.path, e)
            return False

    def _save_if_auto(self) -> None:
        if self._autosave and self.path:
            self.save()
