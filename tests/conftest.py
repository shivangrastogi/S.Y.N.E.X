"""Pytest fixtures and collection rules.

The brain (and the engine that wraps it) loads a ~120 MB multilingual encoder
on first use. We share one instance per session via `shared_brain` and
`shared_engine` fixtures so the suite stays fast.

Old hardware-touching scripts in this folder (test_stt.py, test_tts.py) and
the legacy print-only test_brain.py are excluded from collection — they
predate this suite and would block on mics / speakers / unaserrtive prints.
"""

from __future__ import annotations

import os
import shutil
import sys

import pytest

# Make `core.*` imports work regardless of pytest's invocation directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

PROJECT_ROOT = _PROJECT_ROOT

# ---------------------------------------------------------------------------
# Load torch's native DLLs before anything can import PyQt5.
#
# The app entry points already do this (see core/torch_dll_preload and
# docs/…ROADMAP.md §6.15): on Windows, once Qt's CRT DLLs are resident, some
# torch builds can no longer initialise theirs, and `import torch` dies with
#
#     OSError: [WinError 1114] ... Error loading ...\torch\lib\c10.dll
#
# The suite had no such guard, so the fast lane was **order-dependent**: any
# Qt test that ran before a torch test poisoned it for the rest of the
# session. Reproduced on the current tree with two untouched files —
#
#     pytest tests/test_routine_builder.py tests/test_semantic_encoder_reuse.py
#
# fails, while `pytest tests/test_semantic_encoder_reuse.py` alone passes.
# That is a property of collection order, not of either test, and it means a
# green run proved less than it looked like it did.
#
# conftest is imported before any test module, which is the one place early
# enough for this to work — the preload is a no-op once Qt is loaded.
# Idempotent, silent, and skipped off Windows.
# ---------------------------------------------------------------------------
try:
    from core.torch_dll_preload import preload_torch_dlls
    preload_torch_dlls()
except Exception:
    pass

# ---------------------------------------------------------------------------
# Never start the phone bridge from the test suite.
#
# `JarvisMainEngine.setup_iter` auto-starts the cloud bridge whenever a
# pairing + service-account key exist. Every engine-constructing test was
# therefore opening a live Firestore `on_snapshot` listener against the real
# pairing and spawning BridgePresence + clipboard-sync daemon threads — none
# of which any test stops. They accumulated across the session and were still
# running (polling the Win32 clipboard) while later tests loaded torch and
# spaCy; that combination killed the full suite with 0xC0000374 three runs
# running. Tests should also simply never talk to the user's Firebase.
#
# Set before any test module imports, so no engine can beat it to the punch.
os.environ.setdefault("AERIS_DISABLE_BRIDGE", "1")


# Skip legacy hardware-touching scripts.
collect_ignore = [
    "test_stt.py",        # opens a microphone, hangs
    "test_tts.py",        # plays through speakers
    "test_brain.py",      # legacy print-only smoke; superseded by test_intent_classifier.py
]


# --- per-test temp paths ---------------------------------------------------

@pytest.fixture
def tmp_memory_path(tmp_path):
    """Fresh user_memory.json path per test (no pollution of real data)."""
    return str(tmp_path / "user_memory.json")


@pytest.fixture
def tmp_feedback_db(tmp_path):
    """Fresh SQLite path per test."""
    return str(tmp_path / "feedback.sqlite")


@pytest.fixture
def tmp_intents_copy(tmp_path):
    """A writable copy of intents.json so tests can mutate without side effects."""
    src = os.path.join(PROJECT_ROOT, "data", "intents.json")
    dst = str(tmp_path / "intents.json")
    shutil.copy(src, dst)
    return dst


# --- session-scoped heavy-load fixtures (shared across tests) -------------

@pytest.fixture(scope="session")
def shared_brain():
    """One JarvisBrain per session — model load is slow (~5s warm, ~30s cold)."""
    from core.brain import JarvisBrain
    return JarvisBrain()


@pytest.fixture(scope="session")
def shared_extractor():
    from core.entity_extractor import EntityExtractor
    return EntityExtractor(
        entities_path=os.path.join(PROJECT_ROOT, "data", "entities.json"),
        intents_path=os.path.join(PROJECT_ROOT, "data", "intents.json"),
    )


@pytest.fixture(scope="session")
def shared_sentiment():
    from core.sentiment import SentimentAnalyzer
    return SentimentAnalyzer()


# --- "slow" auto-marking -----------------------------------------------------
#
# These modules load the ~120 MB sentence-transformer encoder, the neural
# intent model, the entity extractor, or a full JarvisMainEngine. Running them
# serially is slow enough that a wall-clock-bounded runner kills the suite
# mid-run (see LOOP_UPGRADES I14). Rather than decorate every test in 25 files,
# we tag the whole module here so `pytest -m "not slow"` gives a fast green
# signal on the 1000+ pure-logic tests, and `pytest -m slow` runs the heavy
# ones on demand. Plain `pytest` still runs everything.

_SLOW_MODULES = {
    "test_app_launching_pipeline", "test_entity_extractor",
    "test_incremental_training", "test_loop_integration",
    "test_intent_classifier", "test_new_skills", "test_pipeline",
    "test_sentiment",
    "test_iter1_skills", "test_iter2_skills", "test_iter3_skills",
    "test_iter4_skills", "test_iter5_skills", "test_iter6_face_gate",
    "test_iter7_gesture_mgmt", "test_iter8_gesture_polish",
    "test_iter9_voice_perms",
    "test_tier1_phase1", "test_tier1_phase2", "test_tier2", "test_tier3",
    "test_tier4", "test_tier5", "test_tier5b", "test_tier6", "test_tier7",
    "test_tier8",
    # Process-isolation tests spawn real child processes — cheap in isolation
    # but Windows 'spawn' re-imports the suite, so they crawl inside the full
    # fast lane. Run them in the slow lane. (The RemoteBrain/run_split/brain
    # CONTRACT tests use fakes, spawn nothing, and stay in the fast lane.)
    "test_service_bus", "test_service_supervisor",
}


def pytest_collection_modifyitems(config, items):
    slow = pytest.mark.slow
    for item in items:
        # Match on the test file's stem via nodeid ("tests/test_pipeline.py::…")
        # — avoids importing item.module just to read its name.
        path = str(getattr(item, "fspath", "") or item.nodeid)
        stem = os.path.splitext(os.path.basename(path.split("::", 1)[0]))[0]
        if stem in _SLOW_MODULES:
            item.add_marker(slow)


# ---------------------------------------------------------------------------
# One QApplication for the whole session.
#
# Qt test modules used to each own a module-scoped `qapp` fixture doing
# `QApplication.instance() or QApplication([])`. That is fine alone and
# broken in combination: when the first module's fixture tears down, its
# local is the only reference left, the QApplication is garbage-collected,
# and every QObject it owned is destroyed with it — including the
# `ui.jarvis_v31.animation_bus` singleton, which is a module-level global.
# The next module then gets a *new* QApplication while `_instance` still
# holds a wrapper around freed C++ memory, and every panel that connects to
# `tick_slow` dies with:
#
#     RuntimeError: wrapped C/C++ object of type AnimationBus has been deleted
#
# Session scope keeps one application alive for the whole run, so the
# singleton it owns stays valid. Lazy, like every fixture — a non-Qt test
# session never creates one.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    # Deliberately not calling app.quit()/deleteLater(): pytest may still
    # tear down widget fixtures after this, and destroying the application
    # first is exactly the crash described above.
