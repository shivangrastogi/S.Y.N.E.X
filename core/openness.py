"""Openness learning — initiative feedback loop (Blueprint P4).

``Initiative.openness`` was hardcoded. This store learns, per initiative
*kind*, whether the user actually acts on that kind of nudge:

    acted = 1.0 · ignored = 0.25 · dismissed = 0.0   →   EMA (α=0.2)

The Initiative Engine injects ``openness(kind)`` into every candidate's score,
so kinds the user ignores fade (anti-nag becomes data-driven) and kinds they
act on surface more readily. A floor keeps any kind from going fully mute —
importance can still carry a critical nudge over the bar.

Flow: dispatch surfaces an initiative → ``surfaced(kind)`` registers pending
feedback → an explicit reaction calls ``feedback(kind, outcome)`` → anything
still pending after ``settle_after_s`` settles as *ignored* on the next
``settle()`` (heartbeat calls it). Pure + injectable (path, clock) → tests on
tmp files with a fake clock.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_ROOT, "data", "openness.json")

_SCORE = {"acted": 1.0, "ignored": 0.25, "dismissed": 0.0}


class OpennessStore:
    def __init__(self, path: str = _DEFAULT_PATH, *,
                 alpha: float = 0.2, floor: float = 0.15, start: float = 0.6,
                 settle_after_s: float = 90.0,
                 now_fn: Callable[[], float] = time.time):
        self._path = path
        self._alpha = float(alpha)
        self._floor = float(floor)
        self._start = float(start)
        self._settle_after = float(settle_after_s)
        self._now = now_fn
        self._ema: dict[str, float] = {}
        self._counts: dict[str, dict] = {}       # kind -> {acted,ignored,dismissed}
        self._pending: dict[str, float] = {}     # kind -> surfaced ts
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self._ema = {k: float(v) for k, v in (d.get("ema") or {}).items()}
                self._counts = d.get("counts") or {}
        except Exception as e:
            log.warning("[openness] load failed: %s", e)

    def _save(self) -> None:
        try:
            from core.atomic_io import write_atomic_json
            write_atomic_json(self._path, {"v": 1, "ema": self._ema,
                                           "counts": self._counts})
        except Exception as e:
            log.warning("[openness] save failed: %s", e)

    # -- the loop --------------------------------------------------------

    def surfaced(self, kind: str) -> None:
        """An initiative of this kind was just surfaced — await a reaction."""
        if kind:
            self._pending[kind] = self._now()

    def feedback(self, kind: str, outcome: str) -> float:
        """Record an explicit reaction. Returns the new openness."""
        if outcome not in _SCORE:
            raise ValueError(f"bad outcome {outcome!r}")
        self._pending.pop(kind, None)
        prev = self._ema.get(kind, self._start)
        newv = prev * (1 - self._alpha) + _SCORE[outcome] * self._alpha
        self._ema[kind] = newv
        c = self._counts.setdefault(kind, {"acted": 0, "ignored": 0,
                                           "dismissed": 0})
        c[outcome] += 1
        self._save()
        return self.openness(kind)

    def settle(self, now: Optional[float] = None) -> int:
        """Pending surfacings past the window settle as *ignored*.
        Returns how many settled. Call from the heartbeat."""
        t = self._now() if now is None else now
        stale = [k for k, ts in self._pending.items()
                 if (t - ts) >= self._settle_after]
        for k in stale:
            self.feedback(k, "ignored")
        return len(stale)

    # -- reads -------------------------------------------------------

    def openness(self, kind: str) -> float:
        return max(self._floor, self._ema.get(kind, self._start))

    def learned(self, kind: str) -> Optional[float]:
        """Openness only if we actually have data for this kind — lets the
        engine keep a source's hand-tuned default until real evidence exists."""
        if kind in self._ema or kind in self._counts:
            return self.openness(kind)
        return None

    def stats(self) -> dict:
        return {k: {"openness": round(self.openness(k), 3),
                    **self._counts.get(k, {})}
                for k in set(self._ema) | set(self._counts)}


_STORE: Optional[OpennessStore] = None


def get_store() -> OpennessStore:
    global _STORE
    if _STORE is None:
        _STORE = OpennessStore()
    return _STORE
