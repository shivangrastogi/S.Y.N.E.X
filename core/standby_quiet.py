"""Quiet hours — let the machine actually sleep overnight.

Normal standby keeps the *system* awake (releasing only the display) so it can
keep listening. But during the hours the user is asleep, that idling is wasted
power: an always-on OS should let the machine enter real sleep at night and wake
on user activity. ``QuietHours`` is the time-window policy that decides when
we're in that period; the daemon uses it to drop the system-awake hold.

The window is expressed as minutes-of-day and correctly handles wrapping past
midnight (e.g. 23:00 → 07:00). The clock is injected, so every boundary is
unit-tested with no real waiting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def _parse_hhmm(s) -> Optional[int]:
    """'HH:MM' → minutes-of-day, or None if malformed."""
    try:
        h_str, m_str = str(s).strip().split(":")
        h, m = int(h_str), int(m_str)
    except (ValueError, AttributeError):
        return None
    if 0 <= h <= 23 and 0 <= m <= 59:
        return h * 60 + m
    return None


class QuietHours:
    """A daily time window [start, end), wrapping midnight if start > end."""

    def __init__(self, start_min: int, end_min: int) -> None:
        self._start = int(start_min) % 1440
        self._end = int(end_min) % 1440

    @classmethod
    def parse(cls, start: str, end: str) -> Optional["QuietHours"]:
        """Build from 'HH:MM' strings. Returns None if either is malformed or
        the window is zero-length (start == end) → quiet hours disabled."""
        s = _parse_hhmm(start)
        e = _parse_hhmm(end)
        if s is None or e is None or s == e:
            return None
        return cls(s, e)

    def is_quiet(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now()
        m = now.hour * 60 + now.minute
        s, e = self._start, self._end
        if s < e:
            return s <= m < e          # same-day window
        return m >= s or m < e         # wraps past midnight

    def describe(self) -> str:
        def hhmm(x):
            return f"{x // 60:02d}:{x % 60:02d}"
        return f"{hhmm(self._start)}–{hhmm(self._end)}"
