"""Reflexion — the ④ critic node the ReAct loop lacks (Year-plan Q3·M7).

After the agent acts, a cheap self-critique asks the three questions the raw
observe/act loop never does: *did this advance the goal? is the result
plausible? what should change next time?* Two concrete jobs:

1. **No-progress detector** (``no_progress``) — the orchestrator already stops on
   an *identical* repeated call, but not on the subtler stall where the model
   keeps trying *different* tools that all fail or return nothing. This catches
   that and lets the loop bail early instead of burning the whole budget.

2. **Outcome → durable lesson** (``reflect_on_outcome`` / ``learn``) — when a
   goal finishes (especially when it *fails*), distil one line of experience
   ("break this into sub-goals", "tool X kept failing — try another") and write
   it to Memory Fabric so future planning recalls it. This is the self-improving
   loop: the agent gets better at its own recurring tasks.

Everything is heuristic-first (works with **no** LLM, so it's fast and always
available) and optionally sharpened by an injected ``llm``. Steps are duck-typed
(``.observation`` / ``.blocked`` / ``.action.name``) so this module never
imports the orchestrator — no cycle. Pure + injectable → unit-tests with plain
namespaces and a fake fabric.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

log = logging.getLogger(__name__)

# Outcomes that mean the run failed to reach the goal (worth a lesson). A
# "blocked" run is parked for the user — not a failure — so it's excluded.
_FAILURE = frozenset({"budget", "stuck", "timeout", "error"})


def _bad_obs(step: Any) -> bool:
    """A step that carried the run nowhere: blocked, errored, or empty."""
    if getattr(step, "blocked", False):
        return True
    obs = (getattr(step, "observation", "") or "").strip()
    return (not obs) or obs == "(no output)" or obs.upper().startswith("ERROR") \
        or obs.startswith("BLOCKED") or obs.startswith("AWAITING")


def _name(step: Any) -> str:
    return getattr(getattr(step, "action", None), "name", None) or ""


# ── 1. no-progress detector ─────────────────────────────────────────── #

def no_progress(steps: List[Any], *, window: int = 3) -> bool:
    """True when the last ``window`` steps show no advance — every one bad, or
    every one producing the *same* observation (a semantic loop even if the
    tool names differ). Returns False until there are ``window`` steps, so a
    short run is never cut off prematurely."""
    tail = list(steps or [])[-window:]
    if len(tail) < window:
        return False
    if all(_bad_obs(s) for s in tail):
        return True
    obs = [(getattr(s, "observation", "") or "").strip() for s in tail]
    return len(set(obs)) == 1 and obs[0] != ""


# ── 2. critique (the three questions) ───────────────────────────────── #

@dataclass(frozen=True)
class Critique:
    progressed: bool
    plausible: bool
    stuck: bool
    note: str = ""


def critique(goal: str, steps: List[Any]) -> Critique:
    """A heuristic read of where the run stands — cheap enough to call each
    step. ``progressed`` = the latest step produced a usable result;
    ``stuck`` = the no-progress detector fired.

    ``note`` is the one field anything consumes: `AgentOrchestrator
    ._reflection_step` folds it into the synthetic nudge the model reads on
    its next turn. So the stuck note names the goal — a 1.5B model re-planning
    from "aage nahi badh raha" alone has to re-derive what it was even trying
    to do, and the whole point of the nudge is to redirect it toward that.

    (``goal`` was accepted and ignored until 2026-09-01 — §6.34's scan. The
    fix is deliberately confined to the consumed field: `plausible` is still
    an alias of `progressed`, because inventing a goal-relevance signal that
    nothing reads would add risk to the agent's hot path for no benefit.)
    """
    steps = list(steps or [])
    last = steps[-1] if steps else None
    progressed = bool(last) and not _bad_obs(last)
    stuck = no_progress(steps)
    plausible = progressed
    if not steps:
        note = "koi step nahi — plan hi nahi bana"
    elif stuck:
        target = _short(goal, 40)
        note = (f"aage nahi badh raha — '{target}' ke liye approach badalni "
                f"chahiye" if target else
                "aage nahi badh raha — approach badalni chahiye")
    elif progressed:
        note = "theek chal raha hai"
    else:
        note = "last step se kuch nahi nikla"
    return Critique(progressed=progressed, plausible=plausible, stuck=stuck,
                    note=note)


# ── 3. outcome → durable lesson ─────────────────────────────────────── #

@dataclass(frozen=True)
class Lesson:
    text: str
    kind: str            # "failure" | "success" | "caution"
    salience: float      # 0..1 — how much to weight it in recall


def _short(goal: str, n: int = 60) -> str:
    g = (goal or "").strip()
    return g if len(g) <= n else g[:n - 1] + "…"


def reflect_on_outcome(goal: str, steps: List[Any], outcome: str, *,
                       llm: Optional[Callable[[str], str]] = None
                       ) -> Optional[Lesson]:
    """Distil one line of experience from a finished run, or None if there's
    nothing worth remembering (a trivial one-shot success, or a run parked for
    the user). Heuristic by default; an injected ``llm`` only *rewrites* the
    heuristic lesson's wording, never invents the verdict."""
    steps = list(steps or [])
    if not steps or outcome == "blocked":
        return None

    tool_steps = [s for s in steps if getattr(getattr(s, "action", None),
                                              "kind", "") == "tool"]
    names = [_name(s) for s in tool_steps]
    repeated = len(names) != len(set(names))
    all_bad = bool(tool_steps) and all(_bad_obs(s) for s in tool_steps)
    g = _short(goal)

    lesson: Optional[Lesson] = None
    if outcome in _FAILURE:
        if repeated:
            bad = next((n for n in names if names.count(n) > 1), names[-1] if names else "")
            text = (f"'{g}' ke liye baar-baar '{bad}' try kiya par kaam nahi hua — "
                    f"agli baar alag tareeka.")
        elif all_bad:
            last = tool_steps[-1]
            text = (f"'{g}' mein '{_name(last)}' fail hota raha — iske liye "
                    f"koi aur approach chahiye.")
        else:
            text = (f"'{g}' step-budget mein poora nahi hua — ise chhote "
                    f"sub-goals mein todna better rahega.")
        lesson = Lesson(text=text, kind="failure", salience=0.7)
    elif outcome == "final" and len(tool_steps) >= 2 and not all_bad:
        # a non-trivial success worth remembering as a recipe
        chain = " → ".join(n for n in names if n) or "kuch steps"
        text = f"'{g}' aise hua: {chain}. Agli baar yahi sequence kaam karega."
        lesson = Lesson(text=text, kind="success", salience=0.4)
    # trivial one-shot success (len<2) → nothing worth storing

    if lesson is None:
        return None

    if llm is not None:
        try:
            prompt = ("Ek line mein, Hinglish, is seekh ko saaf-suthra likho "
                      f"(koi extra text nahi):\n{lesson.text}")
            refined = (llm(prompt) or "").strip().splitlines()[0].strip()
            if 8 <= len(refined) <= 200:
                lesson = Lesson(text=refined, kind=lesson.kind,
                                salience=lesson.salience)
        except Exception as e:
            log.debug("[reflect] llm refine skipped: %s", e)
    return lesson


def _default_fabric() -> Any:
    from core import memory_fabric
    return memory_fabric.get_fabric()


def record_lesson(lesson: Lesson, *,
                  fabric_provider: Optional[Callable[[], Any]] = None) -> bool:
    """Persist a lesson into Memory Fabric so future planning recalls it."""
    if lesson is None:
        return False
    provider = fabric_provider or _default_fabric
    try:
        provider().remember(f"Lesson: {lesson.text}", kind="note")
        log.info("[reflect] lesson stored (%s): %s", lesson.kind, lesson.text)
        return True
    except Exception as e:
        log.debug("[reflect] record failed: %s", e)
        return False


def learn(goal: str, steps: List[Any], outcome: str, *,
          llm: Optional[Callable[[str], str]] = None,
          fabric_provider: Optional[Callable[[], Any]] = None) -> Optional[Lesson]:
    """Reflect on a finished run and, if there's a lesson, store it. Returns the
    Lesson (stored) or None. Best-effort: never raises into the caller."""
    try:
        lesson = reflect_on_outcome(goal, steps, outcome, llm=llm)
    except Exception as e:
        log.debug("[reflect] reflect failed: %s", e)
        return None
    if lesson is None:
        return None
    record_lesson(lesson, fabric_provider=fabric_provider)
    return lesson
