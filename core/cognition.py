"""Cognition Loop — the "thinks on its own" layer (Sentient-Partner Phase 6).

A deterministic background reasoner. Given the current `ContextSnapshot` (battery,
calendar, mood, time-of-day, presence, recent commands) it forms candidate
*sub-goals* — things a thoughtful partner would proactively raise — ranks them,
and returns the single most worthwhile `Thought` (or None, to stay quiet). It
stitches the other cores together: perception (Context Bus) + habits (Anticipation)
+ feeling (Affect mood) + safety (Trust Ladder). It ONLY proposes — nothing here
auto-executes; the caller speaks the thought and, for an actionable one, a "haan"
runs the command through the normal pipeline.

Emotionally aware: when you're frustrated or low it suppresses everything except a
genuinely urgent nudge (battery) so it never piles on. Quiet-hours aware (only a
one-off rest nudge + battery at night). Rate-limited so it can't nag. Manual
autonomy (level 0) silences proactive habit ideas but keeps safety/care nudges.
Kill switch: `AERIS_COGNITION_OFF=1`.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

_BATTERY_LOW = 20         # percent
_URGENT = 80              # priority at/above which a thought survives a bad mood
_COOLDOWN_S = 1200.0      # 20 min — cognition never speaks more often than this


@dataclass(frozen=True)
class Thought:
    kind: str              # "battery" | "calendar" | "rest" | "habit"
    message: str           # what AERIS would say
    command: Optional[str] # replayable command text if actionable, else None
    trust: str             # AUTO | OFFER (never CONFIRM/FORBID — those aren't proactive)
    priority: int          # higher = more worth raising
    action: str = "offer"  # "offer" (ask first) | "do" (L3 silent auto-do candidate)


def _autonomy() -> int:
    try:
        from core.trust_ladder import autonomy_level
        return autonomy_level()
    except Exception:
        return 2


class CognitionLoop:
    def __init__(self, enabled: Optional[bool] = None, cooldown_s: float = _COOLDOWN_S):
        if enabled is None:
            enabled = os.environ.get("AERIS_COGNITION_OFF", "") not in ("1", "true", "True")
        self.enabled = enabled
        self._cooldown = cooldown_s
        self._last_at = 0.0
        self._last_sig: Optional[tuple] = None
        self._seen_event: Optional[str] = None

    # ── candidate formation ──────────────────────────────────────────────
    def _habit(self, snap) -> Optional[Thought]:
        try:
            from core import anticipation
            prev = snap.recent_intents[-1] if snap.recent_intents else None
            sug = anticipation.get().suggest(snap.time_of_day, prev)
        except Exception:
            return None
        if not sug:
            return None
        return Thought("habit", sug.phrase, sug.command, sug.trust, 55, sug.action)

    def _candidates(self, snap) -> list[Thought]:
        from core.trust_ladder import OFFER
        out: list[Thought] = []
        # Battery — the one nudge urgent enough to survive a bad mood / quiet hours.
        if snap.battery_pct is not None and snap.battery_pct <= _BATTERY_LOW:
            out.append(Thought("battery",
                               f"Battery {snap.battery_pct}% pe hai — charger laga lein?",
                               None, OFFER, 90))
        if snap.is_quiet_hours:
            # At night: only a gentle, one-off rest nudge (+ battery above).
            if snap.presence == "active" or snap.recent_commands:
                out.append(Thought("rest",
                                   "Kaafi raat ho gayi hai — thoda aaram bhi zaroori hai.",
                                   None, OFFER, 40))
            return out
        # Daytime: a calendar reminder (deduped per event) ...
        if snap.next_event and snap.next_event != self._seen_event:
            out.append(Thought("calendar",
                               f"Yaad dila raha hoon — {snap.next_event}.", None, OFFER, 70))
        # ... and a proactive habit, unless the user asked for manual control.
        if _autonomy() >= 1:
            h = self._habit(snap)
            if h:
                out.append(h)
        return out

    # ── the loop ─────────────────────────────────────────────────────────
    def reflect(self, snap, *, now: Optional[float] = None) -> Optional[Thought]:
        """The single most worthwhile proactive thought right now, or None."""
        if not self.enabled:
            return None
        now = time.time() if now is None else now
        if self._last_at and (now - self._last_at) < self._cooldown:
            return None
        cands = self._candidates(snap)
        if snap.mood in ("frustrated", "low"):
            cands = [t for t in cands if t.priority >= _URGENT]   # don't pile on
        if not cands:
            return None
        cands.sort(key=lambda t: t.priority, reverse=True)
        # Don't repeat the exact thought we last raised — pick the next distinct one.
        top = cands[0]
        if (top.kind, top.message) == self._last_sig:
            top = next((t for t in cands
                        if (t.kind, t.message) != self._last_sig), None)
            if top is None:
                return None
        self._last_at = now
        self._last_sig = (top.kind, top.message)
        if top.kind == "calendar":
            self._seen_event = snap.next_event
        return top


_DEFAULT: Optional[CognitionLoop] = None


def get() -> CognitionLoop:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = CognitionLoop()
    return _DEFAULT
