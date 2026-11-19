"""Locks the shape of JarvisMainEngine's turn pipeline (_TURN_STEPS).

process_text used to be one 300-line if-chain; it is now an ordered tuple of
small step methods. The order is behaviour (pending state resolves before new
input is interpreted; memory capture runs before routing), so it is pinned
here, and every name must resolve to a method. Pure: no engine construction.
"""
from __future__ import annotations

from core.main_engine import JarvisMainEngine as _J


def test_every_step_is_a_method():
    for name in _J._TURN_STEPS:
        assert callable(getattr(_J, name, None)), name


def test_steps_are_unique():
    assert len(set(_J._TURN_STEPS)) == len(_J._TURN_STEPS)


def test_pending_state_resolves_before_new_input():
    steps = list(_J._TURN_STEPS)
    pending = ["_step_anticipation_reply", "_step_slot_fill",
               "_step_disambiguation", "_step_destructive_confirm",
               "_step_proactive_offer"]
    assert steps[:len(pending)] == pending


def test_memory_capture_runs_before_goals_and_cancel():
    steps = list(_J._TURN_STEPS)
    assert steps.index("_step_memory") < steps.index("_step_goal_capture")
    assert steps[-1] == "_step_idle_cancel"


class _History:
    def __init__(self):
        self.turns = []

    def add_user(self, text, label):
        self.turns.append(("user", text, label))

    def add_assistant(self, text):
        self.turns.append(("assistant", text))


class _Memory:
    """Recall answers only questions; store answers only statements."""

    def detect_and_recall(self, text):
        return "Shivang" if text.endswith("?") else None

    def detect_and_store(self, text):
        return "Yaad rakh liya." if "naam" in text else None

    def detect_and_forget(self, text):
        raise AssertionError("forget must not run once store answered")


class _Stub:
    _PASS = _J._PASS
    _reply = _J._reply
    _step_memory = _J._step_memory

    def __init__(self):
        self.history = _History()
        self.memory = _Memory()


def test_memory_step_recalls_first_then_stores_and_records_history():
    s = _Stub()
    assert s._step_memory("mera naam kya hai?") == "Shivang"
    assert s._step_memory("mera naam Shivang hai") == "Yaad rakh liya."
    assert s.history.turns[-2:] == [("user", "mera naam Shivang hai", "neutral"),
                                    ("assistant", "Yaad rakh liya.")]


def test_unhandled_step_passes():
    s = _Stub()
    s.memory.detect_and_forget = lambda text: None
    assert s._step_memory("chrome kholo") is _J._PASS
