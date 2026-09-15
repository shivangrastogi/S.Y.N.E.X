"""Goal System — standing intentions that outlive a single turn.

Q1·M2 of the Autonomous-Year plan (docs/AERIS_AUTONOMOUS_YEAR_PLAN.md).

Today the ReAct loop (`core.agent_orchestrator`) runs and finishes inside one
call. A goal here is a *persistent* objective with a lifecycle: it can be
captured from natural language, worked on, PARKED when it needs the user / more
time / a missing tool, and RESUMED later at the right moment.

State machine::

    captured ─► planning ─► acting ─┬─► done
                    ▲               ├─► dropped
                    └── blocked ◄───┘   (need_user | need_time | need_tool)

``advance(goal, orchestrator)`` runs one work session on a goal by driving the
orchestrator with the goal's restored scratchpad, then maps the result back
onto the goal's state (final→done, blocked→park, else keep acting). Everything
is injectable — the store path, the clock, and the orchestrator — so the whole
system unit-tests with a scripted fake agent and no disk/model.
"""
from __future__ import annotations

import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_PATH = os.path.join(_ROOT, "data", "goals.json")

STATES = ("captured", "planning", "acting", "blocked", "done", "dropped")
BLOCKERS = ("need_user", "need_time", "need_tool")


# ── the goal ────────────────────────────────────────────────────────── #

@dataclass
class Goal:
    text: str
    id: str = field(default_factory=lambda: "g_" + uuid.uuid4().hex[:8])
    state: str = "captured"
    blocker: Optional[str] = None          # one of BLOCKERS when state==blocked
    ask: Optional[str] = None              # question surfaced to the user
    plan: list = field(default_factory=list)      # [{"step":..., "done":bool}]
    scratchpad: list = field(default_factory=list)  # [{"action":..,"observation":..}]
    check_in_at: Optional[float] = None    # resume-at wall-clock (need_time)
    autonomy_level: int = 2                # default L2 (draft/confirm) per ladder
    owner_subagent: Optional[str] = None
    source: str = "voice"
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Goal":
        known = {k: d.get(k) for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)

    @property
    def is_open(self) -> bool:
        return self.state not in ("done", "dropped")


# ── natural-language capture ────────────────────────────────────────── #

# Phrases that mean "hold this and pursue it over time", not "do it once now"
# and NOT a timed reminder (those belong to the existing reminder/alarm skill,
# so bare "remind me / yaad dilana" is deliberately excluded to avoid hijacking
# them). The standing-intention verbs below don't collide with one-shot skills.
_CAPTURE_RE = re.compile(
    r"\b("
    r"follow[\s-]?up|"
    r"help me plan|plan (?:kar(?:o|na)|banao)|"
    r"keep an eye on|nazar rakh|dekhte rehna|khayal rakhna|"
    r"track karo|monitor|keep track|"
    r"pursue|work on this over|iske peeche"
    r")\b",
    re.I,
)


def looks_like_goal(text: str) -> bool:
    return bool(_CAPTURE_RE.search(text or ""))


# ── the store ───────────────────────────────────────────────────────── #

class GoalStore:
    """Persistent set of goals with the lifecycle transitions."""

    def __init__(self, path: str = _DEFAULT_PATH,
                 *, now_fn: Callable[[], float] = time.time):
        self._path = path
        self._now = now_fn
        self._goals: dict[str, Goal] = {}
        self._load()

    # -- persistence ---------------------------------------------------

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                import json
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for d in raw.get("goals", []):
                    g = Goal.from_dict(d)
                    self._goals[g.id] = g
        except Exception as e:
            log.warning("[goals] load failed: %s", e)

    def _save(self) -> None:
        try:
            from core.atomic_io import write_atomic_json
            write_atomic_json(
                self._path, {"goals": [g.to_dict() for g in self._goals.values()]})
        except Exception as e:
            log.warning("[goals] save failed: %s", e)

    # -- capture + CRUD ------------------------------------------------

    def capture(self, text: str, *, source: str = "voice",
                autonomy_level: int = 2) -> Optional[Goal]:
        """Create a goal from an utterance if it reads like a standing
        intention; else return None so normal one-shot handling continues."""
        text = (text or "").strip()
        if not text or not looks_like_goal(text):
            return None
        g = Goal(text=text, source=source, autonomy_level=autonomy_level)
        self._goals[g.id] = g
        self._save()
        return g

    def add(self, goal: Goal) -> Goal:
        self._goals[goal.id] = goal
        self._save()
        return goal

    def get(self, goal_id: str) -> Optional[Goal]:
        return self._goals.get(goal_id)

    def all(self) -> list[Goal]:
        return list(self._goals.values())

    def open_goals(self) -> list[Goal]:
        return [g for g in self._goals.values() if g.is_open]

    def by_state(self, state: str) -> list[Goal]:
        return [g for g in self._goals.values() if g.state == state]

    # -- transitions ---------------------------------------------------

    def _touch(self, g: Goal) -> None:
        g.updated = self._now()
        self._save()

    def transition(self, g: Goal, state: str) -> Goal:
        if state not in STATES:
            raise ValueError(f"bad state {state!r}")
        g.state = state
        if state != "blocked":
            g.blocker = None
            g.ask = None
        self._touch(g)
        return g

    def park(self, g: Goal, reason: str, ask: str = "",
             *, resume_at: Optional[float] = None) -> Goal:
        """Move a goal to blocked with a reason; optionally schedule a
        resume time (need_time)."""
        if reason not in BLOCKERS:
            reason = "need_user"
        g.state = "blocked"
        g.blocker = reason
        g.ask = ask or g.ask
        g.check_in_at = resume_at if resume_at is not None else g.check_in_at
        self._touch(g)
        return g

    def complete(self, g: Goal) -> Goal:
        return self.transition(g, "done")

    def drop(self, g: Goal) -> Goal:
        return self.transition(g, "dropped")

    # -- scheduling ----------------------------------------------------

    def due(self, now: Optional[float] = None) -> list[Goal]:
        """Goals parked on need_time whose resume moment has arrived."""
        t = self._now() if now is None else now
        return [g for g in self._goals.values()
                if g.state == "blocked" and g.blocker == "need_time"
                and g.check_in_at is not None and g.check_in_at <= t]

    def awaiting_confirmation(self, within_s: Optional[float] = None
                             ) -> Optional[Goal]:
        """The most-recently parked goal blocked on ``need_user`` — i.e. one
        that asked the user a yes/no. ``within_s`` limits it to a recently-asked
        one so an old parked goal can't hijack an unrelated "haan"."""
        t = self._now()
        cands = [g for g in self._goals.values()
                 if g.state == "blocked" and g.blocker == "need_user"
                 and (within_s is None or (t - g.updated) <= within_s)]
        return max(cands, key=lambda g: g.updated) if cands else None

    def resumable(self) -> list[Goal]:
        """Goals ready to be worked again: acting, planning, or captured, plus
        any need_time goals now due."""
        ready = [g for g in self._goals.values()
                 if g.state in ("captured", "planning", "acting")]
        return ready + self.due()


# ── advancing a goal via the orchestrator ───────────────────────────── #

def _steps_to_scratch(steps) -> list[dict]:
    out = []
    for s in steps:
        a = s.action
        out.append({
            "action": {"kind": a.kind, "name": a.name, "args": a.args,
                       "reply": a.reply},
            "observation": s.observation,
            "blocked": s.blocked,
        })
    return out


# Public name — main_engine persists a directly-run agent trace through this.
def steps_to_scratch(steps) -> list[dict]:
    return _steps_to_scratch(steps)


def declined_action(goal) -> tuple:
    """The (name, args) a parked goal was waiting on — for the ledger (§6.33).

    Lives here because the scratchpad's nested shape (`{"action": {"kind",
    "name", "args", ...}}`) is this module's format; reaching into it from the
    engine would put a second reader of a private layout in another file.

    Prefers the last **blocked** step, which is the one that actually asked for
    confirmation; falls back to the last step with a name so a differently
    shaped trace still yields something rather than nothing.
    """
    steps = list(getattr(goal, "scratchpad", None) or [])
    for want_blocked in (True, False):
        for d in reversed(steps):
            if not isinstance(d, dict):
                continue
            if want_blocked and not d.get("blocked"):
                continue
            a = d.get("action")
            if isinstance(a, dict) and a.get("name"):
                return str(a["name"]), dict(a.get("args") or {})
    return "", {}


def _scratch_to_steps(scratch: list[dict]):
    from core.agent_orchestrator import AgentAction, AgentStep
    steps = []
    for d in scratch or []:
        a = d.get("action", {})
        steps.append(AgentStep(
            action=AgentAction(kind=a.get("kind", "tool"), name=a.get("name"),
                               args=a.get("args") or {}, reply=a.get("reply")),
            observation=d.get("observation", ""),
            blocked=bool(d.get("blocked", False)),
        ))
    return steps


def advance(store: GoalStore, goal: Goal, orchestrator,
            *, resume_delay_s: float = 3600.0, approve_last: bool = False):
    """Run one work session on ``goal`` with ``orchestrator`` (anything with a
    ``run(text, prior_steps=..., approved=...)`` → AgentResult). Maps the result
    onto the goal's lifecycle and persists. Returns the AgentResult.

    ``approve_last=True`` (the user just said "haan" to a parked confirmation)
    pre-approves the action that parked the goal, so the gate won't re-ask."""
    store.transition(goal, "acting")
    prior = _scratch_to_steps(goal.scratchpad)
    approved = None
    if approve_last and goal.scratchpad:
        name = (goal.scratchpad[-1].get("action") or {}).get("name")
        if name:
            approved = {name}
    result = orchestrator.run(goal.text, prior_steps=prior, approved=approved)
    goal.scratchpad = _steps_to_scratch(result.steps)

    reason = result.stopped_reason
    if reason == "final":
        store.complete(goal)
    elif reason == "blocked":
        block = result.block_reason or "need_user"
        resume_at = (store._now() + resume_delay_s) if block == "need_time" else None
        store.park(goal, block, ask=result.reply, resume_at=resume_at)
    else:
        # budget / stuck / error / timeout → park for a retry, needs a tool or
        # more time rather than the user.
        store.park(goal, "need_tool", ask=result.reply)
    return result


# ── module singleton ────────────────────────────────────────────────── #

_STORE: Optional[GoalStore] = None


def get_goal_store() -> GoalStore:
    global _STORE
    if _STORE is None:
        _STORE = GoalStore()
    return _STORE


def configure(path: str = _DEFAULT_PATH) -> GoalStore:
    global _STORE
    _STORE = GoalStore(path)
    return _STORE


def capture_ack(goal: Goal) -> str:
    """A short Hinglish acknowledgement for a freshly captured goal."""
    t = goal.text
    if re.search(r"\b(plan|trip|research)\b", t, re.I):
        return f"Theek hai, ispe kaam shuru karta hoon: {t}"
    return f"Theek hai, yaad rakhunga: {t}"
