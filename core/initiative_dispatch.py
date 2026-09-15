"""Initiative dispatch — the bridge from "AERIS decided to act" to it happening.

The Initiative Engine (``core.initiative_engine``) decides WHAT is worth
surfacing and WHETHER to surface it now (salience × ladder × quiet-hours ×
anti-nag). It returns Initiatives but doesn't *do* anything with them. This maps
a surfaced Initiative to a concrete effect:

* ``notify_user`` (and anything unrecognised) → just speak the text.
* ``resume_goal`` → actually resume the parked/due goal via the agent
  (``goal_system.advance``) and speak whatever it reports back — so "pehle
  poocha tha, ab dekhun?" turns into real work, not just a reminder.

The routing/authorisation already happened in the engine (an ACT only reaches
here once the Trust Gate allowed it), so this layer is pure execution. Injectable
(goal store + orchestrator pass in) → unit-tests with fakes, no engine or model.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

log = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    text: str                       # what AERIS should say (may be "")
    acted: bool = False             # did we do more than notify?
    goal_id: Optional[str] = None   # the goal we resumed, if any
    kind: str = ""                  # the initiative kind, for logging


def _default_goals():
    from core.goal_system import get_goal_store
    return get_goal_store()


def dispatch(initiative, *, goals: Any = None,
             orchestrator: Any = None) -> DispatchResult:
    """Execute one surfaced Initiative. Never raises — a dispatch hiccup must
    not take down the surfacing loop; it degrades to a plain notification."""
    kind = getattr(initiative, "kind", "")
    text = getattr(initiative, "text", "") or ""
    action = getattr(initiative, "action", "notify_user")
    goal_id = getattr(initiative, "goal_id", None)

    if action == "resume_goal" and goal_id:
        try:
            store = goals or _default_goals()
            g = store.get(goal_id)
            if g is None or not getattr(g, "is_open", True):
                # goal already done/dropped — nothing to resume, don't nag
                return DispatchResult(text="", acted=False, kind=kind)
            if orchestrator is None:
                # no agent to work it → fall back to just reminding
                return DispatchResult(text=text, acted=False, goal_id=goal_id,
                                      kind=kind)
            from core import goal_system
            res = goal_system.advance(store, g, orchestrator)
            reply = getattr(res, "reply", "") or text
            return DispatchResult(text=reply, acted=True, goal_id=goal_id,
                                  kind=kind)
        except Exception as e:
            log.debug("[initiative] resume_goal dispatch failed: %s", e)
            return DispatchResult(text=text, acted=False, goal_id=goal_id,
                                  kind=kind)

    # notify_user and everything else: surface the text as-is.
    return DispatchResult(text=text, acted=False, kind=kind)
