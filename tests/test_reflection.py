"""Reflexion critic (core.reflection) — no-progress detector + outcome→lesson.
Duck-typed steps (SimpleNamespace), fake fabric — no orchestrator, model, or DB.
"""
from types import SimpleNamespace as NS

from core import reflection as rf


def _step(name, obs, *, blocked=False, kind="tool"):
    return NS(action=NS(kind=kind, name=name, args={}), observation=obs,
              blocked=blocked)


# ── no-progress detector ──────────────────────────────────────────────

def test_no_progress_false_for_short_or_healthy_runs():
    assert rf.no_progress([]) is False
    assert rf.no_progress([_step("a", "ok")]) is False        # too short
    good = [_step("a", "found 3"), _step("b", "opened"), _step("c", "sent")]
    assert rf.no_progress(good) is False


def test_no_progress_true_when_all_recent_steps_fail():
    bad = [_step("a", "ERROR: boom"), _step("b", "(no output)"),
           _step("c", "", blocked=True)]
    assert rf.no_progress(bad) is True                        # diff tools, all bad


def test_no_progress_true_on_identical_observation_loop():
    same = [_step("a", "same result"), _step("b", "same result"),
            _step("c", "same result")]
    assert rf.no_progress(same) is True


def test_no_progress_respects_window():
    steps = [_step("a", "ERROR"), _step("b", "ERROR"), _step("c", "good")]
    assert rf.no_progress(steps, window=3) is False           # last one recovered
    assert rf.no_progress(steps, window=2) is False           # b,c not both bad


# ── critique ──────────────────────────────────────────────────────────

def test_critique_reads_progress_and_stall():
    c = rf.critique("goal", [_step("a", "found the file")])
    assert c.progressed is True and c.stuck is False
    bad = [_step("a", "ERROR"), _step("b", "ERROR"), _step("c", "ERROR")]
    c2 = rf.critique("goal", bad)
    assert c2.stuck is True and c2.progressed is False


# ── outcome → lesson ──────────────────────────────────────────────────

def test_failure_from_repeated_tool_yields_caution_lesson():
    steps = [_step("search", "ERROR"), _step("search", "ERROR")]
    lesson = rf.reflect_on_outcome("find rahul's flat", steps, "stuck")
    assert lesson is not None and lesson.kind == "failure"
    assert "search" in lesson.text and lesson.salience >= 0.5


def test_failure_from_budget_suggests_subgoals():
    steps = [_step("a", "partial"), _step("b", "more")]
    lesson = rf.reflect_on_outcome("plan whole goa trip", steps, "budget")
    assert lesson is not None
    assert "sub-goal" in lesson.text or "chhote" in lesson.text


def test_multi_step_success_is_remembered_as_recipe():
    steps = [_step("search_flights", "3 found"), _step("open_url", "opened")]
    lesson = rf.reflect_on_outcome("book a flight", steps, "final")
    assert lesson is not None and lesson.kind == "success"
    assert "search_flights" in lesson.text and "open_url" in lesson.text


def test_trivial_success_and_blocked_store_nothing():
    # one-shot success isn't worth a memory
    assert rf.reflect_on_outcome("torch on", [_step("torch_on", "on")],
                                 "final") is None
    # a run parked for the user is not a failure to learn from
    assert rf.reflect_on_outcome("msg rahul",
                                 [_step("send", "AWAITING", blocked=True)],
                                 "blocked") is None
    assert rf.reflect_on_outcome("x", [], "budget") is None   # no steps


# ── record + learn (fake fabric) ──────────────────────────────────────

def test_learn_stores_lesson_to_fabric():
    stored = []

    class FakeFabric:
        def remember(self, text, *, kind="auto"):
            stored.append((text, kind))

    steps = [_step("search", "ERROR"), _step("search", "ERROR")]
    lesson = rf.learn("find x", steps, "stuck",
                      fabric_provider=lambda: FakeFabric())
    assert lesson is not None
    assert len(stored) == 1
    assert stored[0][0].startswith("Lesson:") and stored[0][1] == "note"


def test_llm_refines_wording_but_not_verdict():
    steps = [_step("a", "partial"), _step("b", "more")]
    lesson = rf.reflect_on_outcome(
        "big goal", steps, "budget",
        llm=lambda p: "Ise chhote hisso mein todo — behtar chalega.")
    assert lesson.kind == "failure"
    assert lesson.text == "Ise chhote hisso mein todo — behtar chalega."


# ── the closed loop: a lesson written on failure is recalled next time ──

class _RealishUM:
    """A UserMemory stand-in whose add_note actually populates the store the
    fabric's recall path reads (`_data["notes"]`)."""
    def __init__(self):
        self._data = {"facts": {}, "notes": [], "preferences": {}}

    def add_note(self, text):
        self._data["notes"].append({"text": text})


def test_reflexion_closed_loop_write_then_recall():
    """End-to-end with the REAL MemoryFabric: a failed run stores a lesson, and
    planning a *similar* goal later surfaces it via recall_context — proving the
    self-improvement loop actually closes."""
    from core.memory_fabric import MemoryFabric
    um = _RealishUM()
    fab = MemoryFabric(semantic_provider=lambda: None, kg_provider=lambda: None,
                       user_memory_provider=lambda: um, now_fn=lambda: 1_000_000.0)

    goal = "book the goa flight"
    steps = [_step("search_flights", "ERROR"), _step("search_flights", "ERROR")]
    lesson = rf.learn(goal, steps, "stuck", fabric_provider=lambda: fab)
    assert lesson is not None
    assert um._data["notes"]                        # stored

    ctx = fab.recall_context("book goa flight again", k=4)
    assert "Lesson:" in ctx                          # the agent will read this
    assert "goa flight" in ctx.lower()


class TestTheStuckNoteNamesTheGoal:
    """§6.34 follow-up. `critique` accepted `goal` and ignored it, so the
    reflection nudge the model reads said only "aage nahi badh raha" — leaving
    a 1.5B model to re-derive what it had been trying to do, when redirecting
    it toward exactly that is the nudge's whole purpose.
    """

    @staticmethod
    def _stuck_steps():
        from types import SimpleNamespace as NS
        return [NS(action=NS(name=f"tool{i}"), observation="ERROR: failed",
                   blocked=False) for i in range(4)]

    def test_the_goal_appears_in_the_stuck_note(self):
        import core.reflection as rf
        c = rf.critique("book the delhi flight", self._stuck_steps())
        assert c.stuck is True
        assert "book the delhi flight" in c.note

    def test_a_long_goal_is_truncated_not_dumped(self):
        import core.reflection as rf
        goal = "please go and " + ("do the thing " * 20)
        note = rf.critique(goal, self._stuck_steps()).note
        assert len(note) < 140 and "…" in note

    def test_an_empty_goal_still_reads_sensibly(self):
        import core.reflection as rf
        note = rf.critique("", self._stuck_steps()).note
        assert "approach badalni chahiye" in note and "''" not in note

    def test_the_healthy_notes_are_unchanged(self):
        """Only the stuck note names the goal — a run that is going fine does
        not need reminding, and the note is read every step."""
        from types import SimpleNamespace as NS
        import core.reflection as rf
        ok = [NS(action=NS(name="a"), observation="found the file",
                 blocked=False)]
        assert rf.critique("some goal", ok).note == "theek chal raha hai"
        assert rf.critique("some goal", []).note == "koi step nahi — plan hi nahi bana"

    def test_it_reaches_the_orchestrator_nudge(self):
        """The note is only useful because `_reflection_step` folds it into
        the synthetic step the model actually reads."""
        from core.agent_orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(llm_step=lambda g, s: "", run_tool=lambda n, a: "")
        step = orch._reflection_step("book the delhi flight", self._stuck_steps())
        assert "book the delhi flight" in step.observation
        assert step.action.kind == "reflect"
