"""Tests for main_engine._affect_tone — mood-coloured reply tone (P1 deepening).
Driven with a stubbed Affective Core, no engine boot."""
from __future__ import annotations

import core.affect as AFF
import core.main_engine as ME


class _StubCore:
    def __init__(self, mood):
        self._mood = mood

    def mood(self):
        return self._mood

    def modulate(self, reply):
        # mimic affect.modulate: prepend a gentle opener for non-neutral moods
        return f"Main yahin hoon. {reply}" if self._mood in ("low", "tired") else reply


class _Eng:
    _TONE_COOLDOWN_S = ME.JarvisMainEngine._TONE_COOLDOWN_S
    _affect_tone = ME.JarvisMainEngine._affect_tone

    def __init__(self):
        self._last_tone_at = 0.0


def test_colours_reply_for_low_mood(monkeypatch):
    monkeypatch.setattr(AFF, "get", lambda: _StubCore("low"))
    eng = _Eng()
    out = eng._affect_tone("Ho gaya, sir.")
    assert out == "Main yahin hoon. Ho gaya, sir."
    assert eng._last_tone_at > 0.0                     # cooldown started


def test_neutral_mood_leaves_reply_untouched(monkeypatch):
    monkeypatch.setattr(AFF, "get", lambda: _StubCore("neutral"))
    eng = _Eng()
    assert eng._affect_tone("Ho gaya.") == "Ho gaya."
    assert eng._last_tone_at == 0.0                    # never spent the cooldown


def test_rate_limited(monkeypatch):
    monkeypatch.setattr(AFF, "get", lambda: _StubCore("low"))
    import time
    eng = _Eng()
    eng._last_tone_at = time.time()                    # just coloured
    assert eng._affect_tone("Ho gaya.") == "Ho gaya."  # within cooldown → untouched


def test_no_opener_change_does_not_spend_cooldown(monkeypatch):
    # a non-neutral mood whose modulate() happens to add nothing → no cooldown spend
    monkeypatch.setattr(AFF, "get", lambda: _StubCore("excited"))
    eng = _Eng()
    assert eng._affect_tone("Badhiya chal raha hai.") == "Badhiya chal raha hai."
    assert eng._last_tone_at == 0.0
