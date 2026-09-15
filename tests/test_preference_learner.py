"""Tests for preference learning (core.preference_learner) — Blueprint loop 1.
Fake fabric, no model/disk.
"""

from core.preference_learner import (
    PreferenceLearner,
    detect_preference,
)


# ── detection (conservative — no command collisions) ───────────────

def test_detects_clear_preferences():
    assert detect_preference("I prefer PhonePe over GPay")
    assert detect_preference("mujhe dark theme pasand hai")
    assert detect_preference("next time use the metric system")
    assert detect_preference("agli baar subah wali route lena")


def test_ignores_commands_and_chatter():
    # command-ambiguous phrasings must NOT be treated as preferences
    assert detect_preference("chrome ki jagah firefox kholo") is None
    assert detect_preference("torch on karo") is None
    assert detect_preference("call rahul") is None
    assert detect_preference("aaj mausam kaisa hai") is None
    assert detect_preference("") is None


# ── learning writes to the fabric ──────────────────────────────────

class FakeFabric:
    def __init__(self):
        self.remembered = []

    def remember(self, text, *, kind="auto", subject=None, role="user"):
        self.remembered.append((text, kind))
        return kind


def test_learn_persists_preference_as_note():
    fab = FakeFabric()
    lrn = PreferenceLearner(fabric_provider=lambda: fab)
    out = lrn.learn("I prefer PhonePe over GPay")
    assert out == "I prefer PhonePe over GPay"
    assert fab.remembered == [("Preference: I prefer PhonePe over GPay", "note")]


def test_learn_ignores_non_preference():
    fab = FakeFabric()
    lrn = PreferenceLearner(fabric_provider=lambda: fab)
    assert lrn.learn("open chrome") is None
    assert fab.remembered == []


def test_learn_survives_store_error():
    def boom():
        raise RuntimeError("store down")
    lrn = PreferenceLearner(fabric_provider=boom)
    assert lrn.learn("I prefer tea") is None  # no crash
