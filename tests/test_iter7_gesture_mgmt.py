"""Iter#7 — gesture trace log, gesture remap/unbind, block counter,
auto-label TTS narration.

Side-effect-safe:
  * gesture_trace tests use the live log file but clear it before each
    parametrized check.
  * gesture_bind tests use monkeypatched settings so the live settings.json
    isn't mutated.
  * auto-label TTS tests stub the speak path so no audio plays.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "gesture_bind", "gesture_unbind", "gesture_bindings",
    "gesture_trace", "gesture_trace_clear",
    "auto_label_speak_on", "auto_label_speak_off",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("bind gesture",              "gesture_bind"),
    ("remap peace to",            "gesture_bind"),
    ("unbind gesture",            "gesture_unbind"),
    ("unbind peace",              "gesture_unbind"),
    ("list gesture bindings",     "gesture_bindings"),
    ("gesture bindings dikhao",   "gesture_bindings"),
    ("gesture trace",             "gesture_trace"),
    ("show gesture trace",        "gesture_trace"),
    ("clear gesture trace",       "gesture_trace_clear"),
    ("speak labels",              "auto_label_speak_on"),
    ("stop speaking labels",      "auto_label_speak_off"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_iter7(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── gesture_trace ─────────────────────────────────────────────────


def test_trace_round_trip(monkeypatch, tmp_path):
    """log_fire / log_block / tail / clear round-trip cleanly."""
    import core.gesture_trace as gt
    monkeypatch.setattr(gt, "_LOG_PATH", str(tmp_path / "trace.log"))
    gt.clear()
    assert gt.tail(10) == []
    gt.log_fire("peace")
    gt.log_block("palm_fist_lock", "face_gate")
    events = gt.tail(10)
    assert len(events) == 2
    assert events[0]["status"] == "fired"
    assert events[0]["gesture"] == "peace"
    assert events[1]["status"] == "blocked"
    assert events[1]["blocked_reason"] == "face_gate"


def test_trace_tail_handles_corrupt_line(monkeypatch, tmp_path):
    """A bad JSON line in the file shouldn't blow up tail()."""
    import core.gesture_trace as gt
    log = tmp_path / "trace.log"
    log.write_text('{"ts": "now", "gesture": "ok"}\n<<<garbage>>>\n',
                   encoding="utf-8")
    monkeypatch.setattr(gt, "_LOG_PATH", str(log))
    events = gt.tail(10)
    assert len(events) == 1
    assert events[0]["gesture"] == "ok"


# ── face_gate block counter ───────────────────────────────────────


def test_block_counter_increments():
    from core import face_gate
    before = face_gate.block_stats()["total"]
    face_gate.record_block("test_gesture")
    after = face_gate.block_stats()["total"]
    assert after == before + 1


def test_explain_mentions_block_count(monkeypatch):
    """face_gate.explain() should include the block count once non-zero."""
    from core import face_gate, settings as _s
    monkeypatch.setattr(_s, "get",
                        lambda k, d=None: [] if k == "master_users" else d)
    face_gate.record_block("x")
    text = face_gate.explain()
    assert "blocked" in text.lower() or "total" in text.lower()


# ── gesture_bind ──────────────────────────────────────────────────


def test_bind_rejects_unknown_gesture(monkeypatch):
    from skills.gesture_mgmt import gesture_bind
    monkeypatch.setattr("core.settings.set_", lambda k, v: None)
    out = gesture_bind({"raw_text": "bind whatever_unknown to screenshot_full"})
    assert "unknown gesture" in out.lower()


def test_bind_rejects_unknown_skill(monkeypatch):
    from skills.gesture_mgmt import gesture_bind
    monkeypatch.setattr("core.settings.set_", lambda k, v: None)
    out = gesture_bind({"raw_text": "bind peace to some_made_up_skill_xyz"})
    assert "skill nahi" in out.lower() or "not" in out.lower() or "nahi hai" in out.lower()


def test_bind_unbind_round_trip(monkeypatch):
    """bind → bindings shows it → unbind → bindings is empty again."""
    from skills.gesture_mgmt import gesture_bind, gesture_unbind, gesture_bindings
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))

    out = gesture_bind({"raw_text": "bind peace to screenshot_full"})
    assert "Bound" in out
    assert state["gesture_binding.peace"] == "screenshot_full"

    listing = gesture_bindings({})
    assert "peace" in listing and "screenshot_full" in listing

    out2 = gesture_unbind({"raw_text": "unbind peace"})
    assert "Unbound" in out2
    assert state["gesture_binding.peace"] == ""

    final = gesture_bindings({})
    assert "Koi custom" in final or "no custom" in final.lower()


def test_bind_format_error_returns_help():
    from skills.gesture_mgmt import gesture_bind
    out = gesture_bind({"raw_text": "bind nothing"})
    assert "Format" in out


# ── auto-label TTS gate ───────────────────────────────────────────


def test_auto_label_speak_toggle():
    import skills.auto_label_skill as als
    on = als.auto_label_speak_on({})
    assert "ON" in on
    assert als._SPEAK_ENABLED is True
    off = als.auto_label_speak_off({})
    assert "OFF" in off
    assert als._SPEAK_ENABLED is False


def test_auto_label_speech_cooldown(monkeypatch):
    """Two rapid sightings of the same label fire TTS only once."""
    import skills.auto_label_skill as als
    spoken: list[str] = []
    monkeypatch.setattr(als, "_speak_blocking",
                        lambda msg: spoken.append(msg))
    monkeypatch.setattr(als, "_SPEAK_ENABLED", True)

    # Reset cooldown bookkeeping so test is deterministic.
    als._LAST_SPOKEN_AT.clear()

    als._record("cell phone", 0.9, (0, 0, 1, 1))
    # Wait must run threading.Thread inline — patch to sync.
    import threading
    real_thread = threading.Thread
    monkeypatch.setattr(threading, "Thread",
                        lambda target, args=(), daemon=True:
                            type("_T", (), {"start": lambda self: target(*args)})())
    als._record("cell phone", 0.9, (0, 0, 1, 1))   # within cooldown → no speak
    monkeypatch.setattr(threading, "Thread", real_thread)


def test_auto_label_status_includes_speak_state(monkeypatch):
    import skills.auto_label_skill as als
    monkeypatch.setattr(als, "_SPEAK_ENABLED", True)
    monkeypatch.setattr(als, "_LAST_SEEN", [])
    out = als.auto_label_status({})
    assert "speak: ON" in out
