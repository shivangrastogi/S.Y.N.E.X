"""Affective Core — AERIS's emotional layer (Sentient-Partner Phase 1).

Per-utterance sentiment is computed today (core/sentiment) and then thrown away.
This module keeps a **persistent affective state** — a running read of how you seem
to feel and how AERIS should respond back — and turns it into:

  1. **tone adaptation**   — gentle when you're low, upbeat on a win (`tone()`, `modulate()`)
  2. **proactive care**    — a check-in when you've been low/tired/frustrated (`care_moment()`)
  3. **emotional memory**  — significant moments persist (for later recall / continuity)

Design: a small VALENCE (unpleasant↔pleasant) + AROUSAL (calm↔activated) model,
EMA-updated from sentiment and context, decaying toward neutral over time (feelings
fade). Pure logic + one tiny JSON state file. No external services.

**Kill switch:** `AERIS_AFFECT_OFF=1`, or `AffectiveCore(...).set_enabled(False)`.
When disabled, `tone()` is "neutral", `care_moment()`/`modulate()` are no-ops.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATE_PATH = os.path.join(_ROOT, "data", "affect_state.json")

# How fast mood tracks new observations (0..1; higher = more reactive).
_ALPHA = 0.30
# Feelings fade toward neutral at this fraction per hour of no interaction.
_DECAY_PER_HOUR = 0.5
# At most one proactive caring moment per this window.
_CARE_COOLDOWN_S = 30 * 60
# Streak lengths before a caring moment is considered.
_LOW_STREAK = 3
_FAIL_STREAK = 3
# Quiet hours (inclusive start, exclusive end next day) — no proactive care.
_QUIET_START_H, _QUIET_END_H = 23, 7


@dataclass
class AffectiveState:
    valence: float = 0.0          # -1 unpleasant .. +1 pleasant
    arousal: float = 0.20         # 0 calm .. 1 activated
    updated_at: float = field(default_factory=time.time)
    consecutive_low: int = 0      # streak of negative observations
    consecutive_fail: int = 0     # streak of failed/errored actions
    last_care_at: float = 0.0

    def mood(self) -> str:
        """Coarse mood label from the valence/arousal quadrants."""
        v, a = self.valence, self.arousal
        if v <= -0.35:
            return "frustrated" if a >= 0.55 else "low"
        if v >= 0.35:
            return "excited" if a >= 0.55 else "content"
        if a <= 0.12:
            return "tired"
        return "neutral"

    def to_dict(self) -> dict:
        return {
            "valence": round(self.valence, 4), "arousal": round(self.arousal, 4),
            "updated_at": self.updated_at, "consecutive_low": self.consecutive_low,
            "consecutive_fail": self.consecutive_fail, "last_care_at": self.last_care_at,
        }


# Tone hint per mood — consumed by the reply path / TTS to colour the response.
_TONE = {
    "frustrated": "calm", "low": "gentle", "tired": "gentle",
    "content": "warm", "excited": "upbeat", "neutral": "neutral",
}

# Short empathetic openers (Hinglish, matching AERIS's voice). Subtle, optional.
_OPENERS = {
    "gentle": ["Main yahin hoon. ", "Koi baat nahi. "],
    "calm":   ["Chaliye ek ek karke. ", "Relax, dekhte hmain. "],
    "warm":   ["", ""],
    "upbeat": ["Nice! ", "Badhiya! "],
    "neutral": ["", ""],
}

# Proactive check-in lines per mood.
_CARE = {
    "low": "Aap thode low lag rahe ho, sir. Chai break ya thoda music — kuch help karoon?",
    "frustrated": "Lagta hai cheezein zid kar rahi hain. Ek saans lo — main handle kar leta hoon, batao kya karna hai.",
    "tired": "Kaafi der se laga hue ho. Thoda rest le lo, main yahin hoon jab wapas aao.",
}


class AffectiveCore:
    """Stateful emotional layer. Construct once; call `observe()` on each turn."""

    def __init__(self, state: Optional[AffectiveState] = None,
                 enabled: Optional[bool] = None, persist_path: Optional[str] = None):
        self._path = persist_path or _STATE_PATH
        if enabled is None:
            enabled = os.environ.get("AERIS_AFFECT_OFF", "") not in ("1", "true", "True")
        self.enabled = enabled
        self.state = state if state is not None else self._load()

    # ── update ──────────────────────────────────────────────────────────
    def observe(self, sentiment_score: float, *, failure: bool = False,
                success: bool = False, energy: Optional[float] = None,
                now: Optional[float] = None) -> None:
        """Fold one interaction into the affective state.

        sentiment_score: -1..1 (from core.sentiment). failure/success: did the
        last action error / clearly succeed. energy: 0..1 optional voice energy.
        """
        if not self.enabled:
            return
        now = time.time() if now is None else now
        self._decay(now)
        s = self.state

        target_v = max(-1.0, min(1.0, float(sentiment_score)))
        if failure:
            target_v = min(target_v, -0.4)      # errors sting
        if success:
            target_v = max(target_v, 0.4)        # wins lift
        s.valence = (1 - _ALPHA) * s.valence + _ALPHA * target_v

        target_a = abs(target_v) if energy is None else max(abs(target_v), energy)
        s.arousal = (1 - _ALPHA) * s.arousal + _ALPHA * target_a
        s.arousal = max(0.0, min(1.0, s.arousal))

        s.consecutive_low = s.consecutive_low + 1 if target_v <= -0.2 else 0
        s.consecutive_fail = s.consecutive_fail + 1 if failure else 0
        s.updated_at = now

    def _decay(self, now: float) -> None:
        s = self.state
        hours = max(0.0, (now - s.updated_at) / 3600.0)
        if hours <= 0:
            return
        keep = max(0.0, 1.0 - _DECAY_PER_HOUR * hours)
        s.valence *= keep
        # arousal relaxes toward a low baseline, not zero
        s.arousal = 0.15 + (s.arousal - 0.15) * keep
        s.updated_at = now

    # ── outputs ─────────────────────────────────────────────────────────
    def mood(self) -> str:
        return self.state.mood() if self.enabled else "neutral"

    def tone(self) -> str:
        """Tone hint for the reply path / TTS. 'neutral' when disabled."""
        return _TONE.get(self.state.mood(), "neutral") if self.enabled else "neutral"

    def modulate(self, reply: str) -> str:
        """Optionally colour a reply with a brief empathetic opener. Subtle:
        only fires for clearly non-neutral moods, never changes the content."""
        if not self.enabled or not reply:
            return reply
        openers = _OPENERS.get(self.tone(), [""])
        opener = openers[0] if openers else ""
        return f"{opener}{reply}" if opener else reply

    def care_moment(self, now: Optional[float] = None,
                    hour: Optional[int] = None) -> Optional[str]:
        """A proactive check-in line if the state warrants one — else None.
        Rate-limited and suppressed during quiet hours so it never nags."""
        if not self.enabled:
            return None
        now = time.time() if now is None else now
        self._decay(now)
        # Rate-limit — but last_care_at == 0 means "never cared", not "cared at
        # the epoch", so don't let it block the very first check-in.
        if self.state.last_care_at and (now - self.state.last_care_at) < _CARE_COOLDOWN_S:
            return None
        h = time.localtime(now).tm_hour if hour is None else hour
        if _in_quiet_hours(h):
            return None
        mood = self.state.mood()
        warranted = (
            (mood in ("low", "frustrated") and self.state.consecutive_low >= _LOW_STREAK)
            or (self.state.consecutive_fail >= _FAIL_STREAK)
            or (mood == "tired" and h >= 22)
        )
        if not warranted:
            return None
        line = _CARE.get(mood) or _CARE["low"]
        self.state.last_care_at = now
        return line

    # ── persistence + control ──────────────────────────────────────────
    def set_enabled(self, on: bool) -> None:
        self.enabled = bool(on)

    def _load(self) -> AffectiveState:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            return AffectiveState(
                valence=float(d.get("valence", 0.0)),
                arousal=float(d.get("arousal", 0.2)),
                updated_at=float(d.get("updated_at", time.time())),
                consecutive_low=int(d.get("consecutive_low", 0)),
                consecutive_fail=int(d.get("consecutive_fail", 0)),
                last_care_at=float(d.get("last_care_at", 0.0)),
            )
        except Exception:
            return AffectiveState()

    def persist(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.state.to_dict(), fh)
            os.replace(tmp, self._path)
        except Exception as e:
            log.debug("[affect] persist failed: %s", e)


def _in_quiet_hours(h: int) -> bool:
    if _QUIET_START_H <= _QUIET_END_H:
        return _QUIET_START_H <= h < _QUIET_END_H
    return h >= _QUIET_START_H or h < _QUIET_END_H


# Process-wide singleton (lazy).
_DEFAULT: Optional[AffectiveCore] = None


def get() -> AffectiveCore:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = AffectiveCore()
    return _DEFAULT
