"""Chains through the real engine: real routing, mocked executor.

The executor is replaced so no app opens, no note is written and nothing
reaches the phone — outcomes are judged by the executor calls made.
"""

import pytest

from core.main_engine import JarvisMainEngine


@pytest.fixture
def engine(tmp_memory_path, tmp_feedback_db):
    e = JarvisMainEngine(
        stt="SKIP", tts="SKIP",
        memory_path=tmp_memory_path,
        feedback_db_path=tmp_feedback_db,
        verbose=False,
    )
    yield e
    e.feedback.close()


def _record(engine, replies=None):
    calls = []
    replies = replies or {}

    def _rec(intent, slots):
        calls.append((intent, dict(slots)))
        return replies.get(intent, f"ran {intent}")

    engine.executor.execute = _rec
    return calls


def test_result_flows_into_the_note(engine):
    calls = _record(engine, {"battery_status": "Battery 64%, plugged in."})
    engine.process_text("battery status batao aur note kar lo")
    assert calls[0][0] == "battery_status"
    assert calls[-1] == ("append_note", {"content": "Battery 64%, plugged in."})
    assert engine.last_chain is not None and engine.last_chain.stopped == "done"


def test_condition_true_runs_the_action(engine):
    calls = _record(engine, {"battery_status": "Battery 20%, battery par."})
    reply = engine.process_text("agar battery 30 se kam hai to system stats batao")
    assert [c[0] for c in calls] == ["battery_status", "system_stats"]
    assert "20 hai — 30 se kam hai" in reply


def test_condition_false_skips_the_action(engine):
    calls = _record(engine, {"battery_status": "Battery 90%, plugged in."})
    reply = engine.process_text("agar battery 30 se kam hai to system stats batao")
    assert [c[0] for c in calls] == ["battery_status"]
    assert "kuch nahi kiya" in reply


def test_pointer_uses_the_previous_answer(engine):
    calls = _record(engine, {"battery_status": "Battery 55%."})
    engine.process_text("battery status batao")
    engine.process_text("isko note kar lo")
    assert calls[-1] == ("append_note", {"content": "Battery 55%."})


def test_plain_multi_command_is_untouched(engine):
    calls = _record(engine)
    engine.process_text("chrome kholo aur notepad band karo")
    assert [c[0] for c in calls] == ["open_app", "close_app"]
    assert engine.last_chain is None
