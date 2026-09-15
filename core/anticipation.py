"""Anticipation engine — "you just think it, it does" (Sentient-Partner Phase 4).

Learns your habits from the Context Bus — *which command tends to follow which,
at what time of day* — and, given the current context, predicts your likely next
action. Each prediction is routed through the **Trust Ladder** so AERIS only ever
*offers* (or, for very confident + safe actions, *does-and-tells*); it stays quiet
otherwise. Destructive/outward actions are never anticipated.

Model: a light transition table `ctx-signature → Counter(next command)`, where the
signature is `time_of_day | previous_intent`, plus a `time_of_day | *` prior (so it
can predict your "morning routine" even with no immediate predecessor). Concrete
command *text* is learned (not just the intent) so a prediction is replayable.
Persists to JSON so habits survive restarts. Disable via `AERIS_ANTICIPATE_OFF=1`.
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "data", "anticipation.json")

# Need at least this many observations of a signature before predicting from it.
_MIN_SUPPORT = 3
# Confidence bands.
_HIGH_CONF = 0.60      # do-and-tell (only for AUTO-tier actions)
_MED_CONF = 0.35       # offer


@dataclass(frozen=True)
class Suggestion:
    command: str        # replayable command text, e.g. "gmail kholo"
    intent: str
    confidence: float
    trust: str          # AUTO | OFFER (never CONFIRM/FORBID — those aren't anticipated)
    action: str         # "do" (auto + tell) | "offer" (ask first)
    phrase: str         # what AERIS says


class Anticipator:
    def __init__(self, path: Optional[str] = None, enabled: Optional[bool] = None,
                 min_support: int = _MIN_SUPPORT):
        self._path = path or _PATH
        if enabled is None:
            enabled = os.environ.get("AERIS_ANTICIPATE_OFF", "") not in ("1", "true", "True")
        self.enabled = enabled
        self.min_support = min_support
        self._trans: dict[str, Counter] = defaultdict(Counter)
        self._cmd_intent: dict[str, str] = {}
        self._since_persist = 0
        self._load()

    # ── learning ────────────────────────────────────────────────────────
    def observe(self, prev_intent: Optional[str], next_command: str,
                next_intent: str, time_of_day: str) -> None:
        """Record that, in `time_of_day` after `prev_intent`, the user did
        `next_command` (whose intent is `next_intent`)."""
        if not self.enabled:
            return
        nc = (next_command or "").strip()
        if not nc:
            return
        prev = prev_intent or "*"
        self._trans[f"{time_of_day}|{prev}"][nc] += 1
        self._trans[f"{time_of_day}|*"][nc] += 1      # time-of-day prior
        self._cmd_intent[nc] = next_intent or ""
        # Auto-persist habits periodically so they survive a restart.
        self._since_persist += 1
        if self._since_persist >= 15:
            self._since_persist = 0
            self.persist()

    # ── prediction ──────────────────────────────────────────────────────
    def predict(self, time_of_day: str, prev_intent: Optional[str],
                k: int = 3) -> list[tuple[str, str, float]]:
        """Top-k (command, intent, confidence) for the given context."""
        if not self.enabled:
            return []
        prev = prev_intent or "*"
        counter = self._trans.get(f"{time_of_day}|{prev}")
        if not counter or sum(counter.values()) < self.min_support:
            counter = self._trans.get(f"{time_of_day}|*")     # fall back to time prior
        if not counter:
            return []
        total = sum(counter.values())
        if total < self.min_support:
            return []
        out = []
        for cmd, cnt in counter.most_common(k):
            out.append((cmd, self._cmd_intent.get(cmd, ""), cnt / total))
        return out

    def suggest(self, time_of_day: str, prev_intent: Optional[str]) -> Optional[Suggestion]:
        """The single best anticipatory move for now — or None to stay quiet.
        Trust-gated: never anticipates CONFIRM/FORBID actions; do-and-tell only
        for AUTO-tier + high confidence, else offer."""
        if not self.enabled:
            return None
        preds = self.predict(time_of_day, prev_intent, k=3)
        if not preds:
            return None
        cmd, intent, conf = preds[0]
        if conf < _MED_CONF:
            return None
        from core.trust_ladder import classify, AUTO, OFFER
        d = classify(intent)
        if d.level not in (AUTO, OFFER):     # CONFIRM/FORBID → never anticipate
            return None
        action = "do" if (d.level == AUTO and conf >= _HIGH_CONF) else "offer"
        phrase = (f"{cmd} kar diya." if action == "do"
                  else f"{cmd} karoon?")
        return Suggestion(command=cmd, intent=intent, confidence=round(conf, 3),
                          trust=d.level, action=action, phrase=phrase)

    # ── persistence ─────────────────────────────────────────────────────
    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            for sig, counts in d.get("trans", {}).items():
                self._trans[sig] = Counter(counts)
            self._cmd_intent = dict(d.get("cmd_intent", {}))
        except Exception:
            pass

    def persist(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            data = {"trans": {k: dict(v) for k, v in self._trans.items()},
                    "cmd_intent": self._cmd_intent}
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, self._path)
        except Exception as e:
            log.debug("[anticipation] persist failed: %s", e)


_DEFAULT: Optional[Anticipator] = None


def get() -> Anticipator:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Anticipator()
    return _DEFAULT
