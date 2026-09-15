"""Tests for the Phase 4 anticipation SURFACE — main_engine._maybe_offer /
_resolve_pending (the offer→confirm loop). Both helpers only use a handful of
`self` attributes, so we drive them with a lightweight stub — no engine boot.
"""
from __future__ import annotations

import time

import core.anticipation as ANT
from core.main_engine import JarvisMainEngine as J


class _State:
    def __init__(self, waiting=False):
        self._w = waiting

    def is_waiting_slot(self):
        return self._w


class _Eng:
    _recently_offered = J._recently_offered           # bind the real dedup helper

    def __init__(self, waiting=False):
        self.state = _State(waiting)
        self._last_suggest_at = 0.0
        self._pending_suggestion = None


def _learned_singleton(tmp_path, monkeypatch):
    a = ANT.Anticipator(path=str(tmp_path / "a.json"), enabled=True, min_support=3)
    for _ in range(5):
        a.observe("get_time", "gmail kholo", "open_app", "morning")
    monkeypatch.setattr(ANT, "_DEFAULT", a)      # auto-restored after the test
    return a


def test_offer_appended_then_confirmed(tmp_path, monkeypatch):
    _learned_singleton(tmp_path, monkeypatch)
    eng = _Eng()
    out = J._maybe_offer(eng, "Abhi 10 baj rahe hain.", "morning", "get_time", "time kya hua")
    assert "gmail kholo karoon?" in out
    assert eng._pending_suggestion == "gmail kholo"
    # a "haan" resolves to the suggested command...
    assert J._resolve_pending(eng, "haan") == "gmail kholo"
    assert eng._pending_suggestion is None
    # ...and it's single-shot.
    assert J._resolve_pending(eng, "haan") is None


def test_rate_limited(tmp_path, monkeypatch):
    _learned_singleton(tmp_path, monkeypatch)
    eng = _Eng()
    eng._last_suggest_at = time.time()           # just offered
    out = J._maybe_offer(eng, "Time.", "morning", "get_time", "time kya hua")
    assert out == "Time." and eng._pending_suggestion is None


def test_no_offer_during_slot_fill(tmp_path, monkeypatch):
    _learned_singleton(tmp_path, monkeypatch)
    eng = _Eng(waiting=True)
    assert J._maybe_offer(eng, "Kya?", "morning", "get_time", "x") == "Kya?"


def test_no_offer_of_what_was_just_done(tmp_path, monkeypatch):
    _learned_singleton(tmp_path, monkeypatch)
    eng = _Eng()
    # user literally just said "gmail kholo" → don't offer it back
    out = J._maybe_offer(eng, "Khol diya.", "morning", "get_time", "gmail kholo")
    assert out == "Khol diya." and eng._pending_suggestion is None


def test_resolve_non_confirmation_drops_offer():
    eng = _Eng()
    eng._pending_suggestion = "gmail kholo"
    assert J._resolve_pending(eng, "nahi abhi nahi") is None
    assert eng._pending_suggestion is None       # dropped, not carried over


def test_resolve_no_pending():
    assert J._resolve_pending(_Eng(), "haan") is None


# ── dedup guard (shared with the Cognition habit thought) ────────────────
def test_recently_offered_dedup():
    eng = _Eng()
    assert eng._recently_offered("gmail kholo", now=1000.0) is False   # first → records
    assert eng._recently_offered("gmail kholo", now=1100.0) is True    # repeat within window
    assert eng._recently_offered("chrome kholo", now=1100.0) is False  # different cmd
    assert eng._recently_offered("gmail kholo", now=1000.0 + 5000.0) is False  # window elapsed


def test_maybe_offer_skips_already_offered(tmp_path, monkeypatch):
    _learned_singleton(tmp_path, monkeypatch)
    eng = _Eng()
    # pretend Cognition already offered "gmail kholo" a moment ago
    eng._last_offered_cmd = "gmail kholo"
    import time
    eng._last_offered_at = time.time()
    out = J._maybe_offer(eng, "Time.", "morning", "get_time", "time kya hua")
    assert out == "Time." and eng._pending_suggestion is None
