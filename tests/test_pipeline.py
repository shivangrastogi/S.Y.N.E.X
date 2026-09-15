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


# ─── Orchestration smoke (I7: brain → response → TTS wiring) ────────────

def test_orchestration_smoke_text_to_speak(engine):
    """A simple utterance produces a non-empty reply that _speak forwards
    verbatim to the TTS backend — the minimal end-to-end orchestration check
    README §13.3 asks for ("send 'hi' → TTS got a non-empty string")."""
    reply = engine.process_text("hello")
    assert isinstance(reply, str) and reply.strip()

    spoken = []

    class _FakeTTS:
        def speak(self, text):
            spoken.append(text)

    engine._tts = _FakeTTS()
    engine._speak(reply)
    assert spoken == [reply]
    assert spoken[0].strip()                 # non-empty string reached TTS


def test_orchestration_speak_ignores_empty(engine):
    spoken = []

    class _FakeTTS:
        def speak(self, text):
            spoken.append(text)

    engine._tts = _FakeTTS()
    engine._speak("")                         # empty → no backend call
    assert spoken == []


# ─── Dispatch side-channel (I2: per-reply "which skill fired" chip) ──────

def test_last_dispatch_side_channel(engine):
    """A skill-routed turn populates engine.last_dispatch with chip metadata."""
    from core.activity_digest import format_chip
    r = engine.process_text("what time is it")
    assert r  # some response came back
    meta = engine.last_dispatch
    assert meta is not None
    assert meta["intent"]                       # an intent was recorded
    assert "latency_ms" in meta and meta["latency_ms"] >= 0
    chip = format_chip(meta)
    assert meta["intent"] in chip and "ms" in chip


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
    """Saying 'galat' after an execution flips reward to -1.

    Uses "mausam kaisa hai" — still owned by the legacy get_weather stub
    (offline-safe). "weather batao" moved to the weather_local skill in
    the 2026-07-04 pattern unification and would hit the network.
    """
    engine.process_text("mausam kaisa hai")
    r = engine.process_text("galat")
    assert r is not None and ("sorry" in r.lower() or "phir se" in r.lower())
    # The bandit threshold for get_weather should now be > default (drifted up)
    threshold = engine.feedback.get_threshold("get_weather")
    from core.feedback import DEFAULT_THRESHOLD
    assert threshold > DEFAULT_THRESHOLD


def test_implicit_acceptance(engine):
    """Any non-correction next turn implicitly accepts the prior."""
    engine.process_text("mausam kaisa hai")
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


# ─── Proactive OFFER "haan" → activate mode (Step 0d) ───────────────────

def test_pending_offer_haan_activates_mode(engine):
    """A parked mode-suggest offer + 'haan' runs activate_mode via executor."""
    calls = []

    def _rec(intent, slots):
        calls.append((intent, dict(slots)))
        return f"ran {intent}"

    engine.executor.execute = _rec
    engine._pending_offer = ("activate_mode", {"raw_text": "sleep"})
    out = engine.process_text("haan")
    assert out == "ran activate_mode"
    assert calls == [("activate_mode", {"raw_text": "sleep"})]
    assert engine._pending_offer is None       # one-turn window closed


def test_pending_offer_other_input_drops_silently(engine):
    """Any non-confirmation drops the offer (no activation) and processes
    the new input normally — no scary 'cancelled' message."""
    calls = []

    def _rec(intent, slots):
        calls.append((intent, dict(slots)))
        return f"ran {intent}"

    engine.executor.execute = _rec
    engine._pending_offer = ("activate_mode", {"raw_text": "sleep"})
    reply = engine.process_text("hello")
    assert isinstance(reply, str) and reply.strip()
    assert engine._pending_offer is None
    assert all(intent != "activate_mode" for intent, _ in calls)
