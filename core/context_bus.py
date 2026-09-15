"""Context Bus — AERIS's unified "what's happening right now" (Sentient-Partner Phase 2).

Today the signals AERIS could act on — time, active app, recent commands, mood,
presence, battery, calendar — live in separate modules, so anticipation/emotion/
cognition each re-derive context. This module gives them ONE `ContextSnapshot`.

Design: a passive aggregator. Sources **push** what they observe
(`record_command`, `set_active_window`, `set_presence`, `set_battery`,
`set_next_event`); cheap/always-available signals (clock, mood) are **pulled** at
snapshot time. `snapshot()` returns an immutable read; `subscribe()` gets a
callback on every push. Thread-safe — the GUI worker, presence thread, and
cloud-bridge all touch it.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

# Time-of-day buckets (match eternal_presence's spirit).
_QUIET_START_H, _QUIET_END_H = 23, 7


def _time_of_day(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def _in_quiet_hours(hour: int) -> bool:
    if _QUIET_START_H <= _QUIET_END_H:
        return _QUIET_START_H <= hour < _QUIET_END_H
    return hour >= _QUIET_START_H or hour < _QUIET_END_H


@dataclass(frozen=True)
class ContextSnapshot:
    ts: float
    hour: int
    time_of_day: str
    is_quiet_hours: bool
    active_app: Optional[str]
    active_title: Optional[str]
    recent_commands: tuple           # last N command texts (newest last)
    recent_intents: tuple
    mood: str
    presence: str                    # active | idle | away | unknown
    idle_seconds: float
    battery_pct: Optional[int]
    next_event: Optional[str]
    summary: str

    def to_dict(self) -> dict:
        d = self.__dict__.copy() if hasattr(self, "__dict__") else {}
        # frozen dataclass stores fields on the instance via __dict__ off; build manually
        return {
            "ts": self.ts, "hour": self.hour, "time_of_day": self.time_of_day,
            "is_quiet_hours": self.is_quiet_hours, "active_app": self.active_app,
            "active_title": self.active_title,
            "recent_commands": list(self.recent_commands),
            "recent_intents": list(self.recent_intents),
            "mood": self.mood, "presence": self.presence,
            "idle_seconds": self.idle_seconds, "battery_pct": self.battery_pct,
            "next_event": self.next_event, "summary": self.summary,
        }


class ContextBus:
    def __init__(self, max_recent: int = 8):
        self._lock = threading.RLock()
        self._recent = deque(maxlen=max_recent)      # (text, intent)
        self._active_app: Optional[str] = None
        self._active_title: Optional[str] = None
        self._presence = "unknown"
        self._idle_seconds = 0.0
        self._battery: Optional[int] = None
        self._next_event: Optional[str] = None
        self._subs: list[Callable[[ContextSnapshot], None]] = []

    # ── push (sources call these) ───────────────────────────────────────
    def record_command(self, text: str, intent: Optional[str] = None) -> None:
        text = (text or "").strip()
        if not text:
            return
        with self._lock:
            self._recent.append((text, intent or ""))
        self._fan_out()

    def set_active_window(self, app: Optional[str], title: Optional[str] = None) -> None:
        with self._lock:
            self._active_app = (app or None)
            self._active_title = (title or None)
        self._fan_out()

    def set_presence(self, state: str, idle_seconds: float = 0.0) -> None:
        with self._lock:
            self._presence = state or "unknown"
            self._idle_seconds = max(0.0, float(idle_seconds))
        self._fan_out()

    def set_battery(self, pct: Optional[int]) -> None:
        with self._lock:
            self._battery = None if pct is None else int(pct)

    def set_next_event(self, summary: Optional[str]) -> None:
        with self._lock:
            self._next_event = (summary or None)

    def subscribe(self, cb: Callable[[ContextSnapshot], None]) -> None:
        with self._lock:
            self._subs.append(cb)

    # ── pull (higher layers call this) ─────────────────────────────────
    def snapshot(self, now: Optional[float] = None,
                 mood: Optional[str] = None,
                 hour: Optional[int] = None) -> ContextSnapshot:
        now = time.time() if now is None else now
        if hour is None:
            hour = time.localtime(now).tm_hour
        if mood is None:
            mood = self._pull_mood()
        with self._lock:
            recent = tuple(t for t, _ in self._recent)
            intents = tuple(i for _, i in self._recent)
            snap = ContextSnapshot(
                ts=now, hour=hour, time_of_day=_time_of_day(hour),
                is_quiet_hours=_in_quiet_hours(hour),
                active_app=self._active_app, active_title=self._active_title,
                recent_commands=recent, recent_intents=intents,
                mood=mood, presence=self._presence, idle_seconds=self._idle_seconds,
                battery_pct=self._battery, next_event=self._next_event,
                summary=self._summarize(hour, recent, mood),
            )
        return snap

    # ── internals ───────────────────────────────────────────────────────
    @staticmethod
    def _pull_mood() -> str:
        try:
            from core import affect
            return affect.get().mood()
        except Exception:
            return "neutral"

    def _summarize(self, hour: int, recent: tuple, mood: str) -> str:
        bits = [_time_of_day(hour)]
        if self._active_app:
            bits.append(self._active_app)
        if mood and mood != "neutral":
            bits.append(f"mood:{mood}")
        if self._presence not in ("unknown", "active"):
            bits.append(self._presence)
        if recent:
            bits.append(f"last:'{recent[-1][:32]}'")
        return " · ".join(bits)

    def _fan_out(self) -> None:
        with self._lock:
            subs = list(self._subs)
        if not subs:
            return
        snap = self.snapshot()
        for cb in subs:
            try:
                cb(snap)
            except Exception:
                pass


# Process-wide singleton (lazy).
_DEFAULT: Optional[ContextBus] = None


def get() -> ContextBus:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ContextBus()
    return _DEFAULT
