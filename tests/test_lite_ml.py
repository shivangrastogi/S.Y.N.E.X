"""Lite-ML boot + tiered router — the "AERIS is heavy to run" fixes.

Three properties are asserted here, each of which used to be false:

1. **Import weight** — importing the brain stack must not drag in torch or
   sentence-transformers. That import alone cost ~15 s and hundreds of MB.
2. **Tiered router** — an utterance answered by a cheap tier (exact pattern,
   plain arithmetic, routing anchor, LRU cache) must never trigger the model
   load. `predict()` used to call `_ensure_loaded()` unconditionally at the
   top, so every turn paid for the encoder.
3. **Convergence** — the first utterance that *does* need embeddings loads
   the models once and fires the ml-loaded hooks, so the extras lite boot
   skipped (spaCy NER, chat gate) come up too.

These are pure-logic tests: the heavy tier is stubbed, nothing loads a model.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from core.brain import JarvisBrain
from core.lite_ml import lite_ml_enabled


# --------------------------------------------------------------------- #
#  1. Import weight                                                      #
# --------------------------------------------------------------------- #

def test_importing_brain_does_not_import_torch():
    """`import core.brain` in a CLEAN interpreter pulls in no ML runtime.

    Run in a subprocess because torch may already be in this process's
    sys.modules thanks to another (slow-lane) test.
    """
    code = (
        "import sys;"
        "import core.brain, core.intent_classifier, core.intent_model;"
        "print('torch' in sys.modules, 'sentence_transformers' in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=180,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip() == "False False", out.stdout


def test_constructing_brain_does_not_import_torch():
    """Even building the object (which constructs NeuralIntentClassifier)
    stays ML-free — `_device` used to call torch.cuda.is_available() in
    __init__."""
    code = (
        "import sys;"
        "from core.brain import JarvisBrain;"
        "b = JarvisBrain(lazy=True);"
        "b.prepare_fast_tiers();"
        "print('torch' in sys.modules, b.ml_loaded)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=180,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip() == "False False", out.stdout


# --------------------------------------------------------------------- #
#  2. Tiered router — cheap tiers never wake the heavy tier              #
# --------------------------------------------------------------------- #

@pytest.fixture
def tracked_brain(monkeypatch):
    """A lazy brain whose fast tiers are live and whose heavy tier is a
    tripwire: if anything reaches it, the test knows."""
    brain = JarvisBrain(lazy=True)
    brain.prepare_fast_tiers()
    calls = []
    monkeypatch.setattr(brain, "_ensure_loaded", lambda: calls.append(1))
    return brain, calls


def test_exact_match_does_not_load_models(tracked_brain):
    brain, calls = tracked_brain
    # Any verbatim pattern from the corpus resolves on tier 0.
    pattern = next(iter(brain.classifier._exact_lookup))
    pred = brain.predict(pattern)
    assert pred.intent
    assert pred.confidence == 1.0
    assert calls == [], "exact-match tier must not load the encoder"


def test_arithmetic_does_not_load_models(tracked_brain):
    brain, calls = tracked_brain
    pred = brain.predict("2 + 2")
    assert pred.intent == "calculate"
    assert calls == []


def test_anchor_does_not_load_models(tracked_brain):
    brain, calls = tracked_brain
    pred = brain.predict("what is the time")
    assert pred.intent
    assert calls == []


def test_cache_hit_does_not_load_models(tracked_brain):
    brain, calls = tracked_brain
    pattern = next(iter(brain.classifier._exact_lookup))
    brain.predict(pattern)
    brain.predict(pattern)          # served from the LRU
    assert calls == []


def test_miss_does_reach_the_heavy_tier(tracked_brain):
    """The flip side: an utterance no cheap tier can answer MUST load the
    models — lite boot defers cost, it doesn't drop capability."""
    brain, calls = tracked_brain
    brain._neural_active = False
    served = []
    brain.classifier.predict = lambda text, threshold=0.5: served.append(text) or _stub_pred(text)
    brain.predict("zyada kuch nahi bas aise hi soch raha tha kal ke baare mein")
    assert calls == [1], "a cheap-tier miss must warm the heavy tier exactly once"
    assert served


def _stub_pred(text):
    from core.intent_classifier import Prediction
    return Prediction(intent=None, confidence=0.0, raw_text=text,
                      normalized_text=text)


# --------------------------------------------------------------------- #
#  3. Convergence — hooks fire when the heavy tier finally warms          #
# --------------------------------------------------------------------- #

def test_ml_loaded_hook_fires_once_on_cold_load(monkeypatch):
    brain = JarvisBrain(lazy=True)
    fired = []
    brain.add_ml_loaded_hook(lambda: fired.append(1))

    monkeypatch.setattr(brain.classifier, "load_encoder", lambda: None)
    monkeypatch.setattr(brain.classifier, "build_or_load_index", lambda: None)
    monkeypatch.setattr(brain.neural, "is_trained", lambda: False)

    brain._ensure_loaded()
    assert fired == [1]
    brain._ensure_loaded()          # already warm — no second fire
    assert fired == [1]


def test_ml_loaded_hook_failure_is_not_fatal(monkeypatch):
    brain = JarvisBrain(lazy=True)

    def boom():
        raise RuntimeError("spaCy exploded")

    brain.add_ml_loaded_hook(boom)
    ok = []
    brain.add_ml_loaded_hook(lambda: ok.append(1))

    monkeypatch.setattr(brain.classifier, "load_encoder", lambda: None)
    monkeypatch.setattr(brain.classifier, "build_or_load_index", lambda: None)
    monkeypatch.setattr(brain.neural, "is_trained", lambda: False)

    brain._ensure_loaded()          # must not raise
    assert brain.ml_loaded is True
    assert ok == [1], "a failing hook must not block the others"


def test_hook_fires_again_after_idle_unload(monkeypatch):
    """Idle-unload drops the weights; the next predict reloads them and the
    extras (which the unload also dropped nothing of, but which may need
    re-warming) get another chance."""
    brain = JarvisBrain(lazy=True)
    monkeypatch.setattr(brain.classifier, "load_encoder", lambda: None)
    monkeypatch.setattr(brain.classifier, "build_or_load_index", lambda: None)
    monkeypatch.setattr(brain.neural, "is_trained", lambda: False)
    fired = []
    brain.add_ml_loaded_hook(lambda: fired.append(1))

    brain._ensure_loaded()
    brain._idle_unload_s = 0
    assert brain.try_unload_idle() is True
    brain._ensure_loaded()
    assert fired == [1, 1]


# --------------------------------------------------------------------- #
#  Flag plumbing                                                         #
# --------------------------------------------------------------------- #

@pytest.mark.parametrize("val,want", [
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("0", False), ("", False), ("off", False), ("no", False),
])
def test_lite_flag_parsing(val, want):
    assert lite_ml_enabled(val) is want


def test_lite_flag_reads_env(monkeypatch):
    monkeypatch.setenv("AERIS_LITE_ML", "1")
    assert lite_ml_enabled() is True
    monkeypatch.delenv("AERIS_LITE_ML")
    assert lite_ml_enabled() is False


def test_torch_pin_is_idempotent():
    from core import torch_setup
    torch_setup._done = False
    first = torch_setup.pin_torch_threads()
    second = torch_setup.pin_torch_threads()
    assert second is False, "pin must be a one-shot"
    assert isinstance(first, bool)


# --------------------------------------------------------------------- #
#  4. Engine boot — which phases each mode actually runs                 #
# --------------------------------------------------------------------- #

def _boot_engine(monkeypatch, lite: bool, tmp_path):
    """Drive JarvisMainEngine.setup_iter with every heavy load stubbed, and
    report which ones it tried to run. Nothing loads a model."""
    monkeypatch.setenv("AERIS_LITE_ML", "1" if lite else "0")

    from core import main_engine as me

    ran: list[str] = []
    real_brain_cls = me.JarvisBrain

    class TrackedBrain(real_brain_cls):
        def load_encoder(self):
            ran.append("load_encoder")

        def load_neural_model(self):
            ran.append("load_neural_model")

        def build_or_load_index(self):
            ran.append("build_or_load_index")

        def prepare_fast_tiers(self):
            ran.append("prepare_fast_tiers")
            super().prepare_fast_tiers()

    monkeypatch.setattr(me, "JarvisBrain", TrackedBrain)

    from core import entity_extractor as ee
    monkeypatch.setattr(ee.EntityExtractor, "_init_spacy",
                        lambda self: ran.append("init_spacy"))

    from core import chat_gate
    monkeypatch.setattr(chat_gate, "ensure_ready",
                        lambda: ran.append("chat_gate_ready") or True)

    eng = me.JarvisMainEngine(
        stt="SKIP", tts="SKIP", verbose=False, lazy=True,
        enable_scheduler=False, enable_agent=False,
        memory_path=str(tmp_path / "mem.json"),
        feedback_db_path=str(tmp_path / "fb.sqlite"),
    )
    for _ in eng.setup_iter():
        pass
    return eng, ran


def test_eager_boot_loads_everything(monkeypatch, tmp_path):
    """The default path is unchanged — all five heavy phases still run."""
    eng, ran = _boot_engine(monkeypatch, lite=False, tmp_path=tmp_path)
    assert eng._lite_ml is False
    for phase in ("load_encoder", "load_neural_model", "build_or_load_index",
                  "init_spacy", "chat_gate_ready"):
        assert phase in ran, f"eager boot must still run {phase}: {ran}"
    assert "prepare_fast_tiers" not in ran


def test_lite_boot_loads_nothing_heavy(monkeypatch, tmp_path):
    """Lite boot runs the cheap tier-0 build and none of the heavy phases."""
    eng, ran = _boot_engine(monkeypatch, lite=True, tmp_path=tmp_path)
    assert eng._lite_ml is True
    assert "prepare_fast_tiers" in ran
    for phase in ("load_encoder", "load_neural_model", "build_or_load_index",
                  "init_spacy", "chat_gate_ready"):
        assert phase not in ran, f"lite boot must defer {phase}: {ran}"
    # …and the exact-match tier is nonetheless live.
    assert eng.brain.classifier._exact_lookup


def test_lite_boot_warms_extras_when_ml_arrives(monkeypatch, tmp_path):
    """The deferred extras come up the moment the heavy tier warms, so lite
    and eager converge instead of lite being permanently degraded."""
    eng, ran = _boot_engine(monkeypatch, lite=True, tmp_path=tmp_path)
    monkeypatch.setattr(eng.brain.classifier, "load_encoder", lambda: None)
    monkeypatch.setattr(eng.brain.classifier, "build_or_load_index", lambda: None)
    monkeypatch.setattr(eng.brain.neural, "is_trained", lambda: False)

    eng.brain._ensure_loaded()

    assert "init_spacy" in ran, f"spaCy must warm with the encoder: {ran}"
    assert "chat_gate_ready" in ran, f"chat gate must warm with the encoder: {ran}"

    # Idempotent — a second warm does not redo the work.
    before = list(ran)
    eng._warm_deferred_ml()
    assert ran == before


# --------------------------------------------------------------------- #
#  5. Deferred spaCy — loaded on first real need, not at boot            #
# --------------------------------------------------------------------- #

def _extractor(tmp_path):
    import os
    from core.entity_extractor import EntityExtractor
    from tests.conftest import PROJECT_ROOT
    e = EntityExtractor(
        entities_path=os.path.join(PROJECT_ROOT, "data", "entities.json"),
        intents_path=os.path.join(PROJECT_ROOT, "data", "intents.json"),
        lazy=True,
    )
    e._load_gazetteer()
    e._load_intents()
    return e


def test_ensure_spacy_noop_when_not_deferred(tmp_path):
    """Eager boot owns the spaCy load; the on-demand path must stay out of
    the way so nothing loads spaCy behind the engine's back."""
    e = _extractor(tmp_path)
    assert e.defer_spacy is False
    assert e._ensure_spacy() is False
    assert e.nlp is None


def test_ensure_spacy_loads_once_when_deferred(tmp_path, monkeypatch):
    e = _extractor(tmp_path)
    e.defer_spacy = True
    loads = []

    def fake_init(self):
        self._spacy_tried = True
        loads.append(1)
        self.nlp = object()

    monkeypatch.setattr(type(e), "_init_spacy", fake_init)
    assert e._ensure_spacy() is True
    assert e._ensure_spacy() is True          # already loaded
    assert loads == [1], "spaCy must load exactly once"


def test_ensure_spacy_does_not_retry_after_failure(tmp_path, monkeypatch):
    """A machine without en_core_web_sm must not re-attempt (and re-log) the
    load on every single utterance."""
    e = _extractor(tmp_path)
    e.defer_spacy = True
    tries = []

    def failing_init(self):
        self._spacy_tried = True
        tries.append(1)
        self.nlp = None

    monkeypatch.setattr(type(e), "_init_spacy", failing_init)
    assert e._ensure_spacy() is False
    assert e._ensure_spacy() is False
    assert tries == [1]


def test_ner_layer_is_skipped_when_no_ner_slot_is_needed(tmp_path, monkeypatch):
    """spacy.load() drags torch in (~220 MB via thinc) and extract() runs on
    EVERY dispatch — so the NER layer must not even ask for spaCy unless a
    person/time/date slot is actually required and still unfilled. An earlier
    version called _ensure_spacy() unconditionally here, which made the first
    command load the whole ML runtime under lite boot.
    """
    e = _extractor(tmp_path)
    e.defer_spacy = True
    asked = []
    monkeypatch.setattr(type(e), "_ensure_spacy",
                        lambda self: asked.append(1) or False)

    # open_app needs an app_name, never person/time/date.
    e.extract("notepad kholo", "open_app")
    assert asked == [], "asked for spaCy on a command with no NER slot"


def test_ner_layer_is_consulted_when_a_slot_needs_it(tmp_path, monkeypatch):
    """The flip side — a command that genuinely needs NER must still get it."""
    e = _extractor(tmp_path)
    e.defer_spacy = True
    asked = []
    monkeypatch.setattr(type(e), "_ensure_spacy",
                        lambda self: asked.append(1) or False)

    for intent, cfg in e.intents.items():
        req = cfg.get("slots") or cfg.get("required") or []
        if any(s in ("person", "time", "date") for s in req):
            e.extract("kal subah unse baat karni hai", intent)
            break
    else:
        pytest.skip("no intent in the corpus requires a person/time/date slot")

    assert asked, "an NER-needing command never consulted spaCy"
