"""Three-tier TTS fallback-chain tests (edge-tts → pyttsx3 → SAPI5).

Mocks each tier's ``_try_*`` method to fail or succeed in sequence and asserts
the chain reaches the next tier — without ever touching a speaker, edge_tts, or
COM. (The hardware-touching test_tts.py is skipped by conftest; this one runs.)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import core.tts as tts_mod
from core.tts import TTS


@pytest.fixture
def tts(monkeypatch):
    # Both optional tiers "available" so speak() will try them; the instance
    # methods are replaced per-test to control success/failure.
    monkeypatch.setattr(tts_mod, "_EDGE_OK", True)
    monkeypatch.setattr(tts_mod, "_PYTTSX3_OK", True)
    return TTS()


def _wire(tts, calls, *, edge, pyttsx3, sapi5):
    """Replace the three tier helpers with recorders returning the given bools."""
    def mk(name, ok):
        def _f(text):
            calls.append(name)
            return ok
        return _f
    tts._try_edge_tts = mk("edge", edge)
    tts._try_pyttsx3 = mk("pyttsx3", pyttsx3)
    tts._try_sapi5 = mk("sapi5", sapi5)


def test_edge_success_short_circuits(tts):
    calls = []
    _wire(tts, calls, edge=True, pyttsx3=True, sapi5=True)
    tts.speak("hello")
    assert calls == ["edge"]                 # nothing after a tier-1 win


def test_falls_through_to_pyttsx3(tts):
    calls = []
    _wire(tts, calls, edge=False, pyttsx3=True, sapi5=True)
    tts.speak("hello")
    assert calls == ["edge", "pyttsx3"]


def test_falls_through_to_sapi5(tts):
    calls = []
    _wire(tts, calls, edge=False, pyttsx3=False, sapi5=True)
    tts.speak("hello")
    assert calls == ["edge", "pyttsx3", "sapi5"]


def test_all_tiers_fail_no_exception(tts):
    calls = []
    _wire(tts, calls, edge=False, pyttsx3=False, sapi5=False)
    tts.speak("hello")                        # must not raise
    assert calls == ["edge", "pyttsx3", "sapi5"]


def test_empty_text_skips_all_tiers(tts):
    calls = []
    _wire(tts, calls, edge=True, pyttsx3=True, sapi5=True)
    tts.speak("")
    assert calls == []


def test_edge_disabled_skips_tier1(tts, monkeypatch):
    monkeypatch.setattr(tts_mod, "_EDGE_OK", False)
    calls = []
    _wire(tts, calls, edge=True, pyttsx3=True, sapi5=True)
    tts.speak("hello")
    assert calls == ["pyttsx3"]               # tier 1 gated off entirely


def test_pyttsx3_disabled_skips_tier2(tts, monkeypatch):
    monkeypatch.setattr(tts_mod, "_PYTTSX3_OK", False)
    calls = []
    _wire(tts, calls, edge=False, pyttsx3=True, sapi5=True)
    tts.speak("hello")
    assert calls == ["edge", "sapi5"]
