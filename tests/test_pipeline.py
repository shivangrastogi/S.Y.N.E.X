"""End-to-end pipeline tests via JarvisMainEngine.process_text().

Each test gets isolated tmp memory + feedback paths so there's no cross-test
or real-data pollution. The engine itself loads the brain only once per
session because it depends on `shared_brain` machinery (Python re-uses the
encoder via SentenceTransformer's internal cache too).
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


# ─── Memory store + recall ──────────────────────────────────────────────

def test_memory_store_and_recall_english(engine):
    r = engine.process_text("hello my name is shivang")
    assert r is not None and "Shivang" in r
    r = engine.process_text("what's my name")
    assert r is not None and "Shivang" in r


def test_memory_recall_hindi_alias(engine):
    engine.process_text("hello my name is shivang")
    engine.process_text("i live in delhi")
    r = engine.process_text("mera ghar kya hai")
    assert r is not None and "Delhi" in r


def test_memory_recall_runs_before_store(engine):
    """Regression: 'mera naam kya hai' must NOT be caught by the store pattern."""
    engine.process_text("hello my name is shivang")
    r = engine.process_text("mera naam kya hai")
    assert r is not None
    # The recall response uses "Aapka naam X hai", not "Got it, ..."
    assert "Got it" not in r
    assert "Shivang" in r


def test_what_do_you_know_about_me(engine):
    engine.process_text("hello my name is shivang")
    engine.process_text("i live in delhi")
    r = engine.process_text("what do you know about me")
    assert r is not None
    assert "Shivang" in r and "Delhi" in r


# ─── Slot-fill flow ──────────────────────────────────────────────────────

def test_slot_fill_two_slots(engine):
    r = engine.process_text("meeting schedule karo")
    assert r is not None and ("Kiske" in r or "kiske" in r)
    r = engine.process_text("with raj")
    assert r is not None and ("Kis time" in r or "kis time" in r)
    r = engine.process_text("5 pm")
    assert r is not None
    # Executor returns a string; at minimum it should mention the person
    assert "raj" in r.lower()


def test_slot_fill_cancel(engine):
    engine.process_text("meeting schedule karo")
    r = engine.process_text("cancel")
    assert r is not None
    assert "cancel" in r.lower()


# ─── Bandit feedback ─────────────────────────────────────────────────────

def test_correction_recorded(engine):
    """Saying 'galat' after an execution flips reward to -1."""
    engine.process_text("weather batao")
    r = engine.process_text("galat")
    assert r is not None and ("sorry" in r.lower() or "phir se" in r.lower())
    # The bandit threshold for get_weather should now be > default (drifted up)
    threshold = engine.feedback.get_threshold("get_weather")
    from core.feedback import DEFAULT_THRESHOLD
    assert threshold > DEFAULT_THRESHOLD


def test_implicit_acceptance(engine):
    """Any non-correction next turn implicitly accepts the prior."""
    engine.process_text("weather batao")
    engine.process_text("hi")  # any benign next turn
    # The accepted feedback should have been recorded — utterance row has user_feedback set
    rows = engine.feedback._conn.execute(
        "SELECT user_feedback FROM utterances WHERE predicted_intent = 'get_weather'"
    ).fetchall()
    assert len(rows) >= 1
    assert any(r["user_feedback"] == "accepted" for r in rows)


# ─── Cancel with no state ────────────────────────────────────────────────

def test_cancel_with_no_state(engine):
    r = engine.process_text("cancel")
    assert r is not None and "kuch chal nahi" in r.lower()


# ─── Empty / whitespace ──────────────────────────────────────────────────

def test_empty_input_returns_none(engine):
    assert engine.process_text("") is None
    assert engine.process_text("   ") is None
