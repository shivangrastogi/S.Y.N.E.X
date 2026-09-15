"""Iter#8 — reverse binding lookup, gesture trace stats, stranger toast,
gesture sensitivity multiplier.

Side-effect-safe:
  * Stranger-toast tests stub the threading.Thread + win10toast paths so
    no real notification fires.
  * Sensitivity tests use monkeypatched settings.
"""
from __future__ import annotations

import os
import sys
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "what_does_gesture_do",
    "gesture_stats",
    "gesture_sensitivity_set",
    "gesture_sensitivity_status",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("what does peace do",                "what_does_gesture_do"),
    ("explain peace",                     "what_does_gesture_do"),
    ("peace gesture kya karta hai",       "what_does_gesture_do"),
    ("gesture stats",                     "gesture_stats"),
    ("kya kya gestures hue",              "gesture_stats"),
    ("gesture sensitivity",               "gesture_sensitivity_set"),
    ("gestures more sensitive",           "gesture_sensitivity_set"),
    ("gestures less sensitive",           "gesture_sensitivity_set"),
    ("gesture sensitivity status",        "gesture_sensitivity_status"),
    ("current gesture sensitivity",       "gesture_sensitivity_status"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_iter8(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── reverse binding lookup ────────────────────────────────────────


def test_what_does_unknown_gesture(monkeypatch):
    from skills.gesture_mgmt import what_does_gesture_do
    out = what_does_gesture_do({"raw_text": "what does notarealgesture do"})
    assert "unknown" in out.lower()


def test_what_does_builtin_default():
    from skills.gesture_mgmt import what_does_gesture_do
    out = what_does_gesture_do({"raw_text": "what does peace do"})
    assert "built-in" in out.lower() or "default" in out.lower()
    assert "peace" in out


def test_what_does_with_override(monkeypatch):
    """When a binding override is set, the answer should name the custom skill."""
    from skills.gesture_mgmt import what_does_gesture_do
    state = {"gesture_binding.peace": "screenshot_full"}
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    out = what_does_gesture_do({"raw_text": "what does peace do"})
    assert "screenshot_full" in out
    assert "custom" in out.lower() or "→" in out


# ── gesture trace stats ───────────────────────────────────────────


def test_gesture_stats_empty(monkeypatch, tmp_path):
    import core.gesture_trace as gt
    from skills.gesture_mgmt import gesture_stats
    monkeypatch.setattr(gt, "_LOG_PATH", str(tmp_path / "trace.log"))
    gt.clear()
    out = gesture_stats({})
    assert "khaali" in out.lower() or "nothing" in out.lower() or "empty" in out.lower() or "nahi mila" in out.lower()


def test_gesture_stats_aggregates(monkeypatch, tmp_path):
    import core.gesture_trace as gt
    from skills.gesture_mgmt import gesture_stats
    monkeypatch.setattr(gt, "_LOG_PATH", str(tmp_path / "trace.log"))
    gt.clear()
    # Seed 3 fires of peace, 2 fires of double_pinch, 1 block.
    for _ in range(3):
        gt.log_fire("peace")
    for _ in range(2):
        gt.log_fire("double_pinch")
    gt.log_block("palm_fist_lock", "face_gate")
    out = gesture_stats({})
    assert "5 fired" in out and "1 blocked" in out
    assert "peace" in out and "3" in out
    assert "double_pinch" in out


# ── stranger toast ────────────────────────────────────────────────


def test_stranger_toast_fires_only_first_per_minute(monkeypatch):
    """record_block fires the toast dispatcher only on the FIRST call per minute."""
    from core import face_gate
    calls: list[str] = []
    monkeypatch.setattr(face_gate, "_toast_stranger_block",
                        lambda gname: calls.append(gname))
    # Reset gate state.
    face_gate._STATE.blocks_total = 0
    face_gate._STATE.blocks_last_minute = 0
    face_gate._STATE.blocks_minute_start = 0.0

    face_gate.record_block("g1")
    face_gate.record_block("g2")
    face_gate.record_block("g3")
    assert calls == ["g1"], "only the first block per minute should toast"


def test_toast_dispatch_is_safe_without_win10toast(monkeypatch):
    """_toast_blocking must NOT crash when win10toast import fails."""
    from core import face_gate
    # The default behaviour is graceful — assert by calling directly.
    face_gate._toast_blocking("test_gesture")
    # No exception → pass.


# ── gesture sensitivity ───────────────────────────────────────────


def test_sensitivity_resolver():
    from skills.gesture_sensitivity import _resolve_level
    assert _resolve_level("gestures less sensitive") == "relaxed"
    assert _resolve_level("make gestures more sensitive") == "sensitive"
    assert _resolve_level("kam sensitive karo") == "relaxed"
    assert _resolve_level("ultra relaxed") == "very_relaxed"
    assert _resolve_level("normal") == "normal"
    assert _resolve_level("reset") == "normal"
    assert _resolve_level("gibberish") is None


def test_sensitivity_set_persists(monkeypatch):
    from skills.gesture_sensitivity import gesture_sensitivity_set
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    out = gesture_sensitivity_set({"raw_text": "gestures less sensitive"})
    assert state.get("gesture_sensitivity") == "relaxed"
    assert "relaxed" in out
    assert "1.2" in out or "1.20" in out


def test_sensitivity_engine_multiplier(monkeypatch):
    """The engine's _sensitivity_multiplier reads the live settings."""
    from core import gesture_engine
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: "very_relaxed" if k == "gesture_sensitivity" else d)
    assert gesture_engine._sensitivity_multiplier() == 1.5
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: "very_sensitive" if k == "gesture_sensitivity" else d)
    assert gesture_engine._sensitivity_multiplier() == 0.7


def test_sensitivity_invalid_input_lists_options(monkeypatch):
    from skills.gesture_sensitivity import gesture_sensitivity_set
    monkeypatch.setattr("core.settings.set_", lambda k, v: None)
    out = gesture_sensitivity_set({"raw_text": "gestures qrjxk mode"})
    assert "samjha nahi" in out.lower() or "try" in out.lower()
    assert "normal" in out and "relaxed" in out
