"""Self-correction against the REAL engine (§6.24) — the check the unit tests
can't make.

`tests/test_repair_memory.py` proves the learning rules and the seam in
isolation, with a stub. What it cannot prove is the thing that actually
matters: that a learned alias **changes where a real utterance routes**, all
the way through `JarvisMainEngine.process_text` with the real classifier,
entity extractor and executor in the path.

Slow lane: this builds a full engine (torch + encoder + every skill).

The taught target is `learned_phrasings` itself — read-only, no required
slots, no side effects — so the test can assert on routing without any risk of
firing something that touches the machine.

Teaching goes through the *explicit* correction path ("galat"), because the
gibberish trigger shares no content word with the repair phrase and the
relatedness guard rightly declines it otherwise. That is the guard working, not
a workaround: a user whose rephrase is not a paraphrase says so out loud.
"""

from __future__ import annotations

import pytest

from core.main_engine import JarvisMainEngine
from core.repair_memory import RepairMemory, set_active

pytestmark = pytest.mark.slow

# Deliberately meaningless, and shaped to pass `learnable()`: 3 tokens, no
# digits. Nothing in a 587-intent corpus should claim it.
GIBBERISH = "zibber flooble wonk"


@pytest.fixture
def engine(tmp_memory_path, tmp_feedback_db, tmp_path, monkeypatch):
    monkeypatch.setenv("AERIS_REPAIR_MEMORY", "1")
    e = JarvisMainEngine(
        stt="SKIP", tts="SKIP",
        memory_path=tmp_memory_path,
        feedback_db_path=tmp_feedback_db,
        verbose=False,
    )
    # Point the table at tmp so a test run never writes to data/.
    e.repair = RepairMemory(path=str(tmp_path / "repair.json"))
    set_active(e.repair)
    yield e
    set_active(None)
    e.feedback.close()


def test_the_flag_actually_builds_a_repair_memory(engine):
    assert engine.repair is not None


def test_gibberish_does_not_route_to_the_target_on_its_own(engine):
    """The premise. If this ever starts failing, the test below proves
    nothing — the phrase would be routing on the corpus, not the alias."""
    engine.process_text(GIBBERISH)
    d = engine.last_dispatch or {}
    assert d.get("intent") != "learned_phrasings"


def test_a_learned_alias_reroutes_a_real_utterance(engine):
    """The whole point of the feature, end to end."""
    engine.repair.note_turn(GIBBERISH, ok=False)
    engine.repair.note_correction("galat")      # waives the relatedness test
    engine.repair.note_turn("show learned phrasings",
                            intent="learned_phrasings",
                            confidence=0.95, ok=True)
    assert engine.repair.lookup(GIBBERISH) is not None, "setup failed to teach"

    reply = engine.process_text(GIBBERISH)
    d = engine.last_dispatch or {}
    assert d.get("intent") == "learned_phrasings", (
        f"alias did not reroute; dispatch={d!r} reply={reply!r}")


def test_forgetting_restores_the_original_routing(engine):
    engine.repair.note_turn(GIBBERISH, ok=False)
    engine.repair.note_correction("galat")      # waives the relatedness test
    engine.repair.note_turn("show learned phrasings",
                            intent="learned_phrasings",
                            confidence=0.95, ok=True)
    engine.process_text(GIBBERISH)
    assert (engine.last_dispatch or {}).get("intent") == "learned_phrasings"

    engine.repair.forget(GIBBERISH)
    engine.process_text(GIBBERISH)
    assert (engine.last_dispatch or {}).get("intent") != "learned_phrasings"


def test_a_normal_command_still_routes_normally_with_the_flag_on(engine):
    """An empty alias table must not perturb ordinary routing — this is the
    regression that would matter most if tier 0 were wrong."""
    reply = engine.process_text("hello")
    assert isinstance(reply, str) and reply.strip()
    assert len(engine.repair) == 0


def test_an_alias_that_misses_deletes_itself_through_the_engine(engine):
    """Teach an alias to an intent that will NOT execute, then use it: the
    turn misses, and the engine's own `from_alias` path drops the rule."""
    engine.repair.note_turn(GIBBERISH, ok=False)
    engine.repair.note_correction("galat")      # waives the relatedness test
    engine.repair.note_turn("show learned phrasings",
                            intent="__no_such_intent__",
                            confidence=0.95, ok=True)
    assert engine.repair.lookup(GIBBERISH) is not None
    engine.process_text(GIBBERISH)
    assert engine.repair.lookup(GIBBERISH) is None
