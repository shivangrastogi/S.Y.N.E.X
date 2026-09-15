"""Routine graduation — trust earned over time (Blueprint learning loop 3).

``core.routine_learner`` only *offers* routines (never acts — earned trust
before automation). This module closes the loop: a suggestion the user accepts
enough times and never reverts **graduates** to an auto-routine that AERIS runs
on its own (governed by the Autonomy Ladder at L3, logged with a "why").

Rules, by design:
* Graduate only after ``threshold`` distinct accepts AND zero reverts — real,
  repeated consent, not one lucky yes.
* A single **revert** un-graduates it immediately and blocks re-graduation
  (the user said "no, stop doing that" — respect it).

Injectable clock + path + atomic persistence → unit-tests with no disk beyond a
tmp file.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_ROOT, "data", "routine_graduation.json")


@dataclass
class GraduationRecord:
    routine_id: str
    accepts: int = 0
    rejects: int = 0
    reverted: bool = False
    graduated: bool = False
    first_seen: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class GraduationTracker:
    def __init__(self, path: str = _DEFAULT_PATH, *,
                 threshold: int = 3,
                 now_fn: Callable[[], float] = time.time):
        self._path = path
        self._threshold = max(1, int(threshold))
        self._now = now_fn
        self._recs: dict[str, GraduationRecord] = {}
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    for d in json.load(f).get("records", []):
                        r = GraduationRecord(**{
                            k: d[k] for k in GraduationRecord.__dataclass_fields__
                            if k in d})
                        self._recs[r.routine_id] = r
        except Exception as e:
            log.warning("[graduation] load failed: %s", e)

    def _save(self) -> None:
        try:
            from core.atomic_io import write_atomic_json
            write_atomic_json(self._path,
                              {"records": [r.to_dict() for r in self._recs.values()]})
        except Exception as e:
            log.warning("[graduation] save failed: %s", e)

    def _rec(self, rid: str) -> GraduationRecord:
        r = self._recs.get(rid)
        if r is None:
            r = GraduationRecord(routine_id=rid, first_seen=self._now(),
                                 updated=self._now())
            self._recs[rid] = r
        return r

    # -- signals --------------------------------------------------------

    def record_accept(self, rid: str) -> bool:
        """User accepted the offer once. Returns True if this accept graduated
        it (crossed the threshold, never reverted)."""
        r = self._rec(rid)
        if r.reverted:
            self._save()
            return False           # reverted routines never re-graduate
        r.accepts += 1
        r.updated = self._now()
        newly = (not r.graduated and r.accepts >= self._threshold)
        if newly:
            r.graduated = True
        self._save()
        return newly

    def record_reject(self, rid: str) -> None:
        r = self._rec(rid)
        r.rejects += 1
        r.updated = self._now()
        self._save()

    def record_revert(self, rid: str) -> None:
        """The user undid an auto-run routine — stop it and never re-graduate."""
        r = self._rec(rid)
        r.reverted = True
        r.graduated = False
        r.updated = self._now()
        self._save()

    # -- queries --------------------------------------------------------

    def is_graduated(self, rid: str) -> bool:
        r = self._recs.get(rid)
        return bool(r and r.graduated and not r.reverted)

    def graduated_routines(self) -> list[str]:
        return [r.routine_id for r in self._recs.values()
                if r.graduated and not r.reverted]

    def status(self, rid: str) -> Optional[GraduationRecord]:
        return self._recs.get(rid)


# ── module singleton ────────────────────────────────────────────────── #

_TRACKER: Optional[GraduationTracker] = None


def get_tracker() -> GraduationTracker:
    global _TRACKER
    if _TRACKER is None:
        _TRACKER = GraduationTracker()
    return _TRACKER
