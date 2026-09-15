"""Agentic ReAct loop — the reasoning core that turns 100+ one-shot skills
into a planner that can solve multi-step problems.

The difference from :mod:`core.tool_router` (single shot) and the ``plan``
shape (blind fan-out) is the **observe loop**: after every tool call the
orchestrator feeds the *actual result* back to the model, which then decides
the next action. That is what lets it recover from failures, chain one
skill's output into the next, and stop when the goal is genuinely met.

Design goals
------------
* **Testable without Ollama.** Both the model call (``llm_step``) and the
  tool runner (``run_tool``) are injected callables, so the loop can be
  exercised with a scripted fake model in unit tests.
* **Safe.** Hard step budget, per-step wall-clock timeout, and a
  confirmation gate for destructive skills (shutdown, kill_process, …).
* **Graceful.** If the model never emits a clean action the loop bails out
  and returns the best observation so far rather than hanging.

Action protocol
---------------
Every model turn must be ONE JSON object — same family as ToolRouter, plus
a terminal ``final`` form::

    {"tool": "<name>", "args": {...}}          # call a skill, see its result
    {"tool": "final", "reply": "<text>"}       # done — this is the answer
    {"tool": "chat",  "reply": "<text>"}       # treated as final too

The loop appends each ``(action, observation)`` pair to a scratchpad that is
handed back to the model on the next turn.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from core.reflection import no_progress as _no_progress
from core.tool_router import _extract_json

log = logging.getLogger(__name__)


# Skills that change system state irreversibly enough to warrant a yes/no
# before the agent fires them autonomously. Matched by exact skill name.
DESTRUCTIVE_SKILLS: frozenset[str] = frozenset({
    "shutdown_pc", "restart_pc", "sleep_pc", "lock_screen",
    "kill_process", "vault_delete", "forget_command",
})


@dataclass
class AgentAction:
    kind: str                       # "tool" | "final" | "noop"
    name: Optional[str] = None
    args: dict = field(default_factory=dict)
    reply: Optional[str] = None


@dataclass
class AgentStep:
    """One (action, observation) pair in the trace."""
    action: AgentAction
    observation: str
    blocked: bool = False
    # Set when the step needs the user before it can proceed (gate → confirm):
    # the loop PARKS the whole run to ask, rather than flailing on.
    park_reason: Optional[str] = None
    park_reply: Optional[str] = None


@dataclass
class AgentResult:
    reply: str
    steps: list[AgentStep] = field(default_factory=list)
    stopped_reason: str = "final"   # final|budget|timeout|stuck|error|blocked
    block_reason: Optional[str] = None  # set when stopped_reason == "blocked"

    @property
    def tool_calls(self) -> int:
        return sum(1 for s in self.steps if s.action.kind == "tool")


def parse_agent_action(raw: str) -> AgentAction:
    """Parse one model turn into a structured action. Tolerates fences/prose."""
    if not raw or not raw.strip():
        return AgentAction(kind="noop")
    obj = _extract_json(raw)
    if not obj:
        # Bare prose with no JSON → treat as the final answer.
        return AgentAction(kind="final", reply=raw.strip())

    tool = obj.get("tool")
    if tool in ("final", "chat", "answer", "done"):
        reply = str(obj.get("reply") or obj.get("answer") or "").strip()
        return AgentAction(kind="final", reply=reply or None)
    # Q1·M2: a goal can PARK itself when it needs the user, more time, or a
    # tool it doesn't have — the runtime resumes it later.
    if tool in ("block", "pause", "ask", "wait"):
        reason = str(obj.get("reason") or "need_user").strip()
        ask = str(obj.get("ask") or obj.get("reply") or "").strip()
        return AgentAction(kind="block", args={"reason": reason, "ask": ask})
    if isinstance(tool, str) and tool:
        args = obj.get("args")
        if not isinstance(args, dict):
            args = {}
        return AgentAction(kind="tool", name=tool, args=args)
    # JSON without a usable "tool" key → if it carries a reply, finish on it.
    reply = obj.get("reply")
    if isinstance(reply, str) and reply.strip():
        return AgentAction(kind="final", reply=reply.strip())
    return AgentAction(kind="noop")


# Type aliases for the injected collaborators.
#   llm_step(goal, scratchpad) -> raw model text
#   run_tool(name, args)       -> observation string
#   confirm(name, args)        -> bool  (may be None → auto-deny destructive)
LLMStep = Callable[[str, list[AgentStep]], Optional[str]]
RunTool = Callable[[str, dict], str]
Confirm = Callable[[str, dict], bool]


class AgentOrchestrator:
    """Runs the observe/act loop. Stateless across goals; create once, reuse."""

    def __init__(
        self,
        llm_step: LLMStep,
        run_tool: RunTool,
        *,
        confirm: Optional[Confirm] = None,
        max_steps: int = 6,
        step_timeout_s: float = 20.0,
        total_budget_s: float = 90.0,
        destructive: frozenset[str] = DESTRUCTIVE_SKILLS,
        authorize: Optional[Callable[[str, dict], object]] = None,
        record: Optional[Callable[[str, dict, str, str, str], None]] = None,
        reflect: Optional[Callable[[str, "AgentResult"], None]] = None,
    ):
        self.llm_step = llm_step
        self.run_tool = run_tool
        self.confirm = confirm
        self.max_steps = max(1, int(max_steps))
        self.step_timeout_s = float(step_timeout_s)
        self.total_budget_s = float(total_budget_s)
        self.destructive = destructive
        # Q3·M7 Reflexion: an optional critic hook called once with the final
        # result of every run — distils a lesson into memory. Injected so the
        # loop still unit-tests with no reflection/memory module.
        self.reflect = reflect
        # Q1·M3 governance: when wired, every tool call is authorized by the
        # Autonomy Ladder (allow / confirm / deny) and logged to the Ledger.
        #   authorize(name, args) -> object with .outcome ('allow'|'confirm'|
        #                            'deny') and .why
        #   record(name, args, decision, why, result) -> None
        # Both injected so the loop still unit-tests with no autonomy module.
        self.authorize = authorize
        self.record = record

    # ── public API ────────────────────────────────────────────────

    def run(self, goal: str,
            *, prior_steps: Optional[list[AgentStep]] = None,
            approved: Optional[set] = None) -> AgentResult:
        """Drive the loop until the model finishes, parks itself, the budget
        runs out, or it gets stuck repeating itself.

        ``prior_steps`` resumes a parked goal: its saved trace is restored so
        the model continues where it left off (Q1·M2). ``approved`` is the set
        of action names the user OK'd when the goal was parked for
        confirmation — the gate won't re-ask for these on resume."""
        result = self._run_inner(goal, prior_steps=prior_steps,
                                 approved=approved)
        # Q3·M7 Reflexion: hand the finished run to the critic (best-effort).
        if self.reflect is not None:
            try:
                self.reflect(goal, result)
            except Exception as e:
                log.debug("[agent] reflect hook failed: %s", e)
        return result

    def _run_inner(self, goal: str,
                   *, prior_steps: Optional[list[AgentStep]] = None,
                   approved: Optional[set] = None) -> AgentResult:
        self._approved = set(approved or ())
        steps: list[AgentStep] = list(prior_steps or [])
        started = time.monotonic()
        last_signature: Optional[tuple] = None
        repeat_count = 0
        reflected = False               # one self-correcting nudge per run

        for _ in range(self.max_steps):
            if time.monotonic() - started > self.total_budget_s:
                return self._wrap(steps, "budget")

            raw = self._safe_llm_step(goal, steps)
            action = parse_agent_action(raw or "")

            if action.kind == "final":
                return AgentResult(
                    reply=action.reply or self._best_observation(steps)
                    or "Ho gaya, sir.",
                    steps=steps,
                    stopped_reason="final",
                )

            if action.kind == "block":
                ask = action.args.get("ask") or "Ismein aapki madad chahiye."
                return AgentResult(
                    reply=ask, steps=steps, stopped_reason="blocked",
                    block_reason=action.args.get("reason") or "need_user",
                )

            if action.kind == "noop":
                # Model produced nothing usable. Give it one nudge, else bail.
                if last_signature == ("noop",):
                    return self._wrap(steps, "stuck")
                last_signature = ("noop",)
                continue

            # action.kind == "tool"
            signature = (action.name, _freeze(action.args))
            if signature == last_signature:
                repeat_count += 1
                if repeat_count >= 2:
                    # Looping on the identical call — stop before it spins.
                    return self._wrap(steps, "stuck")
            else:
                repeat_count = 0
            last_signature = signature

            step = self._run_tool_step(action)
            steps.append(step)
            if step.park_reason:
                return AgentResult(
                    reply=step.park_reply or "Ismein confirmation chahiye.",
                    steps=steps, stopped_reason="blocked",
                    block_reason=step.park_reason,
                )

            # Q3·M7 Reflexion: semantic no-progress guard. First time the run
            # stalls, don't just bail — inject ONE self-critique nudge so the
            # model can step back and try a different approach (the actual power
            # of Reflexion). If it stalls again after reflecting, then stop.
            if _no_progress(steps):
                if not reflected:
                    steps.append(self._reflection_step(goal, steps))
                    reflected = True
                    last_signature = None      # let it try something fresh
                    repeat_count = 0
                    continue
                return self._wrap(steps, "stuck")

        return self._wrap(steps, "budget")

    # ── internals ─────────────────────────────────────────────────

    def _run_tool_step(self, action: AgentAction) -> AgentStep:
        name = action.name or ""

        # ── governance: Autonomy Ladder + Ledger (Q1·M3), when wired ──
        why = ""
        if self.authorize is not None:
            d = self.authorize(name, dict(action.args))
            outcome = getattr(d, "outcome", "allow")
            why = getattr(d, "why", "")
            if outcome == "deny":
                self._log(name, action.args, "deny", why, "BLOCKED")
                return AgentStep(
                    action=action,
                    observation=f"BLOCKED: '{name}' not allowed ({why}).",
                    blocked=True,
                )
            if outcome == "confirm" and name not in getattr(
                    self, "_approved", set()):
                if not bool(self.confirm and self.confirm(name, action.args)):
                    # Not a denial — it just needs the user's OK. Park the run
                    # and ask, instead of blocking-and-flailing.
                    self._log(name, action.args, "confirm", why, "PARKED")
                    ask = (f"'{name}' karne se pehle confirmation chahiye"
                           f"{(' — ' + why) if why else ''}. "
                           f"Bolo 'haan' ya 'cancel'.")
                    return AgentStep(
                        action=action,
                        observation=f"AWAITING CONFIRMATION: '{name}'.",
                        blocked=True, park_reason="need_user", park_reply=ask,
                    )
        # legacy fallback when no gate is wired: the curated destructive set.
        elif name in self.destructive:
            allowed = bool(self.confirm and self.confirm(name, action.args))
            if not allowed:
                return AgentStep(
                    action=action,
                    observation=f"BLOCKED: '{name}' needs explicit user "
                                f"confirmation and was not approved.",
                    blocked=True,
                )

        deadline = time.monotonic() + self.step_timeout_s
        try:
            obs = self.run_tool(name, dict(action.args))
        except Exception as e:  # a skill blowing up must not kill the agent
            log.warning("[agent] tool %r raised: %s", name, e)
            obs = f"ERROR: tool '{name}' failed: {e}"
        if time.monotonic() > deadline:
            log.info("[agent] tool %r overran step timeout", name)
        obs = (obs or "(no output)").strip()
        if self.authorize is not None:
            self._log(name, action.args, "allow", why, obs[:80])
        return AgentStep(action=action, observation=obs)

    def _log(self, name: str, args: dict, decision: str, why: str,
             result: str) -> None:
        if self.record is None:
            return
        try:
            self.record(name, dict(args or {}), decision, why, result)
        except Exception as e:  # logging must never break the loop
            log.debug("[agent] ledger record failed: %s", e)

    def _reflection_step(self, goal: str, steps: list[AgentStep]) -> AgentStep:
        """A synthetic in-trace nudge the model reads on its next turn. Not a
        tool call — it carries the critic's read of *why* the run is stuck and
        asks for a fundamentally different approach."""
        try:
            from core.reflection import critique
            note = critique(goal, steps).note
        except Exception:
            note = "aage nahi badh raha"
        hint = (f"REFLECTION: ab tak jo try kiya usse baat nahi bani ({note}). "
                f"Ek kadam peeche hato aur bilkul alag tareeka socho — "
                f"wahi tool dubara mat chalao.")
        return AgentStep(action=AgentAction(kind="reflect"), observation=hint)

    def _safe_llm_step(self, goal: str, steps: list[AgentStep]) -> Optional[str]:
        try:
            return self.llm_step(goal, steps)
        except Exception as e:
            log.warning("[agent] llm_step raised: %s", e)
            return None

    def _wrap(self, steps: list[AgentStep], reason: str) -> AgentResult:
        return AgentResult(
            reply=self._best_observation(steps) or "Poora nahi kar paaya, sir.",
            steps=steps,
            stopped_reason=reason,
        )

    @staticmethod
    def _best_observation(steps: list[AgentStep]) -> str:
        for step in reversed(steps):
            if step.action.kind == "reflect":
                continue                       # synthetic nudge, not a result
            if not step.blocked and step.observation and not step.observation.startswith("ERROR"):
                return step.observation
        # fall back to the last real (non-reflect) step's observation
        for step in reversed(steps):
            if step.action.kind != "reflect":
                return step.observation
        return ""


def _freeze(d: dict) -> tuple:
    """Hashable signature of an args dict for loop-detection."""
    try:
        return tuple(sorted((str(k), str(v)) for k, v in (d or {}).items()))
    except Exception:
        return tuple()
