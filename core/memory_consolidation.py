"""Nightly memory consolidation — the agent's "sleep" (Blueprint learning loop 2).

Once a day, AERIS summarizes the day's episodic memory into a durable note and
lets the raw noise age out — the same job sleep does for a brain. Built on the
Memory Fabric's ``consolidate()`` (which pulls recent episodic records and asks
a summarizer), wrapped here with **idempotency** (once per day, survives
restarts via a small marker) and a scheduling helper.

Injectable (fabric, llm, clock, marker path) so it unit-tests with fakes — no
model, no real disk beyond a tmp marker.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_MARKER = os.path.join(_ROOT, "data", "consolidation.marker")


class Consolidator:
    def __init__(self, *,
                 fabric_provider: Optional[Callable[[], Any]] = None,
                 llm: Optional[Callable[[str], str]] = None,
                 now_fn: Callable[[], float] = time.time,
                 marker_path: str = _DEFAULT_MARKER):
        self._fabric_provider = fabric_provider or _default_fabric
        self._llm = llm
        self._now = now_fn
        self._marker = marker_path

    def set_llm(self, llm: Callable[[str], str]) -> None:
        """Wire the summarizer (e.g. the local LLM) after construction."""
        self._llm = llm

    # -- idempotency ----------------------------------------------------

    def _today(self) -> date:
        return datetime.fromtimestamp(self._now()).date()

    def last_run_date(self) -> Optional[date]:
        try:
            if os.path.exists(self._marker):
                with open(self._marker, "r", encoding="utf-8") as f:
                    return date.fromisoformat(f.read().strip())
        except Exception:
            pass
        return None

    def already_done_today(self) -> bool:
        return self.last_run_date() == self._today()

    def _mark_done(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._marker), exist_ok=True)
            with open(self._marker, "w", encoding="utf-8") as f:
                f.write(self._today().isoformat())
        except Exception as e:
            log.warning("[consolidate] marker write failed: %s", e)

    # -- the job --------------------------------------------------------

    def consolidate(self, *, force: bool = False) -> Optional[str]:
        """Run one consolidation pass. Returns the summary, or None if it was
        already done today (unless ``force``) / nothing to summarize."""
        if not force and self.already_done_today():
            return None
        if self._llm is None:
            return None  # no summarizer wired → safe no-op
        try:
            fabric = self._fabric_provider()
            summary = fabric.consolidate(llm=self._llm)
        except Exception as e:
            log.warning("[consolidate] failed: %s", e)
            return None
        # Mark the day done even if the summary was empty, so an idle day
        # doesn't retry every tick.
        self._mark_done()
        return summary


# ── scheduling ──────────────────────────────────────────────────────── #

def seconds_until_next(hour: int, minute: int, now: float) -> float:
    """Seconds from ``now`` to the next local HH:MM (today if still ahead,
    else tomorrow). Off-minute default so fleets don't all wake at :00."""
    from datetime import timedelta
    dt = datetime.fromtimestamp(now)
    target = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target.timestamp() <= now:
        target += timedelta(days=1)
    return max(1.0, target.timestamp() - now)


def schedule_nightly(scheduler, *, hour: int = 3, minute: int = 17,
                     now_fn: Callable[[], float] = time.time) -> None:
    """Register the next nightly consolidation with a scheduler exposing
    ``schedule(message, fire_at)``. The engine binds the ``__consolidate__``
    message id to ``get_consolidator().consolidate()`` in its on-fire handler,
    and calls this again to line up the following night."""
    fire_at = datetime.fromtimestamp(
        now_fn() + seconds_until_next(hour, minute, now_fn()))
    try:
        scheduler.schedule("__consolidate__", fire_at)
    except Exception as e:
        log.debug("[consolidate] scheduling skipped: %s", e)


# ── defaults ────────────────────────────────────────────────────────── #

def _default_fabric() -> Any:
    from core import memory_fabric
    return memory_fabric.get_fabric()


_CONSOLIDATOR: Optional[Consolidator] = None


def get_consolidator() -> Consolidator:
    global _CONSOLIDATOR
    if _CONSOLIDATOR is None:
        _CONSOLIDATOR = Consolidator()
    return _CONSOLIDATOR
