"""Routine offers — the bridge that closes the learning loop.

``core.routine_learner`` only *suggests* routines. ``core.routine_graduation``
tracks which suggestions the user has repeatedly accepted (and never reverted).
This module joins the two so the rest of AERIS sees a single, trust-aware view:

* ``pending_offers()`` — suggestions the user still needs to decide on. Anything
  the user **reverted** is suppressed (they said "stop" — don't nag again) and
  anything already **graduated** drops out of the yes/no list.
* ``active_routines()`` — graduated suggestions turned into *runnable* specs the
  scheduler can fire on its own (``enabled=True``, ``autonomy_level=3``).
* ``accept`` / ``reject`` / ``revert`` — thin feedback hooks the GUI calls; each
  funnels the signal into the graduation tracker and reports what changed.

Trust-before-autonomy is enforced here, not assumed: a routine only auto-enables
if **every** action is reversible/harmless (``_SAFE_AUTO_KINDS``). A graduated
routine that would message/pay/open/delete stays confirm-gated — the same spirit
as the Autonomy Ladder's HARD_CAP on irreversible classes. So graduation earns
*less friction*, never a blank cheque.

Pure and injectable (records, learner fn, tracker, clock all pass in) → unit-
tests with no camera, disk, model, or wall clock.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.routine_learner import Suggestion, learn_from_journal
from core.routine_graduation import GraduationTracker, get_tracker

log = logging.getLogger(__name__)

# Action kinds that are safe to fire without a human in the loop: reversible,
# non-destructive, no outbound side effects. Everything else keeps needing a
# confirmation even after a routine graduates.
_SAFE_AUTO_KINDS = frozenset({"notify", "tts", "speak", "log", "summary",
                              "recap", "brief"})

# The autonomy level a graduated, all-safe routine runs at (L3 = act + notify).
_GRADUATED_LEVEL = 3


@dataclass(frozen=True)
class Offer:
    """A suggestion joined with its graduation progress, for the GUI card."""
    suggestion: Suggestion
    accepts: int
    threshold: int
    reverted: bool
    graduated: bool

    @property
    def key(self) -> str:
        return self.suggestion.key

    @property
    def accepts_left(self) -> int:
        return max(0, self.threshold - self.accepts)


def _tracker(tracker: Optional[GraduationTracker]) -> GraduationTracker:
    return tracker if tracker is not None else get_tracker()


def _suggestions(records: Optional[List[Dict[str, Any]]],
                 learner: Optional[Callable[..., List[Suggestion]]],
                 now: Optional[datetime]) -> List[Suggestion]:
    fn = learner or learn_from_journal
    try:
        return fn(records, now=now) if records is not None else fn(now=now)
    except TypeError:
        # a learner that doesn't take now= (e.g. a test stub)
        return fn(records) if records is not None else fn()


def _safe_to_auto(spec: Dict[str, Any]) -> bool:
    actions = spec.get("actions") or []
    return bool(actions) and all(
        (a.get("kind") in _SAFE_AUTO_KINDS) for a in actions)


# ── the joined views ────────────────────────────────────────────────── #

def all_offers(*, records: Optional[List[Dict[str, Any]]] = None,
               learner: Optional[Callable[..., List[Suggestion]]] = None,
               tracker: Optional[GraduationTracker] = None,
               now: Optional[datetime] = None) -> List[Offer]:
    """Every current suggestion joined with its graduation state."""
    tr = _tracker(tracker)
    out: List[Offer] = []
    for s in _suggestions(records, learner, now):
        rec = tr.status(s.key)
        out.append(Offer(
            suggestion=s,
            accepts=(rec.accepts if rec else 0),
            threshold=tr._threshold,
            reverted=bool(rec and rec.reverted),
            graduated=tr.is_graduated(s.key),
        ))
    return out


def pending_offers(*, records: Optional[List[Dict[str, Any]]] = None,
                   learner: Optional[Callable[..., List[Suggestion]]] = None,
                   tracker: Optional[GraduationTracker] = None,
                   now: Optional[datetime] = None) -> List[Offer]:
    """Offers the user still needs to act on: not yet graduated, not reverted.

    Sorted most-confident first so the GUI leads with the strongest pattern."""
    offers = [o for o in all_offers(records=records, learner=learner,
                                    tracker=tracker, now=now)
              if not o.graduated and not o.reverted]
    offers.sort(key=lambda o: o.suggestion.confidence, reverse=True)
    return offers


def active_routines(*, records: Optional[List[Dict[str, Any]]] = None,
                    learner: Optional[Callable[..., List[Suggestion]]] = None,
                    tracker: Optional[GraduationTracker] = None,
                    now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Runnable routine specs for suggestions that have graduated. Only routines
    whose every action is reversible auto-enable; a graduated-but-risky one is
    returned still-disabled and flagged so the caller confirms before firing."""
    tr = _tracker(tracker)
    specs: List[Dict[str, Any]] = []
    for s in _suggestions(records, learner, now):
        if not tr.is_graduated(s.key):
            continue
        spec = dict(s.routine_spec)          # copy — never mutate the learner's
        safe = _safe_to_auto(spec)
        spec["enabled"] = safe
        spec["autonomy_level"] = _GRADUATED_LEVEL
        spec["source"] = "graduated"
        spec["key"] = s.key
        if not safe:
            spec["needs_confirm"] = True     # graduated, but not a blank cheque
        specs.append(spec)
    return specs


# ── feedback hooks (what the GUI / voice layer calls) ───────────────── #

def accept(key: str, *, tracker: Optional[GraduationTracker] = None) -> bool:
    """User accepted an offer. Returns True if this accept *graduated* it."""
    newly = _tracker(tracker).record_accept(key)
    if newly:
        log.info("[offers] routine graduated to auto-run: %s", key)
    return newly


def reject(key: str, *, tracker: Optional[GraduationTracker] = None) -> None:
    """User dismissed an offer (soft no — it may resurface later)."""
    _tracker(tracker).record_reject(key)


def revert(key: str, *, tracker: Optional[GraduationTracker] = None) -> None:
    """User undid an auto-run routine (hard no — un-graduate + never re-offer)."""
    _tracker(tracker).record_revert(key)
    log.info("[offers] routine reverted, will not re-graduate: %s", key)
