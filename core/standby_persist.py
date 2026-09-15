"""Lifetime standby telemetry — persist the duty cycle across restarts.

``core.standby_stats.StandbyStats`` tracks one *session* (reset every launch).
But the always-on thesis — "the brain is dormant ~99% of the time" — is only
convincing measured across the machine's whole life, spanning reboots. This
module banks each session's totals into a small JSON file and reports the
running lifetime duty cycle.

Two pieces, split so the accounting is pure and the IO is thin:

  * ``LifetimeStats`` — an immutable accumulator. ``merge_session(snapshot)``
    folds one session's ``StandbyStats.snapshot()`` in and counts it as a
    session. All arithmetic, no IO — trivially testable.
  * ``StandbyStatsStore`` — loads the baseline from disk, and ``commit`` writes
    ``baseline + current session`` back. It always recomputes from the *fixed*
    loaded baseline, so committing repeatedly (periodic checkpoint *and* a final
    shutdown flush) can never double-count the same session.

The file read/write are injectable, so the whole thing is unit-tested against an
in-memory dict — no real disk. The default writer is atomic (temp + os.replace)
so a crash mid-write can't corrupt the running total.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, Optional


def _f(d: dict, key: str, default: float = 0.0) -> float:
    try:
        v = float(d.get(key, default))
    except (TypeError, ValueError):
        return default
    return v if v == v and v >= 0 else default  # reject NaN / negative


def _i(d: dict, key: str, default: int = 0) -> int:
    try:
        v = int(d.get(key, default))
    except (TypeError, ValueError):
        return default
    return v if v >= 0 else default


@dataclass(frozen=True)
class LifetimeStats:
    """Running totals across every standby session so far."""

    active_s: float = 0.0
    dormant_s: float = 0.0
    wakes: int = 0
    spinups: int = 0
    sessions: int = 0

    def merge_session(self, snap: dict) -> "LifetimeStats":
        """Return a new total with one session's snapshot folded in (+1 session).

        ``snap`` is a ``StandbyStats.snapshot()`` dict; missing/garbage fields
        count as zero so a partial snapshot can never corrupt the lifetime total.
        """
        snap = snap or {}
        return LifetimeStats(
            active_s=self.active_s + _f(snap, "active_s"),
            dormant_s=self.dormant_s + _f(snap, "dormant_s"),
            wakes=self.wakes + _i(snap, "wakes"),
            spinups=self.spinups + _i(snap, "spinups"),
            sessions=self.sessions + 1,
        )

    def snapshot(self) -> dict:
        total = self.active_s + self.dormant_s
        dormant_pct = (self.dormant_s / total * 100.0) if total > 0 else 100.0
        return {
            "lifetime_active_s": self.active_s,
            "lifetime_dormant_s": self.dormant_s,
            "lifetime_dormant_pct": dormant_pct,
            "lifetime_wakes": self.wakes,
            "lifetime_spinups": self.spinups,
            "sessions": self.sessions,
        }

    def summary_line(self) -> str:
        s = self.snapshot()
        return (f"lifetime: {s['lifetime_dormant_pct']:.1f}% dormant across "
                f"{self.sessions} session(s), {self.wakes} wakes")

    def to_dict(self) -> dict:
        return {
            "active_s": self.active_s,
            "dormant_s": self.dormant_s,
            "wakes": self.wakes,
            "spinups": self.spinups,
            "sessions": self.sessions,
        }

    @classmethod
    def from_dict(cls, d) -> "LifetimeStats":
        """Rebuild from a persisted dict, tolerating anything malformed."""
        if not isinstance(d, dict):
            return cls()
        return cls(
            active_s=_f(d, "active_s"),
            dormant_s=_f(d, "dormant_s"),
            wakes=_i(d, "wakes"),
            spinups=_i(d, "spinups"),
            sessions=_i(d, "sessions"),
        )


def _default_read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _default_write(path: str, text: str) -> None:
    """Atomic write: temp file in the same dir, then os.replace over the target."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)  # atomic on Windows + POSIX


class StandbyStatsStore:
    """Persists the lifetime duty cycle. IO is injectable for tests."""

    def __init__(
        self,
        path: str,
        *,
        read: Callable[[str], str] = _default_read,
        write: Callable[[str, str], None] = _default_write,
    ) -> None:
        self._path = path
        self._read = read
        self._write = write
        self._baseline = LifetimeStats()

    def load(self) -> LifetimeStats:
        """Read the persisted baseline. Missing or corrupt file → fresh zero."""
        try:
            raw = self._read(self._path)
        except (FileNotFoundError, OSError):
            self._baseline = LifetimeStats()
            return self._baseline
        try:
            self._baseline = LifetimeStats.from_dict(json.loads(raw))
        except (ValueError, TypeError):
            self._baseline = LifetimeStats()  # unparseable → start over, don't crash
        return self._baseline

    @property
    def baseline(self) -> LifetimeStats:
        return self._baseline

    def merged(self, session_snapshot: Optional[dict]) -> LifetimeStats:
        """Baseline + the current session — recomputed from the fixed baseline,
        so calling this (and ``commit``) repeatedly never double-counts."""
        return self._baseline.merge_session(session_snapshot or {})

    def commit(self, session_snapshot: Optional[dict]) -> LifetimeStats:
        """Persist ``baseline + session`` and return the new lifetime total."""
        merged = self.merged(session_snapshot)
        self._write(self._path, json.dumps(merged.to_dict(), indent=2))
        return merged
