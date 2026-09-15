"""Tests for the Goal System (core.goal_system) + the orchestrator's new
resume/park hooks. Injectable clock + scripted fake agent — no disk, no model.
See docs/AERIS_AUTONOMOUS_YEAR_PLAN.md (Q1·M2).
"""

import os

from core.agent_orchestrator import (
    AgentAction,
    AgentOrchestrator,
    AgentResult,
    AgentStep,
    parse_agent_action,
)
from core.goal_system import (
    Goal,
    GoalStore,
    advance,
    looks_like_goal,
)


# ── capture ───────────────────────────────────────────────────────

def test_looks_like_goal():
    assert looks_like_goal("yaad dilana Rahul ko follow up karna hai")
    assert looks_like_goal("help me plan a Goa trip")
    assert looks_like_goal("keep an eye on the cricket score")
    assert not looks_like_goal("torch on karo")
    assert not looks_like_goal("aaj mausam kaisa hai")
    # A TIMED reminder must NOT be captured — it belongs to the reminder skill.
    assert not looks_like_goal("remind me at 5pm to call the plumber")
    assert not looks_like_goal("subah 7 baje yaad dilana")


def test_capture_creates_goal(tmp_path):
    store = GoalStore(str(tmp_path / "goals.json"))
    g = store.capture("follow up with Rahul about the flat")
    assert g is not None and g.state == "captured"
    assert store.get(g.id) is g


def test_capture_ignores_one_shot(tmp_path):
    store = GoalStore(str(tmp_path / "goals.json"))
    assert store.capture("open chrome") is None
    # and a timed reminder flows past capture to the real reminder skill
    assert store.capture("remind me at 6pm to call mom") is None
    assert store.all() == []


# ── persistence ───────────────────────────────────────────────────

def test_persistence_round_trip(tmp_path):
    path = str(tmp_path / "goals.json")
    s1 = GoalStore(path)
    g = s1.capture("follow up with Rahul about the flat")
    assert os.path.exists(path)
    s2 = GoalStore(path)  # fresh load from disk
    reloaded = s2.get(g.id)
    assert reloaded is not None
    assert reloaded.text == g.text and reloaded.state == "captured"


# ── transitions + scheduling ──────────────────────────────────────

def test_park_and_due_with_fake_clock(tmp_path):
    clock = {"t": 1000.0}
    store = GoalStore(str(tmp_path / "goals.json"), now_fn=lambda: clock["t"])
    g = store.add(Goal(text="check flights"))
    store.park(g, "need_time", ask="I'll look again at 6pm",
               resume_at=2000.0)
    assert g.state == "blocked" and g.blocker == "need_time"
    assert store.due() == []          # not yet
    clock["t"] = 2500.0
    assert store.due() == [g]         # now due
    assert g in store.resumable()


def test_awaiting_confirmation_returns_recent_need_user(tmp_path):
    clock = {"t": 1000.0}
    store = GoalStore(str(tmp_path / "goals.json"), now_fn=lambda: clock["t"])
    a = store.add(Goal(text="confirm A"))
    store.park(a, "need_user", ask="Pakka A?")
    clock["t"] = 1100.0
    b = store.add(Goal(text="confirm B"))
    store.park(b, "need_user", ask="Pakka B?")
    # most recently parked wins
    assert store.awaiting_confirmation().id == b.id
    # a need_time park is not a confirmation
    c = store.add(Goal(text="later"))
    store.park(c, "need_time")
    assert store.awaiting_confirmation().id == b.id


def test_awaiting_confirmation_recency_window(tmp_path):
    clock = {"t": 1000.0}
    store = GoalStore(str(tmp_path / "goals.json"), now_fn=lambda: clock["t"])
    g = store.add(Goal(text="old confirm"))
    store.park(g, "need_user", ask="Pakka?")
    clock["t"] = 1000.0 + 400          # 400s later
    assert store.awaiting_confirmation(within_s=300) is None   # too old
    assert store.awaiting_confirmation() is not None           # no window → found


def test_complete_and_drop(tmp_path):
    store = GoalStore(str(tmp_path / "goals.json"))
    g = store.add(Goal(text="x"))
    store.complete(g)
    assert g.state == "done" and not g.is_open
    g2 = store.add(Goal(text="y"))
    store.drop(g2)
    assert g2.state == "dropped"


# ── orchestrator: park + resume ───────────────────────────────────

def test_parse_block_action():
    a = parse_agent_action(
        '{"tool":"block","reason":"need_user","ask":"Konsi date?"}')
    assert a.kind == "block"
    assert a.args["reason"] == "need_user"
    assert a.args["ask"] == "Konsi date?"


def test_orchestrator_parks_on_block():
    # model immediately parks asking for input
    def llm(goal, steps):
        return '{"tool":"block","reason":"need_user","ask":"Kis din?"}'
    orch = AgentOrchestrator(llm, lambda n, a: "")
    res = orch.run("plan trip")
    assert res.stopped_reason == "blocked"
    assert res.block_reason == "need_user"
    assert res.reply == "Kis din?"


def test_orchestrator_resumes_with_prior_steps():
    seen = {}

    def llm(goal, steps):
        seen["n"] = len(steps)          # sees the restored trace
        return '{"tool":"final","reply":"done"}'

    orch = AgentOrchestrator(llm, lambda n, a: "")
    prior = [AgentStep(AgentAction(kind="tool", name="search",
                                   args={}), "found 3 flights")]
    res = orch.run("book flight", prior_steps=prior)
    assert seen["n"] == 1               # prior step was restored
    assert res.stopped_reason == "final"


# ── advance(): result → lifecycle ─────────────────────────────────

class FakeOrch:
    def __init__(self, result):
        self._result = result
        self.calls = []

    def run(self, text, prior_steps=None, approved=None):
        self.calls.append((text, list(prior_steps or []), approved))
        return self._result


def test_advance_final_completes(tmp_path):
    store = GoalStore(str(tmp_path / "goals.json"))
    g = store.add(Goal(text="do thing"))
    res = AgentResult(reply="ho gaya", steps=[], stopped_reason="final")
    advance(store, g, FakeOrch(res))
    assert g.state == "done"


def test_advance_block_parks_with_reason(tmp_path):
    clock = {"t": 100.0}
    store = GoalStore(str(tmp_path / "goals.json"), now_fn=lambda: clock["t"])
    g = store.add(Goal(text="plan trip"))
    res = AgentResult(reply="Kis din jaana hai?", steps=[],
                      stopped_reason="blocked", block_reason="need_user")
    advance(store, g, FakeOrch(res))
    assert g.state == "blocked" and g.blocker == "need_user"
    assert g.ask == "Kis din jaana hai?"


def test_advance_need_time_schedules_resume(tmp_path):
    clock = {"t": 100.0}
    store = GoalStore(str(tmp_path / "goals.json"), now_fn=lambda: clock["t"])
    g = store.add(Goal(text="watch score"))
    res = AgentResult(reply="baad mein dekhunga", steps=[],
                      stopped_reason="blocked", block_reason="need_time")
    advance(store, g, FakeOrch(res), resume_delay_s=500.0)
    assert g.check_in_at == 600.0       # 100 + 500
    clock["t"] = 700.0
    assert store.due() == [g]


def test_advance_persists_scratchpad_for_resume(tmp_path):
    path = str(tmp_path / "goals.json")
    store = GoalStore(path)
    g = store.add(Goal(text="research"))
    steps = [AgentStep(AgentAction(kind="tool", name="search", args={"q": "goa"}),
                       "3 results")]
    res = AgentResult(reply="need more", steps=steps, stopped_reason="blocked",
                      block_reason="need_user")
    advance(store, g, FakeOrch(res))
    # scratchpad serialized on the goal + survives a reload
    assert g.scratchpad and g.scratchpad[0]["action"]["name"] == "search"
    reloaded = GoalStore(path).get(g.id)
    assert reloaded.scratchpad[0]["observation"] == "3 results"


def test_advance_approve_last_preapproves_parked_action(tmp_path):
    store = GoalStore(str(tmp_path / "goals.json"))
    g = store.add(Goal(text="delete the thing"))
    g.scratchpad = [{"action": {"name": "delete_thing", "args": {}},
                     "observation": "AWAITING CONFIRMATION", "blocked": True}]
    orch = FakeOrch(AgentResult(reply="done", steps=[], stopped_reason="final"))
    advance(store, g, orch, approve_last=True)
    # the parked action name was passed as approved so the gate won't re-ask
    assert orch.calls[-1][2] == {"delete_thing"}
    assert g.state == "done"


def test_advance_without_approve_passes_none(tmp_path):
    store = GoalStore(str(tmp_path / "goals.json"))
    g = store.add(Goal(text="x"))
    orch = FakeOrch(AgentResult(reply="ok", steps=[], stopped_reason="final"))
    advance(store, g, orch)
    assert orch.calls[-1][2] is None


def test_advance_budget_parks_need_tool(tmp_path):
    store = GoalStore(str(tmp_path / "goals.json"))
    g = store.add(Goal(text="hard task"))
    res = AgentResult(reply="ran out", steps=[], stopped_reason="budget")
    advance(store, g, FakeOrch(res))
    assert g.state == "blocked" and g.blocker == "need_tool"
