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
