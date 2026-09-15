"""Iter#6 — master-user face gate, auto-label engine, gesture revamp.

Side-effect-safe:
  * face_gate tests stub the recognizer so no real InsightFace inference runs.
  * auto_label tests stub the ObjectDetector + VisionEngine so no camera
    is opened.
  * Gesture revamp tests assert constant tuning + the new velocity gate
    in _maybe_emit_swipe.
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
    "register_face", "i_am_master",
    "add_master", "remove_master",
    "list_masters", "face_gate_status",
    "auto_label_on", "auto_label_off", "auto_label_status",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("register my face",         "register_face"),
    ("register face as shivang", "register_face"),
    ("i am master",              "i_am_master"),
    ("set me as master",         "i_am_master"),
    ("add master",               "add_master"),
    ("remove master",            "remove_master"),
    ("list masters",             "list_masters"),
    ("face gate status",         "face_gate_status"),
    ("auto label on",            "auto_label_on"),
    ("auto label off",           "auto_label_off"),
    # "describe what you see" moved to detect_scene in the 2026-07-04
    # pattern unification (one-shot description vs continuous labeling).
    ("describe what you see",    "detect_scene"),
    ("auto label status",        "auto_label_status"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_iter6(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── face_gate behaviour ───────────────────────────────────────────


def _reset_gate_state():
    """Wipe the in-process gate cache so tests don't bleed into each other."""
    from core import face_gate
    with face_gate._STATE.lock:
        face_gate._STATE.last_inference_at = 0.0
        face_gate._STATE.last_names = []
        face_gate._STATE.last_master_seen_at = 0.0
        face_gate._STATE.settings_cache_at = 0.0
        face_gate._STATE.masters_cache = []
        face_gate._STATE.strict_cache = False


def test_face_gate_open_when_no_masters_set(monkeypatch):
    from core import settings as _s, face_gate
    _reset_gate_state()
    monkeypatch.setattr(_s, "get",
                        lambda k, d=None: [] if k == "master_users" else d)
    assert face_gate.is_master_present(None) is True
    assert "DISABLED" in face_gate.explain()


def test_face_gate_blocks_unknown_when_masters_set(monkeypatch):
    from core import settings as _s, face_gate
    _reset_gate_state()
    settings_map = {"master_users": ["shivang"], "master_gate_strict": False}
    monkeypatch.setattr(_s, "get",
                        lambda k, d=None: settings_map.get(k, d))

    # Fake recognizer says: a stranger is in frame (None).
    class _FakeRec:
        def is_available(self): return True
        def identify_faces(self, frame): return [None]
    monkeypatch.setattr("core.face_recognition.get_recognizer", lambda: _FakeRec())

    # First call without a frame → no inference yet, no last-seen master.
    # Lax mode + no-face → True. But we have last_names empty, so we hit
    # _decide which says "no names + lax → True". With a frame and a
    # stranger detected, the decision should flip to False.
    fake_frame = object()
    allowed = face_gate.is_master_present(fake_frame)
    assert allowed is False, "stranger present + lax mode should still block (master not seen)"


def test_face_gate_allows_master(monkeypatch):
    from core import settings as _s, face_gate
    _reset_gate_state()
    settings_map = {"master_users": ["shivang"], "master_gate_strict": False}
    monkeypatch.setattr(_s, "get",
                        lambda k, d=None: settings_map.get(k, d))

    class _FakeRec:
        def is_available(self): return True
        def identify_faces(self, frame): return ["Shivang"]   # case-insensitive
    monkeypatch.setattr("core.face_recognition.get_recognizer", lambda: _FakeRec())

    assert face_gate.is_master_present(object()) is True


def test_face_gate_grace_window(monkeypatch):
    """After seeing a master, brief detection misses should still pass."""
    from core import settings as _s, face_gate
    _reset_gate_state()
    settings_map = {"master_users": ["shivang"], "master_gate_strict": False}
    monkeypatch.setattr(_s, "get",
                        lambda k, d=None: settings_map.get(k, d))

    # Seed: master was seen 1.0 s ago (< 2.5 s grace).
    face_gate._STATE.last_master_seen_at = time.monotonic() - 1.0
    face_gate._STATE.last_inference_at = time.monotonic()  # inside throttle
    face_gate._STATE.last_names = [None]  # current frame is empty
    assert face_gate.is_master_present(None) is True


def test_face_gate_fails_open_on_recognizer_unavailable(monkeypatch):
    """If insightface is missing, gate should NOT lock the user out."""
    from core import settings as _s, face_gate
    _reset_gate_state()
    settings_map = {"master_users": ["shivang"], "master_gate_strict": True}
    monkeypatch.setattr(_s, "get",
                        lambda k, d=None: settings_map.get(k, d))

    class _NoRec:
        def is_available(self): return False
        def identify_faces(self, _): return []
    monkeypatch.setattr("core.face_recognition.get_recognizer", lambda: _NoRec())

    assert face_gate.is_master_present(object()) is True


# ── master_users skill helpers ────────────────────────────────────


def test_load_save_masters(monkeypatch):
    from core import settings as _s
    from skills import master_users as mu
    saved = {}
    monkeypatch.setattr(_s, "set_", lambda k, v: saved.update({k: v}))
    monkeypatch.setattr(_s, "get",
                        lambda k, d=None: saved.get(k, d) if k == "master_users" else d)
    mu._save_masters(["Shivang", "Sara", "shivang", ""])  # dedup + lowercase
    assert saved["master_users"] == ["sara", "shivang"]


def test_remove_master_when_absent(monkeypatch):
    from skills.master_users import remove_master
    from core import settings as _s
    monkeypatch.setattr(_s, "get",
                        lambda k, d=None: [] if k == "master_users" else d)
    out = remove_master({"raw_text": "remove master ghost"})
    assert "tha hi nahi" in out.lower() or "not" in out.lower()


def test_list_masters_when_empty(monkeypatch):
    from skills.master_users import list_masters
    from core import settings as _s
    monkeypatch.setattr(_s, "get",
                        lambda k, d=None: [] if k == "master_users" else d)
    out = list_masters({})
    assert "disabled" in out.lower() or "koi master" in out.lower()


# ── auto_label engine ────────────────────────────────────────────


def test_auto_label_start_skipped_when_detector_unavailable(monkeypatch):
    """If ObjectDetector reports unavailable AND subscribe fails, start
    should still attempt — but we just want to ensure NO crash."""
    from core import auto_label
    eng = auto_label.get_auto_label_engine()
    if eng.is_enabled():
        eng.stop()
    # Don't actually start (would touch the camera). Just verify the API
    # surface is well-shaped.
    assert not eng.is_enabled()
    assert hasattr(eng, "start")
    assert hasattr(eng, "stop")


def test_auto_label_throttle(monkeypatch):
    """Same label repeated within cool-down should NOT fire twice."""
    from core import auto_label

    eng = auto_label.get_auto_label_engine()
    eng._last_seen.clear()
    seen: list[str] = []
    fired: list[tuple] = []

    def _listener(label, score, bbox):
        fired.append((label, score, bbox))

    # Clear existing listeners + attach ours.
    with eng._lock:
        eng._listeners.clear()
        eng._listeners.append(_listener)

    # Fake a "phone" detection that exceeds area + confidence thresholds.
    class _Det:
        def __init__(self, label, score, area):
            self.label = label
            self.score = score
            self._area = area
            self.bbox = (0, 0, int(area ** 0.5), int(area ** 0.5))
        def area(self): return self._area

    class _Frame:
        shape = (480, 640, 3)

    class _Detector:
        def is_available(self): return True
        def detect(self, frame):
            return [_Det("cell phone", 0.9, int(480 * 640 * 0.2))]

    eng._detector = _Detector()
    eng._frame_count = auto_label._DETECT_EVERY_N_FRAMES - 1  # next frame fires
    # First fire:
    eng._on_frame(_Frame())
    assert len(fired) == 1
    # Immediately again inside cooldown → no second fire.
    eng._frame_count = auto_label._DETECT_EVERY_N_FRAMES * 2 - 1
    eng._on_frame(_Frame())
    assert len(fired) == 1, "throttle should suppress same-label refire"


# ── gesture revamp asserts ────────────────────────────────────────


def test_swipe_thresholds_were_revamped():
    """The revamp raised swipe delta from 0.18 → 0.22 and added a velocity
    gate. Read the gesture_engine source to confirm."""
    import inspect
    from core.gesture_engine import GestureEngine
    src = inspect.getsource(GestureEngine._maybe_emit_swipe)
    assert "0.22" in src
    assert "VELOCITY_THRESH" in src or "velocity" in src.lower()


def test_lock_sequence_timeout_was_relaxed():
    """4 seconds was bumped from 3 — verify the constant."""
    from core import gesture_engine as ge
    assert ge._LOCK_SEQ_TIMEOUT_S >= 4.0


def test_sideways_palm_hold_was_revamped():
    from core import gesture_engine as ge
    assert ge._SIDE_PALM_HOLD_S >= 0.30
    assert ge._SIDE_PALM_SWIPE_THRESH >= 0.12
