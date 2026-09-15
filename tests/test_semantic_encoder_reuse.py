"""Semantic memory must reuse the brain's encoder, not load a second one.

`SemanticMemory._ensure_encoder` used to have exactly one reuse path: walk
`QApplication.topLevelWidgets()` looking for a GUI whose `_brain._engine` held
an encoder. That succeeds in one configuration — the GUI process with an
in-process brain. In the split-brain CHILD, in `main.py --text`, and under
pytest it found nothing and fell through to loading its own
SentenceTransformer on the embed thread: a second ~450 MB model in the very
process the split architecture exists to keep light, triggered by simply
storing a conversation turn (so lite boot could not defer it either).
"""

from __future__ import annotations

import pytest

from core.semantic_memory import SemanticMemory


@pytest.fixture
def store():
    return SemanticMemory()


def test_provider_encoder_is_used(store):
    sentinel = object()
    store.set_encoder_provider(lambda: sentinel)
    assert store._ensure_encoder() is True
    assert store._encoder is sentinel


def test_provider_is_reresolved_every_call(store):
    """Never cache: a cached reference would keep the brain's encoder alive
    through an idle-unload, so the RAM would never actually come back."""
    handles = [object(), object(), object()]
    calls = []

    def provider():
        calls.append(1)
        return handles[len(calls) - 1]

    store.set_encoder_provider(provider)
    for expected in handles:
        assert store._ensure_encoder() is True
        assert store._encoder is expected
    assert len(calls) == 3, "provider must be consulted on every call"


def test_cold_brain_means_wait_not_a_second_model(store, monkeypatch):
    """When the brain has unloaded its weights the provider returns None. The
    store must report 'not ready' and wait — NOT load its own encoder."""
    loaded = []

    def explode(*a, **k):
        loaded.append(1)
        raise AssertionError("loaded a second encoder instead of waiting")

    monkeypatch.setattr(
        "sentence_transformers.SentenceTransformer", explode, raising=False)

    store.set_encoder_provider(lambda: None)
    assert store._ensure_encoder() is False
    assert store._encoder is None
    assert loaded == []


def test_provider_recovers_when_the_brain_warms_again(store):
    """Cold -> warm must start working again without a restart."""
    state = {"enc": None}
    store.set_encoder_provider(lambda: state["enc"])

    assert store._ensure_encoder() is False
    state["enc"] = object()
    assert store._ensure_encoder() is True
    assert store._encoder is state["enc"]


def test_failing_provider_is_not_fatal(store):
    def boom():
        raise RuntimeError("brain is mid-restart")

    store.set_encoder_provider(boom)
    assert store._ensure_encoder() is False      # must not raise
    assert store._encoder is None


def test_engine_registers_a_provider(monkeypatch, tmp_path):
    """The wiring itself — if setup_iter stops registering it, every headless
    AERIS quietly goes back to running two encoders."""
    monkeypatch.setenv("AERIS_LITE_ML", "1")
    monkeypatch.setenv("AERIS_DISABLE_BRIDGE", "1")

    from core import main_engine as me, semantic_memory

    registered = {}
    monkeypatch.setattr(
        SemanticMemory, "set_encoder_provider",
        lambda self, p: registered.setdefault("provider", p))

    eng = me.JarvisMainEngine(
        stt="SKIP", tts="SKIP", verbose=False, lazy=True,
        enable_scheduler=False, enable_agent=False,
        memory_path=str(tmp_path / "m.json"),
        feedback_db_path=str(tmp_path / "f.sqlite"),
    )
    for _ in eng.setup_iter():
        pass

    assert "provider" in registered, "engine did not register an encoder provider"
    # Lite boot: brain is cold, so the provider yields None rather than
    # prompting a second model load.
    assert registered["provider"]() is None
    assert eng.brain.ml_loaded is False
