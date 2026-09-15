"""Initiative Engine — the "awakening" (Blueprint Month 4 / Year Q2·M5).

This is what turns AERIS from reactive into self-starting: it decides, on its
own, WHAT is worth surfacing and WHETHER to surface it right now — then routes
each candidate through the Autonomy Ladder (act / offer / drop). It is the
make-or-break piece: an agent that interrupts badly is deleted, so the whole
design is about *salience* and restraint, not more notifications.

Salience = importance × timeliness × confidence × user_openness  (all 0..1).
Routing (governed by `TrustGate`):
    high salience + ladder allows autonomous act  → ACT
    medium salience                               → OFFER (surface a yes/no)
    low salience / quiet hours / nagged too much  → DROP (silence is a feature)

Candidate sources (pluggable):
  * Due goals  — a goal parked on need_time whose moment has arrived → resurface
    (this alone delivers the Q1 north-star: "Rahul follow-up" comes back).
  * Extra sources — callables returning Initiatives (world-model events land here
    later: unread-important-mail, leave-now, deadline radar…).

Pure + injectable (clock, goal store, gate, de-dup memory) → unit-tests with
fakes; no engine, model, or disk.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

log = logging.getLogger(__name__)

ACT, OFFER, DROP = "act", "offer", "drop"


@dataclass
class Initiative:
    text: str                       # what AERIS would say / offer
    kind: str                       # "goal_resume" | "reminder" | ...
    action: str = "notify_user"     # the tool/class this maps to (for the gate)
    importance: float = 0.6
    timeliness: float = 0.6
    confidence: float = 0.7
    openness: float = 0.6           # learned: does the user act on this kind?
    source_id: str = ""             # for de-dup
    goal_id: Optional[str] = None
    requested_level: int = 2        # L2 offer by default
    # filled by the engine:
    salience: float = 0.0
    route: str = DROP
    why: str = ""

    def score(self) -> float:
        return round(self.importance * self.timeliness *
                     self.confidence * self.openness, 4)


class InitiativeEngine:
    def __init__(self, *,
                 goals_provider: Optional[Callable[[], object]] = None,
                 gate_provider: Optional[Callable[[], object]] = None,
                 extra_sources: Optional[list] = None,
                 now_fn: Callable[[], float] = time.time,
                 act_threshold: float = 0.28,
                 offer_threshold: float = 0.12,
                 cooldown_s: float = 3600.0,
                 max_per_hour: int = 4,
                 openness_provider: Optional[Callable[[str], Optional[float]]] = None):
        self._goals = goals_provider or _default_goals
        self._gate = gate_provider or _default_gate
        self._extra = extra_sources or []
        # P4: learned per-kind openness overrides a source's hand-tuned default
        # once real evidence exists (returns None until then).
        self._openness = openness_provider
        self._now = now_fn
        self.act_threshold = act_threshold
        self.offer_threshold = offer_threshold
        self.cooldown_s = cooldown_s
        self.max_per_hour = max_per_hour
        # de-dup + anti-nag memory: source_id -> last-surfaced ts, and a rolling
        # list of surface timestamps.
        self._surfaced: dict[str, float] = {}
        self._surface_log: list[float] = []
        # what AERIS currently wants to say (for the Mind dashboard). Kept but
        # NOT auto-spoken yet — proactive speech is wired only after on-device
        # quiet-hours/DND verification (trust before autonomy).
        self._pending: list[Initiative] = []

    # -- candidate gathering --------------------------------------------

    def candidates(self) -> list[Initiative]:
        out: list[Initiative] = []
        # 1) due goals → resurface
        store = _safe(self._goals)
        if store is not None:
            try:
                for g in store.due():
                    out.append(Initiative(
                        text=f"Aapne kaha tha: {g.text}. Ab dekhein?",
                        kind="goal_resume", action="resume_goal",
                        importance=0.75, timeliness=1.0, confidence=0.85,
                        openness=0.7, source_id=f"goal:{g.id}", goal_id=g.id,
                        requested_level=2))
            except Exception as e:
                log.debug("[initiative] goals source failed: %s", e)
        # 2) pluggable extra sources (world-model events, later)
        for src in self._extra:
            try:
                out.extend(src() or [])
            except Exception as e:
                log.debug("[initiative] extra source failed: %s", e)
        return out

    # -- the decision ----------------------------------------------------

    def tick(self, now: Optional[float] = None) -> list[Initiative]:
        """Score, route, de-dup, and budget candidates. Returns only the
        Initiatives that should be surfaced right now (act or offer)."""
        t = self._now() if now is None else now
        self._prune(t)
        surfaced: list[Initiative] = []
        cands = self.candidates()
        for c in cands:
            self._apply_openness(c)
        for c in sorted(cands, key=lambda x: -x.score()):
            c.salience = c.score()
            c.route = self._route(c, t)
            if c.route == DROP:
                continue
            # anti-nag: don't repeat the same thing within the cooldown, and
            # cap how many interruptions per hour.
            last = self._surfaced.get(c.source_id)
            if last is not None and (t - last) < self.cooldown_s:
                continue
            if len(self._surface_log) >= self.max_per_hour:
                break  # budget spent for this hour
            surfaced.append(c)
            self._mark(c, t)
        if surfaced:
            self._pending = (self._pending + surfaced)[-10:]
        return surfaced

    def preview(self, now: Optional[float] = None) -> list[dict]:
        """READ-ONLY view of what tick() would surface right now — same scoring
        and routing, but NO marking, NO budget consumption, NO pending append.
        The dashboard polls this; a GET must never mutate anti-nag state."""
        t = self._now() if now is None else now
        out: list[dict] = []
        cands = self.candidates()
        for c in cands:
            self._apply_openness(c)
        for c in sorted(cands, key=lambda x: -x.score()):
            c.salience = c.score()
            route = self._route(c, t)
            if route == DROP:
                continue
            last = self._surfaced.get(c.source_id)
            if last is not None and (t - last) < self.cooldown_s:
                continue
            out.append({"text": c.text, "kind": c.kind, "route": route,
                        "salience": c.salience})
        return out

    def pending(self) -> list[dict]:
        """What AERIS currently wants to surface (for the Mind dashboard)."""
        return [{"text": i.text, "kind": i.kind, "route": i.route,
                 "salience": i.salience} for i in self._pending]

    def clear_pending(self) -> None:
        self._pending = []

    def _apply_openness(self, c: Initiative) -> None:
        if self._openness is None:
            return
        try:
            v = self._openness(c.kind)
            if v is not None:
                c.openness = float(v)
        except Exception:
            pass

    def _route(self, c: Initiative, t: float) -> str:
        if c.salience < self.offer_threshold:
            return DROP
        gate = _safe(self._gate)
        # Quiet hours silence ALL proactive surfacing (not just L3+ acts) —
        # an offer at 3am is still an interruption. "Silence is a feature."
        if gate is not None:
            try:
                if gate._in_quiet(t):
                    return DROP
            except Exception:
                pass
        # An autonomous ACT must clear both the salience bar and the ladder.
        if c.salience >= self.act_threshold and gate is not None:
            try:
                d = gate.authorize(c.action, c.requested_level, now=t)
                if d.outcome == "allow":
                    c.why = f"salience {c.salience}; {d.why}"
                    return ACT
                if d.outcome == "deny":
                    # gate forbids acting AND (quiet hours) → hold entirely
                    if "PANIC" in d.why or "Quiet" in d.why:
                        return DROP
            except Exception as e:
                log.debug("[initiative] gate failed: %s", e)
        c.why = f"salience {c.salience}; offered"
        return OFFER

    # -- de-dup / anti-nag memory ---------------------------------------

    def _mark(self, c: Initiative, t: float) -> None:
        self._surfaced[c.source_id] = t
        self._surface_log.append(t)

    def _prune(self, t: float) -> None:
        # rolling 1-hour window for the anti-nag budget
        self._surface_log = [ts for ts in self._surface_log if t - ts < 3600.0]

    def note_openness(self, source_kind: str, acted: bool) -> None:
        """Hook for learning loop 1: the user acted on / dismissed this kind of
        nudge. (Wired to feedback later; kept here so the shape exists.)"""
        # Stored in memory fabric as a preference in a later milestone.
        log.debug("[initiative] openness %s acted=%s", source_kind, acted)


def _safe(provider: Callable[[], object]):
    try:
        return provider()
    except Exception:
        return None


def _default_goals():
    from core.goal_system import get_goal_store
    return get_goal_store()


def _default_gate():
    from core.autonomy import get_gate
    return get_gate()


# ── module singleton ────────────────────────────────────────────────── #

_ENGINE: Optional[InitiativeEngine] = None


def get_engine() -> InitiativeEngine:
    global _ENGINE
    if _ENGINE is None:
        # Default sources: due goals (built in) + the World Model's
        # "goal blocked needing your input" (lazy import avoids a cycle).
        def _world_src():
            try:
                from core.world_model import situation_initiatives
                return situation_initiatives()
            except Exception:
                return []

        # Continual-learning loop: a once-a-day "retrain due" offer when the
        # brain-health advisor says the corpus has outgrown the model.
        def _learning_src():
            try:
                from core.brain_health import initiative_candidates
                return initiative_candidates()
            except Exception:
                return []

        # Time-of-day Mode nudge: "raat ho rahi hai — sleep mode chalu karu?"
        # (only offers a mode that exists and isn't already active).
        def _mode_src():
            try:
                from core.mode_suggestion import mode_suggestion_source
                return mode_suggestion_source()
            except Exception:
                return []

        # P4: learned openness (None until a kind has real evidence).
        def _learned(kind):
            try:
                from core.openness import get_store
                return get_store().learned(kind)
            except Exception:
                return None
        # Earned trust: "'app' 12 baar bina dikkat chala — L2 se L3 karu?"
        # A NOTIFY only — raising autonomy is the one decision that must never
        # be taken autonomously (§6.32).
        def _trust_src():
            try:
                from core.trust_promotion import initiative_candidates
                return initiative_candidates()
            except Exception:
                return []

        _ENGINE = InitiativeEngine(
            extra_sources=[_world_src, _learning_src, _mode_src, _trust_src],
            openness_provider=_learned)
    return _ENGINE
