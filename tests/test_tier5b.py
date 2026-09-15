"""Tier 5b — live transcript bus, gesture practice loop, permissions matrix.

Side-effect-safe:
  * Transcript tests use the bus directly — no PyQt5 window opens.
  * Practice tests synthesise gesture events via the engine's listener API
    (the GestureEngine is started lazily; we patch it out where it would
    try to grab the camera).
  * Permissions tests exercise the pure ``build_matrix`` / ``matrix_to_perms``
    helpers — the QDialog never opens.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "transcript_on", "transcript_off", "transcript_status", "transcript_log",
    "practice_gesture", "practice_status", "practice_stop",
    "open_permissions_editor",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("transcript on",              "transcript_on"),
    ("show transcript",            "transcript_on"),
    ("captions on",                "transcript_on"),
    ("transcript off",             "transcript_off"),
    ("transcript status",          "transcript_status"),
    ("transcript log",             "transcript_log"),
    ("practice gesture",           "practice_gesture"),
    ("practice peace",             "practice_gesture"),
    ("practice status",            "practice_status"),
    ("practice stop",              "practice_stop"),
    ("open permissions editor",    "open_permissions_editor"),
    ("permissions editor",         "open_permissions_editor"),
    ("edit permissions",           "open_permissions_editor"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier5b(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── transcript_bus ────────────────────────────────────────────────


def test_bus_publish_fans_out():
    from core.transcript_bus import get_bus
    bus = get_bus()
    bus.clear()
    received = []
    bus.add_listener(received.append)
    bus.publish("hello", "final")
    bus.publish("world", "partial")
    assert len(received) == 2
    assert received[0]["text"] == "hello"
    assert received[0]["role"] == "final"
    assert received[1]["role"] == "partial"


def test_bus_recent_returns_tail():
    from core.transcript_bus import get_bus
    bus = get_bus()
    bus.clear()
    for i in range(15):
        bus.publish(f"line {i}")
    tail = bus.recent(5)
    assert len(tail) == 5
    assert tail[-1]["text"] == "line 14"


def test_bus_remove_listener():
    from core.transcript_bus import get_bus
    bus = get_bus()
    bus.clear()
    seen = []
    fn = lambda e: seen.append(e)
    bus.add_listener(fn)
    bus.publish("a")
    assert len(seen) == 1
    removed = bus.remove_listener(fn)
    assert removed is True
    bus.publish("b")
    assert len(seen) == 1, "removed listener should not receive new events"


def test_bus_empty_text_ignored():
    from core.transcript_bus import get_bus
    bus = get_bus()
    bus.clear()
    bus.publish("")
    bus.publish(None)  # type: ignore[arg-type]
    assert bus.recent(10) == []


def test_bus_clear_returns_count():
    from core.transcript_bus import get_bus
    bus = get_bus()
    bus.clear()
    bus.publish("a"); bus.publish("b")
    assert bus.clear() == 2
    assert bus.recent(10) == []


def test_transcript_skill_log_when_empty():
    from core.transcript_bus import get_bus
    from skills.transcript_skill import transcript_log
    get_bus().clear()
    out = transcript_log({})
    assert "khaali" in out.lower() or "empty" in out.lower()


def test_transcript_skill_status_returns_text():
    from skills.transcript_skill import transcript_status
    out = transcript_status({})
    assert "Transcript" in out


# ── gesture_practice ─────────────────────────────────────────────


def test_practice_parser_extracts_target_and_duration():
    from skills.gesture_practice_skill import _parse
    target, dur = _parse("practice peace for 60 seconds")
    assert target == "peace"
    assert dur == 60
    target, dur = _parse("practice double_pinch for 2 minutes")
    assert target == "double_pinch"
    assert dur == 120
    target, dur = _parse("practice peace")
    assert target == "peace"
    assert dur == 30   # default


def test_practice_skill_no_target():
    from skills.gesture_practice_skill import practice_gesture
    out = practice_gesture({"raw_text": "practice"})
    assert "Kaunsa" in out or "target" in out.lower()


def test_practice_session_counts_hits(monkeypatch):
    """Synthesise the gesture-engine listener path: start_practice attaches
    a listener; firing _on_gesture(target) bumps the hit counter."""
    import core.gesture_practice as gp
    # Stub GestureEngine.add_listener / is_enabled / start so no camera opens.
    class _FakeEng:
        listeners = []
        def is_enabled(self): return True
        def start(self): return True
        def add_listener(self, fn): _FakeEng.listeners.append(fn)
    monkeypatch.setattr("core.gesture_engine.get_gesture_engine",
                        lambda: _FakeEng())
    gp._SESSION = None
    sess = gp.start_practice("peace", session_seconds=10)
    assert sess.get("error") is None
    # Simulate engine firing — three peace hits + one miss.
    gp._on_gesture("peace")
    gp._on_gesture("peace")
    gp._on_gesture("swipe_left")    # miss
    gp._on_gesture("peace")
    snap = gp.status()
    assert snap["hits"] == 3
    assert snap["misses"] == 1
    assert 0.7 < snap["accuracy"] <= 0.8


def test_practice_stop_returns_final_stats(monkeypatch):
    import core.gesture_practice as gp
    class _FakeEng:
        def is_enabled(self): return True
        def start(self): return True
        def add_listener(self, fn): pass
    monkeypatch.setattr("core.gesture_engine.get_gesture_engine",
                        lambda: _FakeEng())
    gp._SESSION = None
    gp.start_practice("peace", session_seconds=10)
    gp._on_gesture("peace")
    final = gp.stop_practice()
    assert final is not None
    assert final["hits"] == 1
    # Subsequent status should report no session.
    snap = gp.status()
    assert snap is None or snap.get("running") is False


def test_practice_status_when_idle():
    from core import gesture_practice as gp
    gp._SESSION = None
    from skills.gesture_practice_skill import practice_status
    out = practice_status({})
    assert "nahi" in out.lower() or "no" in out.lower()


# ── permissions_editor ────────────────────────────────────────────


def test_build_matrix_all_grants_full_row():
    from ui.permissions_editor import build_matrix
    perms = {"shivang": ["all"]}
    m = build_matrix(["shivang"], perms, ["peace", "double_pinch"])
    assert m["shivang"]["peace"] is True
    assert m["shivang"]["double_pinch"] is True


def test_build_matrix_unknown_master_defaults_open():
    """A master not in perms gets every checkbox ticked (backward compat)."""
    from ui.permissions_editor import build_matrix
    m = build_matrix(["new_guy"], {}, ["peace", "double_pinch"])
    assert m["new_guy"]["peace"] is True
    assert m["new_guy"]["double_pinch"] is True


def test_build_matrix_explicit_allowlist():
    from ui.permissions_editor import build_matrix
    perms = {"kid": ["peace"]}
    m = build_matrix(["kid"], perms, ["peace", "double_pinch", "palm_fist_lock"])
    assert m["kid"]["peace"] is True
    assert m["kid"]["double_pinch"] is False
    assert m["kid"]["palm_fist_lock"] is False


def test_matrix_to_perms_collapses_all():
    from ui.permissions_editor import matrix_to_perms
    m = {"shivang": {"peace": True, "double_pinch": True}}
    out = matrix_to_perms(m)
    assert out["shivang"] == ["all"]


def test_matrix_to_perms_partial_list():
    from ui.permissions_editor import matrix_to_perms
    m = {"kid": {"peace": True, "double_pinch": False, "palm_fist_lock": False}}
    out = matrix_to_perms(m)
    assert out["kid"] == ["peace"]


def test_matrix_to_perms_empty_row():
    """Master with no checked gestures should still appear with an empty
    allowlist (interpreted as 'totally blocked' by face_gate)."""
    from ui.permissions_editor import matrix_to_perms
    m = {"locked_out": {"peace": False, "double_pinch": False}}
    out = matrix_to_perms(m)
    assert out["locked_out"] == []


def test_matrix_round_trip_preserves_semantic():
    """build_matrix → matrix_to_perms should preserve the meaning even if
    the representation changes (explicit list ↔ 'all')."""
    from ui.permissions_editor import build_matrix, matrix_to_perms
    gestures = ["peace", "double_pinch", "palm_fist_lock"]
    masters = ["shivang", "kid"]
    perms = {"shivang": ["all"], "kid": ["peace", "double_pinch"]}
    m = build_matrix(masters, perms, gestures)
    out = matrix_to_perms(m)
    # Shivang is fully allowed → 'all'
    assert out["shivang"] == ["all"]
    # Kid keeps the same gestures
    assert sorted(out["kid"]) == ["double_pinch", "peace"]


def test_permissions_editor_skill_returns_immediately():
    """Skill spawns a daemon thread, returns fast."""
    import time
    from skills.permissions_editor_skill import open_permissions_editor
    t0 = time.monotonic()
    out = open_permissions_editor({})
    assert time.monotonic() - t0 < 0.5
    assert "permissions" in out.lower()
