"""Graduated routines → live automations (the last mile of the learning loop).

``core.routine_offers.active_routines()`` reports which learned routines have
earned auto-run trust. This module **materializes** the safe, enabled ones into
the real ``core.automation.AutomationEngine`` so they actually fire on their
cron — and **retires** the ones the user reverted or that lost graduation.

Design guarantees:

* **Idempotent.** Every routine this creates is tagged ``[grad:<key>]`` in its
  description. Re-syncing reconciles against that tag: nothing is duplicated,
  and a reverted routine's live automation is removed.
* **Hands off the user's routines.** Only tagged routines are ever touched — a
  routine the user built by hand is never enabled, disabled, or deleted here.
* **Trust-gated by construction.** ``active_routines()`` only enables all-safe
  (reversible) routines; a graduated-but-risky one arrives ``enabled=False`` and
  is *not* materialized, so it can't fire without a confirmation.

Pure orchestration over injected collaborators (the engine + the offers fn), so
it unit-tests with a tmp-file AutomationEngine and a scripted learner — no real
cron thread, camera, or model.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from core.automation import Action, Trigger

log = logging.getLogger(__name__)

_MARK_RE = re.compile(r"\[grad:(?P<key>.+?)\]")


def _mark(key: str) -> str:
    return f"[grad:{key}]"


def _key_of(routine) -> Optional[str]:
    """The offer key a routine was materialized from, or None if it wasn't."""
    m = _MARK_RE.search(getattr(routine, "description", "") or "")
    return m.group("key") if m else None


def _spec_to_trigger(spec: Dict[str, Any]) -> Trigger:
    t = spec.get("trigger") or {}
    return Trigger(kind=t.get("kind", "manual"), params=dict(t.get("params") or {}))


def _spec_to_actions(spec: Dict[str, Any]) -> List[Action]:
    return [Action(kind=a.get("kind", "notify"), params=dict(a.get("params") or {}))
            for a in (spec.get("actions") or [])]


def sync(engine, *, offers_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
         records=None, learner=None, tracker=None, now=None) -> Dict[str, list]:
    """Reconcile the AutomationEngine's *graduated* routines with what has
    currently earned auto-run trust.

    Returns ``{"created": [...], "retired": [...], "kept": [...]}`` (offer keys).
    """
    if offers_fn is None:
        from core.routine_offers import active_routines as offers_fn  # lazy

    active = offers_fn(records=records, learner=learner, tracker=tracker, now=now)
    # Only the safe, already-enabled graduates become live automations. A
    # needs_confirm one stays out of the executor entirely.
    desired = {s["key"]: s for s in active
               if s.get("enabled") and s.get("key")}

    existing: Dict[str, Any] = {}
    for r in engine.list_routines():
        k = _key_of(r)
        if k is not None:
            existing[k] = r

    created, retired, kept = [], [], []

    # Create newly-graduated routines.
    for key, spec in desired.items():
        if key in existing:
            # already live — make sure it's enabled, then leave it be
            r = existing[key]
            if not r.enabled:
                engine.set_enabled(r.id, True)
            kept.append(key)
            continue
        desc = (spec.get("description") or "AERIS learned this from your routine")
        engine.create_routine(
            name=spec.get("name") or key,
            trigger=_spec_to_trigger(spec),
            actions=_spec_to_actions(spec),
            description=f"{desc} {_mark(key)}",
            enabled=True,
        )
        created.append(key)
        log.info("[graduated] materialized auto-routine: %s", key)

    # Retire routines that are no longer graduated (reverted / un-graduated).
    for key, r in existing.items():
        if key not in desired:
            engine.delete_routine(r.id)
            retired.append(key)
            log.info("[graduated] retired reverted auto-routine: %s", key)

    return {"created": created, "retired": retired, "kept": kept}
