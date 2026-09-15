"""Self-Model — AERIS's read-only view of itself (Blueprint Month 1).

An agent that feels like a mind knows its own state, abilities, and limits. This
module federates what AERIS already tracks — its skills, live telemetry, the
action ledger, active goals, and autonomy level — into one introspective
``SelfState`` and answers "tu kya kar sakta hai / abhi kya kar raha hai / kaisa
hai / kya nahi kar sakta".

Read-only by design: it never changes anything, so it's safe to call anywhere
and it can't be a source of bugs. Injectable providers → unit-tests with fakes,
no engine/model/disk.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

_BOOT_TS = time.time()


@dataclass
class SelfState:
    awake: bool = True
    autonomy: str = "normal"        # "normal" | "halted (panic)"
    skills_count: int = 0
    capabilities: dict = field(default_factory=dict)  # class -> count
    active_goals: list = field(default_factory=list)  # [{text, state}]
    recent_actions: list = field(default_factory=list)  # [{action, why}]
    recent_errors: list = field(default_factory=list)
    confidence: float = 1.0         # 0..1 from recent success rate
    mood: str = "focused"
    memory_size: int = 0
    uptime_s: float = 0.0

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


class SelfModel:
    def __init__(self, *,
                 skills_provider: Optional[Callable[[], Any]] = None,
                 ledger_provider: Optional[Callable[[], Any]] = None,
                 goals_provider: Optional[Callable[[], Any]] = None,
                 telemetry_provider: Optional[Callable[[], Any]] = None,
                 panic_provider: Optional[Callable[[], bool]] = None,
                 now_fn: Callable[[], float] = time.time):
        self._skills = skills_provider or _default_skills
        self._ledger = ledger_provider or _default_ledger
        self._goals = goals_provider or _default_goals
        self._telemetry = telemetry_provider or _default_telemetry
        self._panic = panic_provider or _default_panic
        self._now = now_fn

    # -- the snapshot ---------------------------------------------------

    def snapshot(self) -> SelfState:
        st = SelfState(uptime_s=max(0.0, self._now() - _BOOT_TS))
        # panic / autonomy
        try:
            st.awake = not self._panic()
            st.autonomy = "halted (panic)" if self._panic() else "normal"
        except Exception:
            pass
        # capabilities (skills grouped by autonomy class)
        try:
            names = list(self._safe(self._skills) or {})
            st.skills_count = len(names)
            st.capabilities = _group_capabilities(names)
        except Exception:
            pass
        # active goals
        try:
            store = self._safe(self._goals)
            if store is not None:
                st.active_goals = [
                    {"text": g.text, "state": g.state}
                    for g in store.open_goals()][:8]
        except Exception:
            pass
        # ledger: recent actions + error rate → confidence
        try:
            led = self._safe(self._ledger)
            if led is not None:
                recent = led.recent(12)
                st.recent_actions = [
                    {"action": e.get("action"), "why": e.get("why")}
                    for e in recent
                    if e.get("decision") == "allow"][-5:]
                errs = [e for e in recent
                        if e.get("decision") == "deny"
                        or str(e.get("result", "")).startswith("ERROR")]
                st.recent_errors = [
                    str(e.get("action") or e.get("result")) for e in errs][-5:]
                total = max(1, len(recent))
                st.confidence = round(1.0 - len(errs) / total, 2)
        except Exception:
            pass
        # memory size + mood
        try:
            tel = self._safe(self._telemetry)
            if tel is not None:
                st.memory_size = int(tel() if callable(tel) else tel)
        except Exception:
            pass
        st.mood = _mood_from(st.confidence, len(st.active_goals))
        return st

    # -- natural-language self-description ------------------------------

    def describe(self, question: str = "") -> str:
        q = (question or "").lower()
        st = self.snapshot()
        if any(w in q for w in ("kya kar raha", "abhi kya", "doing", "busy")):
            if st.active_goals:
                acting = [g for g in st.active_goals if g["state"] == "acting"]
                if acting:
                    return "Abhi ye kaam kar raha hoon: " + \
                        ", ".join(g["text"] for g in acting[:2]) + "."
                return f"{len(st.active_goals)} goals pending hain; abhi sun " \
                       "raha hoon."
            return "Abhi kuch specific nahi — sun raha hoon, bolo."
        if any(w in q for w in ("kya kar sakta", "can you", "capabilit",
                                "kya kar sakte")):
            top = sorted(st.capabilities.items(), key=lambda x: -x[1])[:5]
            caps = ", ".join(f"{k}" for k, _ in top)
            return f"{st.skills_count}+ kaam kar sakta hoon — jaise: {caps}. " \
                   "Aur bahut kuch; bas bolo."
        if any(w in q for w in ("kaisa hai", "kaise ho", "how are")):
            return f"Main {st.mood} hoon, confidence {int(st.confidence*100)}%. " \
                   f"{'Sab normal.' if st.awake else 'Autonomy abhi halted hai.'}"
        if any(w in q for w in ("kyun", "why")) and st.recent_actions:
            a = st.recent_actions[-1]
            return f"Aakhri kaam '{a['action']}' — {a['why']}"
        # default self-summary
        return (f"Main {st.mood} hoon ({int(st.confidence*100)}% confident), "
                f"{st.skills_count}+ skills, {len(st.active_goals)} active goals. "
                f"{'Autonomy normal.' if st.awake else 'PANIC: autonomy off.'}")

    @staticmethod
    def _safe(provider: Callable[[], Any]) -> Any:
        try:
            return provider()
        except Exception as e:
            log.debug("[self] provider unavailable: %s", e)
            return None


# ── helpers ─────────────────────────────────────────────────────────── #

def _group_capabilities(names: list[str]) -> dict:
    out: dict[str, int] = {}
    try:
        from core.autonomy import classify
    except Exception:
        return {"skills": len(names)}
    for n in names:
        c = classify(n)
        out[c] = out.get(c, 0) + 1
    return out


def _mood_from(confidence: float, n_goals: int) -> str:
    if confidence < 0.5:
        return "thoda struggling"
    if n_goals >= 4:
        return "busy"
    if confidence >= 0.9:
        return "focused"
    return "steady"


# ── default providers (lazy, borrow the live singletons) ────────────── #

def _default_skills() -> Any:
    from core.skill_registry import all_skills
    return all_skills()


def _default_ledger() -> Any:
    from core.autonomy import get_gate
    return get_gate().ledger


def _default_goals() -> Any:
    from core.goal_system import get_goal_store
    return get_goal_store()


def _default_telemetry() -> Any:
    from core import telemetry
    return telemetry.kg_size()


def _default_panic() -> bool:
    from core.autonomy import get_gate
    return get_gate()._is_panic()


# ── module singleton ────────────────────────────────────────────────── #

_SELF: Optional[SelfModel] = None


def get_self_model() -> SelfModel:
    global _SELF
    if _SELF is None:
        _SELF = SelfModel()
    return _SELF
