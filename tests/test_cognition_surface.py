"""Tests for the Phase 6 cognition SURFACE — main_engine._surface_cognition.
Drives the method with a stub engine + a stubbed Cognition Loop, so no boot.
"""
from __future__ import annotations

import core.cognition as COG
import core.context_bus as CB
import core.continuity as CONT
import core.main_engine as ME
from core.cognition import Thought
from core.context_bus import ContextSnapshot


def _boom():
    raise RuntimeError("no router in test")


def _snap(**kw):
    base = dict(
        ts=0.0, hour=14, time_of_day="afternoon", is_quiet_hours=False,
        active_app=None, active_title=None, recent_commands=("time",),
        recent_intents=("get_time",), mood="neutral", presence="active",
        idle_seconds=0.0, battery_pct=None, next_event=None, summary="",
    )
    base.update(kw)
    return ContextSnapshot(**base)


class _Bus:
    """Stub Context Bus returning a fixed snapshot; push calls are no-ops."""
    def __init__(self, snap):
        self._snap = snap

    def set_battery(self, *a):
        pass

    def set_next_event(self, *a):
        pass

    def snapshot(self, *a, **k):
        return self._snap


class _Eng:
    _tts = "laptop"
    _pending_suggestion = None
    _recently_offered = ME.JarvisMainEngine._recently_offered     # real helpers
    _speak_proactive = ME.JarvisMainEngine._speak_proactive
    _autodo_allowed = ME.JarvisMainEngine._autodo_allowed
    _auto_do = ME.JarvisMainEngine._auto_do

    def __init__(self):
        self.spoken = []
        self.ran = []

    def _speak(self, msg):
        self.spoken.append(msg)

    def process_text(self, text, **kw):
        self.ran.append(text)
        return f"{text} ho gaya"


def test_surface_speaks_and_parks_actionable(monkeypatch):
    monkeypatch.setattr(COG, "get", lambda: _StubCog(
        Thought("battery", "Battery 10% — charger laga lein?",
                "charge reminder set karo", "offer", 90)))
    monkeypatch.setattr(CONT, "get_router", _boom)   # force self._speak fallback
    eng = _Eng()
    ME.JarvisMainEngine._surface_cognition(eng)
    assert eng.spoken == ["Battery 10% — charger laga lein?"]
    assert eng._pending_suggestion == "charge reminder set karo"


def test_surface_speaks_nonactionable_without_parking(monkeypatch):
    monkeypatch.setattr(COG, "get", lambda: _StubCog(
        Thought("rest", "Raat ho gayi — aaram karo.", None, "offer", 40)))
    monkeypatch.setattr(CONT, "get_router", _boom)
    eng = _Eng()
    ME.JarvisMainEngine._surface_cognition(eng)
    assert eng.spoken == ["Raat ho gayi — aaram karo."]
    assert eng._pending_suggestion is None


def test_surface_silent_when_no_thought(monkeypatch):
    monkeypatch.setattr(COG, "get", lambda: _StubCog(None))
    eng = _Eng()
    ME.JarvisMainEngine._surface_cognition(eng)
    assert eng.spoken == [] and eng._pending_suggestion is None


def test_surface_skipped_in_headless_test_engine(monkeypatch):
    fired = []
    monkeypatch.setattr(COG, "get", lambda: _StubCog(
        Thought("x", "y", None, "offer", 1), fired))
    eng = _Eng()
    eng._tts = "SKIP"                                 # headless test engine
    ME.JarvisMainEngine._surface_cognition(eng)
    assert fired == [] and eng.spoken == []           # never even reflected


# ── L3 silent auto-do ────────────────────────────────────────────────────
def _do_thought():
    return Thought("habit", "gmail kholo kar diya.", "gmail kholo", "auto", 55, "do")


def test_autodo_executes_at_trusted_autonomy(monkeypatch):
    monkeypatch.setenv("AERIS_AUTONOMY_LEVEL", "3")
    monkeypatch.setattr(CB, "get", lambda: _Bus(_snap()))
    monkeypatch.setattr(COG, "get", lambda: _StubCog(_do_thought()))
    monkeypatch.setattr(CONT, "get_router", _boom)
    eng = _Eng()
    ME.JarvisMainEngine._surface_cognition(eng)
    assert eng.ran == ["gmail kholo"]                 # actually executed
    assert eng.spoken == ["gmail kholo ho gaya"]      # reported the real result
    assert eng._pending_suggestion is None            # nothing to confirm — it's done


def test_autodo_downgrades_to_offer_below_level3(monkeypatch):
    monkeypatch.setenv("AERIS_AUTONOMY_LEVEL", "1")
    monkeypatch.setattr(CB, "get", lambda: _Bus(_snap()))
    monkeypatch.setattr(COG, "get", lambda: _StubCog(_do_thought()))
    monkeypatch.setattr(CONT, "get_router", _boom)
    eng = _Eng()
    ME.JarvisMainEngine._surface_cognition(eng)
    assert eng.ran == []                              # NOT executed
    assert eng.spoken == ["gmail kholo karoon?"]      # re-phrased as a question, not "kar diya"
    assert eng._pending_suggestion == "gmail kholo"   # parked for a "haan"


def test_autodo_blocked_when_user_absent(monkeypatch):
    monkeypatch.setenv("AERIS_AUTONOMY_LEVEL", "3")
    # no recent commands → user not present → never auto-act
    monkeypatch.setattr(CB, "get", lambda: _Bus(_snap(recent_commands=())))
    monkeypatch.setattr(COG, "get", lambda: _StubCog(_do_thought()))
    monkeypatch.setattr(CONT, "get_router", _boom)
    eng = _Eng()
    ME.JarvisMainEngine._surface_cognition(eng)
    assert eng.ran == [] and eng._pending_suggestion == "gmail kholo"


def test_autodo_blocked_in_quiet_hours(monkeypatch):
    monkeypatch.setenv("AERIS_AUTONOMY_LEVEL", "3")
    monkeypatch.setattr(CB, "get", lambda: _Bus(_snap(is_quiet_hours=True)))
    monkeypatch.setattr(COG, "get", lambda: _StubCog(_do_thought()))
    monkeypatch.setattr(CONT, "get_router", _boom)
    eng = _Eng()
    ME.JarvisMainEngine._surface_cognition(eng)
    assert eng.ran == []                              # silent hours → no auto-act


class _StubCog:
    def __init__(self, thought, fired=None):
        self._t = thought
        self._fired = fired

    def reflect(self, snap, now=None):
        if self._fired is not None:
            self._fired.append(1)
        return self._t
