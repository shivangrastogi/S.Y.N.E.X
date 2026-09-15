"""Idle-unload ticker — give the model weights back when nobody's talking.

`JarvisBrain.try_unload_idle()` predates this file, but nothing called it on a
timer: its only caller was the GUI's ResourceMonitor *pressure* hook, which
fires only once the whole machine is short on memory — and which reaches for
`self._brain._engine`, an attribute a split-brain RemoteBrain doesn't have. So
in practice the brain held its weights from the first hard utterance until the
process exited. These tests pin the ticker that closes that.
"""

from __future__ import annotations

import threading
import time

import pytest

from core.brain import JarvisBrain, _idle_unload_seconds, _IDLE_UNLOAD_S


@pytest.fixture
def brain(monkeypatch):
    """A lazy brain with the heavy loads stubbed — no model ever touched."""
    b = JarvisBrain(lazy=True)
    monkeypatch.setattr(b.classifier, "load_encoder", lambda: None)
    monkeypatch.setattr(b.classifier, "build_or_load_index", lambda: None)
    monkeypatch.setattr(b.neural, "is_trained", lambda: False)
    yield b
    b.stop_idle_unloader()


# --------------------------------------------------------------------- #
#  Window configuration                                                  #
# --------------------------------------------------------------------- #

def test_default_idle_window(monkeypatch):
    monkeypatch.delenv("AERIS_IDLE_UNLOAD_S", raising=False)
    assert _idle_unload_seconds() == float(_IDLE_UNLOAD_S)


def test_env_overrides_idle_window(monkeypatch):
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "12")
    assert _idle_unload_seconds() == 12.0


def test_zero_disables(monkeypatch):
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "0")
    assert _idle_unload_seconds() == 0.0


def test_garbage_env_falls_back_to_default(monkeypatch):
    """A bad value must not break boot — the brain is the app's critical path."""
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "five minutes")
    assert _idle_unload_seconds() == float(_IDLE_UNLOAD_S)


def test_negative_env_clamps_to_disabled(monkeypatch):
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "-30")
    assert _idle_unload_seconds() == 0.0


# --------------------------------------------------------------------- #
#  Ticker lifecycle                                                      #
# --------------------------------------------------------------------- #

def test_start_is_idempotent(brain):
    assert brain.start_idle_unloader(interval_s=30) is True
    assert brain.start_idle_unloader(interval_s=30) is False, "no second thread"


def test_disabled_window_starts_no_thread(brain):
    brain._idle_unload_s = 0
    assert brain.start_idle_unloader(interval_s=0.05) is False
    assert brain._unloader_thread is None


def test_stop_is_safe_when_never_started(brain):
    brain.stop_idle_unloader()          # must not raise
    assert brain._unloader_thread is None


def test_thread_is_daemon(brain):
    """A non-daemon ticker would keep the interpreter alive at shutdown."""
    brain.start_idle_unloader(interval_s=30)
    assert brain._unloader_thread.daemon is True


def test_stop_ends_the_thread(brain):
    brain.start_idle_unloader(interval_s=0.05)
    t = brain._unloader_thread
    brain.stop_idle_unloader()
    t.join(timeout=5)
    assert not t.is_alive()


# --------------------------------------------------------------------- #
#  The behaviour that matters                                            #
# --------------------------------------------------------------------- #

def test_ticker_unloads_after_the_idle_window(brain):
    """Load weights, go quiet, and the ticker gives the RAM back on its own."""
    brain._ensure_loaded()
    assert brain.ml_loaded is True

    brain._idle_unload_s = 0.01          # "idle" almost immediately
    unloaded = threading.Event()
    real = brain.try_unload_idle

    def watched():
        did = real()
        if did:
            unloaded.set()
        return did

    brain.try_unload_idle = watched
    brain.start_idle_unloader(interval_s=0.05)

    assert unloaded.wait(timeout=10), "ticker never reclaimed the weights"
    assert brain.ml_loaded is False


def test_ticker_leaves_a_busy_brain_alone(brain):
    """Weights must NOT be dropped while the user is still talking — that
    would make every other utterance pay a reload."""
    brain._ensure_loaded()
    brain._idle_unload_s = 30            # long window; brain was just used
    brain.start_idle_unloader(interval_s=0.05)

    time.sleep(0.5)                      # several ticks
    assert brain.ml_loaded is True, "unloaded a brain that was just used"


def test_tick_failure_does_not_kill_the_thread(brain):
    """One bad tick must not silently end idle-unloading for the session."""
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("transient")
        return False

    brain.try_unload_idle = flaky
    brain.start_idle_unloader(interval_s=0.05)

    deadline = time.time() + 10
    while len(calls) < 3 and time.time() < deadline:
        time.sleep(0.05)
    assert len(calls) >= 3, "ticker died on the first exception"


def test_reload_after_unload_restores_service(brain):
    """The whole trade only works if a cold brain comes back transparently."""
    brain._ensure_loaded()
    brain._idle_unload_s = 0
    assert brain.try_unload_idle() is True
    assert brain.ml_loaded is False

    brain._ensure_loaded()
    assert brain.ml_loaded is True


# --------------------------------------------------------------------- #
#  Check interval tracks the window                                      #
# --------------------------------------------------------------------- #
# A flat 60s check silently rounds a short window up to the interval: ask
# for a 30s window and you wait 60-90s for the RAM back. The default now
# derives from the window instead.

@pytest.mark.parametrize("window,expected", [
    (5 * 60, 60.0),     # 5-min default -> capped at the 60s ceiling
    (600, 60.0),        # longer window -> still 60s, no lazier than that
    (30, 15.0),         # short window -> checks twice as often
    (12, 6.0),
    (4, 5.0),           # very short -> floored at 5s, not a busy-loop
])
def test_default_check_interval_tracks_window(monkeypatch, window, expected):
    b = JarvisBrain(lazy=True)
    b._idle_unload_s = window
    captured = {}
    real_thread = threading.Thread

    def spy(*args, **kwargs):
        captured["name"] = kwargs.get("name")
        return real_thread(*args, **kwargs)

    monkeypatch.setattr(threading, "Thread", spy)
    monkeypatch.setattr(b, "try_unload_idle", lambda: False)

    computed = max(5.0, min(60.0, window / 2.0))
    assert computed == expected

    assert b.start_idle_unloader() is True
    assert captured["name"] == "BrainIdleUnloader"
    b.stop_idle_unloader()


def test_explicit_interval_still_wins(brain):
    """Callers that know better (tests, tuning) keep full control."""
    assert brain.start_idle_unloader(interval_s=0.05) is True
    assert brain._unloader_thread is not None


# --------------------------------------------------------------------- #
#  Regression: unload must not race a predict                            #
# --------------------------------------------------------------------- #

def test_unload_cannot_interleave_with_a_heavy_predict(monkeypatch):
    """The idle unloader must never null the encoder out from under an
    in-flight predict.

    `_ensure_loaded()` takes ENCODER_LOCK and RELEASES it; if the k-NN
    predict then runs unlocked, the ticker can drop `classifier.encoder`
    in between and the predict dies with
    "'NoneType' object has no attribute 'encode'". That is not theoretical —
    it happened on the first real run of the ticker against the live engine.
    Here the unload is triggered from another thread at the worst possible
    moment: from inside the encoder call itself.
    """
    from core.intent_classifier import Prediction

    b = JarvisBrain(lazy=True)
    b.prepare_fast_tiers()
    monkeypatch.setattr(b.classifier, "load_encoder", lambda: None)
    monkeypatch.setattr(b.classifier, "build_or_load_index", lambda: None)
    monkeypatch.setattr(b.neural, "is_trained", lambda: False)
    b._ensure_loaded()
    b.classifier.encoder = object()          # stand-in for a live encoder

    errors = []

    def classifier_predict(text, threshold=0.5):
        # Mid-predict, let an unloader thread try to pull the rug out.
        b._idle_unload_s = 0
        t = threading.Thread(target=b.try_unload_idle)
        t.start()
        t.join(timeout=5)
        if b.classifier.encoder is None:
            errors.append("encoder vanished mid-predict")
        return Prediction(intent="x", confidence=0.9, raw_text=text,
                          normalized_text=text)

    b.classifier.predict = classifier_predict
    b._neural_active = False

    pred = b.predict("something no cheap tier can answer at all bilkul")

    assert pred.intent == "x"
    assert errors == [], errors[0] if errors else ""


# --------------------------------------------------------------------- #
#  Sweeping the resources the brain does NOT own                         #
# --------------------------------------------------------------------- #
# The brain drops only the encoder + neural head. spaCy (~220 MB, drags
# torch in) and the local Qwen LLM (1 GB gguf) are loaded on demand and were
# never released — LocalLLM.maybe_unload_idle() existed, documented, with
# zero callers. That is why RSS sat at ~495 MB after one hard utterance even
# with the brain's own weights dropped.

def test_idle_hooks_run_on_every_tick(brain):
    calls = []
    brain.add_idle_unload_hook(lambda: calls.append("a") or False)
    brain.add_idle_unload_hook(lambda: calls.append("b") or False)

    brain._sweep_idle_hooks()
    assert calls == ["a", "b"]
    brain._sweep_idle_hooks()
    assert calls == ["a", "b", "a", "b"]


def test_a_failing_hook_does_not_stop_the_others(brain):
    """One stuck resource must not end idle-unloading for the session."""
    def boom():
        raise RuntimeError("spaCy wedged")

    ok = []
    brain.add_idle_unload_hook(boom)
    brain.add_idle_unload_hook(lambda: ok.append(1) or True)

    brain._sweep_idle_hooks()           # must not raise
    assert ok == [1]


def test_ticker_sweeps_hooks_even_when_weights_are_already_gone(brain):
    """The brain's own weights may already be unloaded (or never loaded, in
    lite mode) — the other resources still need sweeping."""
    swept = threading.Event()
    brain.add_idle_unload_hook(lambda: swept.set() or False)
    assert brain.ml_loaded is False      # nothing of the brain's is loaded
    brain.start_idle_unloader(interval_s=0.05)
    assert swept.wait(timeout=10), "hooks skipped because the brain was cold"


def test_engine_registers_spacy_and_llm_hooks(monkeypatch, tmp_path):
    """The wiring — if setup_iter stops registering these, the 495 MB comes
    back and nothing fails loudly."""
    monkeypatch.setenv("AERIS_LITE_ML", "1")
    monkeypatch.setenv("AERIS_DISABLE_BRIDGE", "1")

    from core import main_engine as me
    from core.brain import JarvisBrain as _RealBrain

    registered = []
    monkeypatch.setattr(_RealBrain, "add_idle_unload_hook",
                        lambda self, fn: registered.append(fn))
    monkeypatch.setattr(_RealBrain, "start_idle_unloader",
                        lambda self, interval_s=None: False)

    eng = me.JarvisMainEngine(
        stt="SKIP", tts="SKIP", verbose=False, lazy=True,
        enable_scheduler=False, enable_agent=False,
        memory_path=str(tmp_path / "m.json"),
        feedback_db_path=str(tmp_path / "f.sqlite"),
    )
    for _ in eng.setup_iter():
        pass

    names = {getattr(f, "__name__", "") for f in registered}
    assert "_unload_idle_spacy" in names, names
    assert "_unload_idle_llm" in names, names


def test_spacy_unload_allows_a_later_reload(tmp_path):
    """`_spacy_tried` blocks retries of a FAILED load. A deliberate unload is
    not a failure — leaving that flag set would silently disable NER for the
    rest of the session."""
    import os
    from core.entity_extractor import EntityExtractor
    from tests.conftest import PROJECT_ROOT

    e = EntityExtractor(
        entities_path=os.path.join(PROJECT_ROOT, "data", "entities.json"),
        intents_path=os.path.join(PROJECT_ROOT, "data", "intents.json"),
        lazy=True,
    )
    e.defer_spacy = True
    e.nlp = object()                    # pretend it is loaded
    e._spacy_tried = True

    assert e.unload_spacy() is True
    assert e.nlp is None
    assert e._spacy_tried is False, "unload left NER permanently disabled"
    assert e.unload_spacy() is False, "second unload should be a no-op"


def test_llm_hook_never_constructs_an_llm(monkeypatch):
    """peek(), not get() — asking 'is there anything to clean up?' must not
    materialise a LocalLLM on a machine that never used one."""
    from core import local_llm, main_engine

    monkeypatch.setattr(local_llm, "_INSTANCE", None)
    built = []
    monkeypatch.setattr(local_llm, "LocalLLM",
                        lambda *a, **k: built.append(1) or object())

    assert main_engine._unload_idle_llm() is False
    assert built == [], "constructed an LLM just to unload it"
    assert local_llm.peek() is None


def test_llm_hook_unloads_an_existing_instance(monkeypatch):
    from core import local_llm, main_engine

    class _Fake:
        def __init__(self):
            self.calls = 0

        def maybe_unload_idle(self):
            self.calls += 1
            return True

    fake = _Fake()
    monkeypatch.setattr(local_llm, "_INSTANCE", fake)
    assert main_engine._unload_idle_llm() is True
    assert fake.calls == 1


def test_llm_hook_survives_a_raising_llm(monkeypatch):
    from core import local_llm, main_engine

    class _Broken:
        def maybe_unload_idle(self):
            raise RuntimeError("llama handle gone")

    monkeypatch.setattr(local_llm, "_INSTANCE", _Broken())
    assert main_engine._unload_idle_llm() is False      # must not raise


# --------------------------------------------------------------------- #
#  The LLM's idle window must follow the process-wide setting            #
# --------------------------------------------------------------------- #
# The LLM is the single biggest chunk in the process (~1 GB gguf), and its
# window used to be a bare module constant. So AERIS_IDLE_UNLOAD_S governed
# the encoder and spaCy but silently NOT the LLM: setting it to a minute gave
# back ~500 MB in a minute and the other gigabyte five minutes later, with
# nothing explaining the difference. Measured on a live run — 90 s idle, and
# llm=True the whole way.

def test_llm_window_defaults_to_five_minutes(monkeypatch):
    from core import local_llm
    monkeypatch.delenv("AERIS_IDLE_UNLOAD_S", raising=False)
    monkeypatch.delenv("AERIS_LLM_IDLE_UNLOAD_S", raising=False)
    assert local_llm.idle_unload_seconds() == local_llm._IDLE_UNLOAD_S


def test_llm_window_follows_the_process_wide_setting(monkeypatch):
    from core import local_llm
    monkeypatch.delenv("AERIS_LLM_IDLE_UNLOAD_S", raising=False)
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "30")
    assert local_llm.idle_unload_seconds() == 30.0


def test_llm_specific_override_wins(monkeypatch):
    """The LLM is the most expensive thing here to reload, so it can be held
    longer than everything else on purpose."""
    from core import local_llm
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "30")
    monkeypatch.setenv("AERIS_LLM_IDLE_UNLOAD_S", "600")
    assert local_llm.idle_unload_seconds() == 600.0


def test_llm_window_ignores_garbage(monkeypatch):
    from core import local_llm
    monkeypatch.delenv("AERIS_LLM_IDLE_UNLOAD_S", raising=False)
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "soon")
    assert local_llm.idle_unload_seconds() == local_llm._IDLE_UNLOAD_S


def test_llm_window_is_read_at_call_time(monkeypatch):
    """A module constant would freeze the value at import; the env must be
    able to change between calls (and tests must be able to set it)."""
    from core import local_llm
    monkeypatch.delenv("AERIS_LLM_IDLE_UNLOAD_S", raising=False)
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "10")
    assert local_llm.idle_unload_seconds() == 10.0
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "20")
    assert local_llm.idle_unload_seconds() == 20.0


def test_llm_zero_means_never_unload(monkeypatch):
    """0 disables unloading, matching the brain — NOT 'unload immediately',
    which is what a naive `elapsed < 0` comparison would do."""
    import time as _t
    from core import local_llm

    monkeypatch.delenv("AERIS_LLM_IDLE_UNLOAD_S", raising=False)
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "0")

    llm = local_llm.LocalLLM()
    llm._llm = object()
    llm._last_used = _t.monotonic() - 10_000      # idle for hours
    assert llm.maybe_unload_idle() is False
    assert llm._llm is not None


def test_llm_unloads_once_past_the_window(monkeypatch):
    import time as _t
    from core import local_llm

    monkeypatch.delenv("AERIS_LLM_IDLE_UNLOAD_S", raising=False)
    monkeypatch.setenv("AERIS_IDLE_UNLOAD_S", "5")

    llm = local_llm.LocalLLM()
    llm._llm = object()
    llm._last_used = _t.monotonic() - 1           # still warm
    assert llm.maybe_unload_idle() is False

    llm._last_used = _t.monotonic() - 60          # now idle
    assert llm.maybe_unload_idle() is True
    assert llm._llm is None
