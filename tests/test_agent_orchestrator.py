"""Tests for the agentic ReAct loop (core.agent_orchestrator).

No Ollama required — the model call and tool runner are injected, so we
script the model's turns and assert the loop observes/acts/stops correctly.
"""

import json

import pytest

from core.agent_orchestrator import (
    AgentOrchestrator,
    AgentResult,
    parse_agent_action,
)


# ── action parsing ────────────────────────────────────────────────

def test_parse_tool_call():
    a = parse_agent_action('{"tool": "get_weather", "args": {"city": "Delhi"}}')
    assert a.kind == "tool"
    assert a.name == "get_weather"
    assert a.args == {"city": "Delhi"}


def test_parse_final():
    a = parse_agent_action('{"tool": "final", "reply": "Done sir"}')
    assert a.kind == "final"
    assert a.reply == "Done sir"


def test_parse_chat_is_terminal():
    a = parse_agent_action('{"tool": "chat", "reply": "hello"}')
    assert a.kind == "final"


def test_parse_fenced_json():
    a = parse_agent_action('```json\n{"tool": "ocr_screen", "args": {}}\n```')
    assert a.kind == "tool"
    assert a.name == "ocr_screen"


def test_parse_bare_prose_is_final():
    a = parse_agent_action("I think we are all done here.")
    assert a.kind == "final"
    assert "done" in a.reply


def test_parse_empty_is_noop():
    assert parse_agent_action("").kind == "noop"
    assert parse_agent_action("   ").kind == "noop"


# ── helpers ────────────────────────────────────────────────────────

def _scripted_llm(turns):
    """Return an llm_step that emits `turns[i]` on the i-th call, ignoring args."""
    state = {"i": 0}

    def step(goal, scratchpad):
        i = state["i"]
        state["i"] += 1
        if i < len(turns):
            return turns[i]
        return '{"tool": "final", "reply": "fallback"}'

    return step


# ── the loop ───────────────────────────────────────────────────────

def test_single_tool_then_final():
    """Model calls one tool, sees the result, then finishes."""
    calls = []

    def run_tool(name, args):
        calls.append((name, args))
        return "Delhi: 31C, clear"

    llm = _scripted_llm([
        '{"tool": "get_weather", "args": {"city": "Delhi"}}',
        '{"tool": "final", "reply": "Delhi is 31C and clear."}',
    ])
    agent = AgentOrchestrator(llm, run_tool)
    res = agent.run("what's the weather in Delhi")

    assert isinstance(res, AgentResult)
    assert res.stopped_reason == "final"
    assert res.tool_calls == 1
    assert calls == [("get_weather", {"city": "Delhi"})]
    assert "31C" in res.reply


def test_multi_step_chaining():
    """Output of step 1 should be observable; loop runs several tools."""
    observed_scratchpads = []

    def llm(goal, scratchpad):
        observed_scratchpads.append(len(scratchpad))
        n = len(scratchpad)
        if n == 0:
            return '{"tool": "system_stats", "args": {}}'
        if n == 1:
            return '{"tool": "append_note", "args": {"text": "logged"}}'
        return '{"tool": "final", "reply": "Stats logged."}'

    def run_tool(name, args):
        return f"ran {name}"

    agent = AgentOrchestrator(llm, run_tool)
    res = agent.run("log my system stats")

    assert res.tool_calls == 2
    assert res.stopped_reason == "final"
    # The model saw a growing scratchpad: 0, then 1, then 2 prior steps.
    assert observed_scratchpads == [0, 1, 2]


def test_step_budget_enforced():
    """A model that never finishes is capped at max_steps tool calls."""
    llm = _scripted_llm([
        '{"tool": "noop_skill", "args": {"i": 1}}',
        '{"tool": "noop_skill", "args": {"i": 2}}',
        '{"tool": "noop_skill", "args": {"i": 3}}',
        '{"tool": "noop_skill", "args": {"i": 4}}',
    ])
    # distinct results each turn → genuine apparent progress, so the run is
    # capped purely by the step budget (not the no-progress guard).
    agent = AgentOrchestrator(llm, lambda n, a: f"result {a.get('i')}",
                              max_steps=3)
    res = agent.run("loop forever")

    assert res.tool_calls == 3
    assert res.stopped_reason == "budget"


def test_reflection_nudge_lets_model_recover():
    """When the run stalls, the loop injects ONE self-critique nudge; a model
    that heeds it and changes course recovers (the point of Reflexion)."""
    def llm(goal, steps):
        # once a reflection appears in the trace, switch to a working answer
        if any(s.action.kind == "reflect" for s in steps):
            return '{"tool": "final", "reply": "alag tareeke se ho gaya"}'
        n = sum(1 for s in steps if s.action.kind == "tool")
        return f'{{"tool": "t{n}", "args": {{}}}}'   # distinct failing tools

    agent = AgentOrchestrator(llm, lambda n, a: "ERROR: nope", max_steps=8)
    res = agent.run("solve it")
    assert res.stopped_reason == "final"
    assert res.reply == "alag tareeke se ho gaya"
    assert any(s.action.kind == "reflect" for s in res.steps)


def test_reflection_nudge_is_one_shot_then_stuck():
    """A model that stays stuck even after the nudge is stopped as 'stuck', and
    is nudged exactly once — no infinite reflection."""
    def llm(goal, steps):
        n = sum(1 for s in steps if s.action.kind == "tool")
        return f'{{"tool": "t{n}", "args": {{}}}}'   # always a new failing tool

    agent = AgentOrchestrator(llm, lambda n, a: "ERROR: nope", max_steps=12)
    res = agent.run("impossible")
    assert res.stopped_reason == "stuck"
    assert sum(1 for s in res.steps if s.action.kind == "reflect") == 1


def test_identical_call_loop_detected():
    """Repeating the exact same call is stopped as 'stuck'."""
    llm = _scripted_llm([
        '{"tool": "spin", "args": {"x": 1}}',
        '{"tool": "spin", "args": {"x": 1}}',
        '{"tool": "spin", "args": {"x": 1}}',
    ])
    agent = AgentOrchestrator(llm, lambda n, a: "same", max_steps=10)
    res = agent.run("spin")

    assert res.stopped_reason == "stuck"
    assert res.tool_calls <= 3


def test_tool_exception_does_not_crash():
    """A skill that raises becomes an ERROR observation, not a crash."""
    def run_tool(name, args):
        raise RuntimeError("boom")

    llm = _scripted_llm([
        '{"tool": "explode", "args": {}}',
        '{"tool": "final", "reply": "Couldn\'t do it."}',
    ])
    agent = AgentOrchestrator(llm, run_tool)
    res = agent.run("explode please")

    assert res.tool_calls == 1
    assert res.steps[0].observation.startswith("ERROR")
    assert res.stopped_reason == "final"


def test_destructive_skill_blocked_without_confirm():
    """Destructive skills are auto-denied when no confirm callback is given."""
    ran = []
    llm = _scripted_llm([
        '{"tool": "shutdown_pc", "args": {}}',
        '{"tool": "final", "reply": "Stopped."}',
    ])
    agent = AgentOrchestrator(llm, lambda n, a: ran.append(n) or "did it")
    res = agent.run("shut down the pc")

    assert ran == []                         # tool never actually ran
    assert res.steps[0].blocked is True
    assert "BLOCKED" in res.steps[0].observation


def test_destructive_skill_runs_with_confirm():
    ran = []
    llm = _scripted_llm([
        '{"tool": "shutdown_pc", "args": {}}',
        '{"tool": "final", "reply": "Shutting down."}',
    ])
    agent = AgentOrchestrator(
        llm,
        lambda n, a: ran.append(n) or "shutting down",
        confirm=lambda n, a: True,
    )
    res = agent.run("shut down the pc")

    assert ran == ["shutdown_pc"]
    assert res.steps[0].blocked is False


def test_llm_unavailable_bails_gracefully():
    """If the model call returns None every turn, the loop ends without hanging."""
    agent = AgentOrchestrator(lambda g, s: None, lambda n, a: "x", max_steps=4)
    res = agent.run("anything")
    assert isinstance(res.reply, str) and res.reply
    assert res.stopped_reason in ("stuck", "budget")


# ── Q1·M3 governance: Autonomy Ladder + Ledger wiring ──────────────

class _Dec:
    """Duck-typed decision like core.autonomy.Decision."""
    def __init__(self, outcome, why="why"):
        self.outcome, self.why = outcome, why


def _governed(authorize, *, confirm=None, record=None, ran=None):
    def llm(goal, steps):
        # call one tool, then finish once there's an observation
        return ('{"tool": "final", "reply": "done"}' if steps
                else '{"tool": "delete_thing", "args": {"x": 1}}')

    def run(name, args):
        if ran is not None:
            ran.append(name)
        return "did " + name

    return AgentOrchestrator(llm, run, confirm=confirm,
                             authorize=authorize, record=record)


def test_gate_allow_runs_and_logs():
    ran, logged = [], []
    o = _governed(lambda n, a: _Dec("allow", "device @ Act"),
                  record=lambda *x: logged.append(x), ran=ran)
    o.run("x")
    assert "delete_thing" in ran
    assert any(row[2] == "allow" for row in logged)     # decision field


def test_gate_deny_blocks_and_logs():
    ran, logged = [], []
    res = None
    o = _governed(lambda n, a: _Dec("deny", "not allowed"),
                  record=lambda *x: logged.append(x), ran=ran)
    res = o.run("x")
    assert "delete_thing" not in ran                    # never executed
    assert any(row[2] == "deny" for row in logged)
    assert any(s.blocked for s in res.steps)


def test_gate_confirm_approved_runs():
    ran = []
    o = _governed(lambda n, a: _Dec("confirm"),
                  confirm=lambda n, a: True, ran=ran)
    o.run("x")
    assert "delete_thing" in ran


def test_gate_confirm_declined_parks_to_ask():
    # confirm needed + no approval → PARK the run and ask the user (need_user),
    # not silently block-and-continue. The tool must not have run.
    ran = []
    o = _governed(lambda n, a: _Dec("confirm", "irreversible"),
                  confirm=lambda n, a: False, ran=ran)
    res = o.run("x")
    assert "delete_thing" not in ran
    assert res.stopped_reason == "blocked"
    assert res.block_reason == "need_user"
    assert "confirmation" in res.reply.lower() or "haan" in res.reply.lower()


def test_gate_confirm_no_callback_parks():
    # with no confirm callback at all, a confirm decision parks (asks) too
    ran = []
    o = _governed(lambda n, a: _Dec("confirm"), confirm=None, ran=ran)
    res = o.run("x")
    assert "delete_thing" not in ran
    assert res.block_reason == "need_user"


def test_approved_action_bypasses_confirm_on_resume():
    # the user already said "haan" → the action is pre-approved, so the gate's
    # "confirm" no longer parks; it runs.
    ran = []
    o = _governed(lambda n, a: _Dec("confirm"), confirm=None, ran=ran)
    res = o.run("x", approved={"delete_thing"})
    assert "delete_thing" in ran
    assert res.stopped_reason == "final"


def test_no_gate_keeps_legacy_destructive_behavior():
    # Without a gate, the curated destructive set still guards (backward compat)
    ran = []
    o = _governed(None, confirm=lambda n, a: True, ran=ran)  # delete_thing not
    o.run("x")                                               # in destructive →
    assert "delete_thing" in ran                            # runs freely
