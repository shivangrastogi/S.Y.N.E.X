"""Standby event journal — a small 'what has the OS been doing' log.

Stats say *how much* (duty cycle); the journal says *what happened and when*:
wakes, spin-ups/downs, self-healed crashes, breaker trips. It's a capped ring
buffer (newest N events) persisted atomically, so `--standby-status` — a
separate process — can show the recent activity of the running/last daemon and
answer "why did the brain restart?".

Events are recorded from several threads (wake, tick, power), so the buffer is
lock-guarded. Persistence IO is injectable, so the whole thing is unit-tested
against an in-memory dict with no real disk.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass(frozen=True)
class JournalEvent:
    ts: float          # epoch seconds
    kind: str          # wake | spinup | spindown | crash | breaker_open | ...
    detail: str = ""

    def to_dict(self) -> dict:
        return {"ts": self.ts, "kind": self.kind, "detail": self.detail}

    @classmethod
    def from_dict(cls, d) -> Optional["JournalEvent"]:
        if not isinstance(d, dict):
            return None
        try:
            return cls(ts=float(d.get("ts", 0.0)),
                       kind=str(d.get("kind", "?")),
                       detail=str(d.get("detail", "")))
        except (TypeError, ValueError):
            return None


def _default_read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _default_write(path: str, text: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _ago(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{int(seconds)}s ago"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    return f"{int(seconds // 86400)}d ago"


class StandbyJournal:
    """A capped, persisted, thread-safe ring buffer of standby events."""

    def __init__(
        self,
        *,
        capacity: int = 200,
        now: Callable[[], float] = time.time,
        path: Optional[str] = None,
        read: Callable[[str], str] = _default_read,
        write: Callable[[str, str], None] = _default_write,
    ) -> None:
        self._events: "deque[JournalEvent]" = deque(maxlen=max(1, int(capacity)))
        self._now = now
        self._path = path
        self._read = read
        self._write = write
        self._lock = threading.Lock()

    # ---- recording --------------------------------------------------- #

    def record(self, kind: str, detail: str = "") -> None:
        with self._lock:
            self._events.append(JournalEvent(self._now(), str(kind), str(detail)))

    def on_state_change(self, state) -> None:
        """Convenience for composing onto the orchestrator's callback."""
        name = getattr(state, "value", str(state))
        self.record("spinup" if name == "active" else "spindown")

    # ---- reading ----------------------------------------------------- #

    def all(self) -> List[JournalEvent]:
        with self._lock:
            return list(self._events)

    def recent(self, n: int = 10, *, kind: Optional[str] = None) -> List[JournalEvent]:
        with self._lock:
            evs = list(self._events)
        if kind is not None:
            evs = [e for e in evs if e.kind == kind]
        return evs[-n:] if n > 0 else []

    def count(self, kind: Optional[str] = None) -> int:
        with self._lock:
            if kind is None:
                return len(self._events)
            return sum(1 for e in self._events if e.kind == kind)

    def summary(self) -> dict:
        """Count of events per kind across the whole buffer."""
        with self._lock:
            evs = list(self._events)
        out: dict = {}
        for e in evs:
            out[e.kind] = out.get(e.kind, 0) + 1
        return out

    def format_recent(self, n: int = 10, *, kind: Optional[str] = None,
                      now: Optional[float] = None) -> List[str]:
        ref = now if now is not None else self._now()
        lines = []
        for e in self.recent(n, kind=kind):
            label = e.kind + (f" ({e.detail})" if e.detail else "")
            lines.append(f"{_ago(ref - e.ts):>8}  {label}")
        return lines

    # ---- persistence ------------------------------------------------- #

    def flush(self) -> None:
        """Write the current buffer atomically (no-op without a path)."""
        if self._path is None:
            return
        payload = json.dumps([e.to_dict() for e in self.all()])
        self._write(self._path, payload)

    def load(self) -> None:
        """Replace the buffer with the persisted events (tolerates missing /
        corrupt file → empty)."""
        if self._path is None:
            return
        try:
            raw = self._read(self._path)
        except (FileNotFoundError, OSError):
            return
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return
        if not isinstance(data, list):
            return
        with self._lock:
            self._events.clear()
            for d in data:
                ev = JournalEvent.from_dict(d)
                if ev is not None:
                    self._events.append(ev)
