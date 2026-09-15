"""Initiative dispatch (core.initiative_dispatch) — the act-on-initiative
bridge. Fake goal store + orchestrator, no engine or model.
"""
from types import SimpleNamespace as NS

from core import initiative_dispatch as disp


def _ini(action="notify_user", text="hello", kind="k", goal_id=None):
    return NS(action=action, text=text, kind=kind, goal_id=goal_id)


def _real_store(tmp_path, *, goals=()):
    """A real GoalStore (advance() needs its transition/park/complete)."""
    from core.goal_system import GoalStore, Goal
    store = GoalStore(str(tmp_path / "goals.json"))
    for text, gid in goals:
        g = Goal(text=text, id=gid)
        store.add(g)
    return store


class FakeAdvanceOrch:
    """Stands in for the agent; goal_system.advance calls .run() on it."""
    def __init__(self, reply):
        self.reply = reply
        self.ran = 0

    def run(self, text, prior_steps=None, approved=None):
        self.ran += 1
        return NS(reply=self.reply, steps=[], stopped_reason="final")


# ── notify path ───────────────────────────────────────────────────────

def test_notify_just_speaks_text():
    res = disp.dispatch(_ini(action="notify_user", text="battery low"))
    assert res.text == "battery low"
    assert res.acted is False


def test_unknown_action_degrades_to_notify():
    res = disp.dispatch(_ini(action="do_a_flip", text="hmm"))
    assert res.text == "hmm" and res.acted is False


# ── resume_goal path ──────────────────────────────────────────────────

def test_resume_goal_advances_and_speaks_reply(tmp_path):
    store = _real_store(tmp_path, goals=[("check score", "g1")])
    orch = FakeAdvanceOrch("kaam aage badha diya")
    res = disp.dispatch(_ini(action="resume_goal", text="ab dekhun?",
                             goal_id="g1"),
                        goals=store, orchestrator=orch)
    assert orch.ran == 1
    assert res.acted is True and res.goal_id == "g1"
    assert res.text == "kaam aage badha diya"
    assert store.get("g1").state == "done"      # advance completed it


def test_resume_missing_goal_is_silent(tmp_path):
    store = _real_store(tmp_path)               # g1 never existed
    orch = FakeAdvanceOrch("x")
    res = disp.dispatch(_ini(action="resume_goal", goal_id="g1"),
                        goals=store, orchestrator=orch)
    assert res.text == "" and res.acted is False
    assert orch.ran == 0                        # never touched the agent


def test_resume_closed_goal_is_silent(tmp_path):
    store = _real_store(tmp_path, goals=[("old", "g1")])
    store.complete(store.get("g1"))             # already done
    orch = FakeAdvanceOrch("x")
    res = disp.dispatch(_ini(action="resume_goal", goal_id="g1"),
                        goals=store, orchestrator=orch)
    assert res.text == "" and orch.ran == 0


def test_resume_without_agent_falls_back_to_reminder(tmp_path):
    store = _real_store(tmp_path, goals=[("check score", "g1")])
    res = disp.dispatch(_ini(action="resume_goal", text="ab dekhun?",
                             goal_id="g1"),
                        goals=store, orchestrator=None)
    assert res.text == "ab dekhun?"            # reminds instead of working
    assert res.acted is False


def test_dispatch_never_raises_on_bad_store():
    class Boom:
        def get(self, gid):
            raise RuntimeError("db down")
    res = disp.dispatch(_ini(action="resume_goal", text="fallback", goal_id="g1"),
                        goals=Boom(), orchestrator=FakeAdvanceOrch("x"))
    assert res.text == "fallback" and res.acted is False


# ── end-to-end: Initiative Engine → tick → dispatch → goal advanced ────

def test_engine_tick_to_dispatch_resumes_a_due_goal(tmp_path):
    """The real InitiativeEngine surfaces a due goal as a resume_goal ACT; the
    dispatcher then actually advances it — locking the full runtime chain."""
    from core.initiative_engine import InitiativeEngine
    from core.goal_system import GoalStore, Goal

    store = GoalStore(str(tmp_path / "g.json"), now_fn=lambda: 5000.0)
    g = store.add(Goal(text="check the score"))
    store.park(g, "need_time", resume_at=1000.0)      # due since t=1000

    class OKGate:                                     # allow autonomous act
        def _in_quiet(self, t): return False
        def authorize(self, action, level, *, now=None):
            return NS(outcome="allow", why="ok")

    eng = InitiativeEngine(goals_provider=lambda: store,
                           gate_provider=lambda: OKGate(),
                           now_fn=lambda: 5000.0)
    surfaced = eng.tick()
    assert surfaced and surfaced[0].action == "resume_goal"

    orch = FakeAdvanceOrch("score dekh liya")
    spoken = []
    for ini in surfaced:
        r = disp.dispatch(ini, goals=store, orchestrator=orch)
        if r.text:
            spoken.append(r.text)
    assert orch.ran == 1
    assert "score dekh liya" in spoken
    assert store.get(g.id).state == "done"            # the goal actually ran
