"""Tests for the maps + mouse gesture engines.

Pure landmark math — no MediaPipe / OpenCV / webcam needed.
The fixtures below are 21-point hand-landmark arrays in MediaPipe's normalised
[0,1] coord space, mocked just well enough to satisfy the predicates."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core import hand_landmarks as HL
from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


# ── landmark fixtures ───────────────────────────────────────


def _zeros() -> list[tuple[float, float, float]]:
    return [(0.5, 0.5, 0.0)] * 21


def _ok_sign_lm(thumb_x=0.4, thumb_y=0.4, idx_x=0.42, idx_y=0.4) -> list:
    """OK sign — thumb tip touching index tip, middle/ring/pinky extended.
    Wrist and MCPs are anchored at the centroid of the thumb/index so the
    palm centre tracks the hand position in space."""
    lm = _zeros()
    base_x = (thumb_x + idx_x) / 2
    base_y = (thumb_y + idx_y) / 2 + 0.10  # palm sits below the pinch
    lm[4]  = (thumb_x, thumb_y, 0.0)           # thumb tip
    lm[3]  = (thumb_x + 0.05, thumb_y, 0.0)    # thumb IP
    lm[8]  = (idx_x, idx_y, 0.0)               # index tip
    lm[6]  = (idx_x, idx_y + 0.05, 0.0)        # index PIP (lower)
    lm[12] = (base_x + 0.02, base_y - 0.20, 0.0); lm[10] = (base_x + 0.02, base_y - 0.10, 0.0)
    lm[16] = (base_x + 0.06, base_y - 0.20, 0.0); lm[14] = (base_x + 0.06, base_y - 0.10, 0.0)
    lm[20] = (base_x + 0.10, base_y - 0.20, 0.0); lm[18] = (base_x + 0.10, base_y - 0.10, 0.0)
    # Anchor wrist + MCPs at the hand base.
    lm[0]  = (base_x, base_y + 0.05, 0.0)
    lm[5]  = (base_x - 0.04, base_y, 0.0)
    lm[9]  = (base_x, base_y, 0.0)
    lm[13] = (base_x + 0.04, base_y, 0.0)
    lm[17] = (base_x + 0.08, base_y, 0.0)
    return lm


def _open_palm_lm(cx=0.5, cy=0.5) -> list:
    lm = _zeros()
    # All five fingertips above their PIPs; thumb pushed left/right.
    lm[8]  = (cx - 0.10, cy - 0.20, 0); lm[6]  = (cx - 0.10, cy - 0.10, 0)
    lm[12] = (cx,        cy - 0.22, 0); lm[10] = (cx,        cy - 0.10, 0)
    lm[16] = (cx + 0.10, cy - 0.20, 0); lm[14] = (cx + 0.10, cy - 0.10, 0)
    lm[20] = (cx + 0.18, cy - 0.15, 0); lm[18] = (cx + 0.18, cy - 0.05, 0)
    lm[4]  = (cx - 0.20, cy, 0);        lm[3]  = (cx - 0.10, cy, 0)
    lm[5]  = (cx - 0.05, cy, 0)
    lm[0]  = (cx, cy + 0.05, 0); lm[9]  = (cx, cy, 0)
    lm[13] = (cx + 0.05, cy, 0); lm[17] = (cx + 0.10, cy, 0)
    return lm


def _peace_lm() -> list:
    """Index + middle extended and SPREAD; ring + pinky folded."""
    lm = _zeros()
    lm[8]  = (0.45, 0.20, 0); lm[6] = (0.45, 0.40, 0)   # index ext
    lm[12] = (0.55, 0.20, 0); lm[10] = (0.55, 0.40, 0)  # middle ext
    lm[16] = (0.50, 0.50, 0); lm[14] = (0.50, 0.45, 0)  # ring folded
    lm[20] = (0.55, 0.50, 0); lm[18] = (0.55, 0.45, 0)  # pinky folded
    return lm


def _mouse_pose_lm(thumb_close_to_folded=False) -> list:
    """V-cursor pose — index + middle STUCK TOGETHER, thumb out, ring/pinky
    folded. Right hand."""
    lm = _zeros()
    lm[8]  = (0.48, 0.20, 0); lm[6]  = (0.48, 0.40, 0)
    lm[12] = (0.50, 0.20, 0); lm[10] = (0.50, 0.40, 0)
    lm[16] = (0.55, 0.50, 0); lm[14] = (0.55, 0.45, 0)
    lm[20] = (0.60, 0.50, 0); lm[18] = (0.60, 0.45, 0)
    # Thumb extended (right hand: tip x < IP x).
    lm[3] = (0.45, 0.42, 0)
    if thumb_close_to_folded:
        # tip near ring/pinky tips → click trigger
        lm[4] = (0.575, 0.49, 0)
    else:
        lm[4] = (0.40, 0.42, 0)
    return lm


# ── HL predicates ───────────────────────────────────────────


def test_ok_sign_detected():
    assert HL.is_ok_sign(_ok_sign_lm()) is True


def test_ok_sign_rejects_open_palm():
    assert HL.is_ok_sign(_open_palm_lm()) is False


def test_open_palm_detected():
    assert HL.is_open_palm(_open_palm_lm()) is True


def test_open_palm_rejects_ok_sign():
    assert HL.is_open_palm(_ok_sign_lm()) is False


def test_peace_detected():
    assert HL.is_peace(_peace_lm()) is True


def test_peace_rejects_mouse_pose():
    # V-cursor has fingers stuck together; peace has them apart.
    assert HL.is_peace(_mouse_pose_lm()) is False


def test_mouse_pose_detected():
    assert HL.is_mouse_pose(_mouse_pose_lm(), "right") is True


def test_mouse_pose_rejects_peace():
    assert HL.is_mouse_pose(_peace_lm(), "right") is False


def test_thumb_touches_folded_fingers_when_close():
    lm = _mouse_pose_lm(thumb_close_to_folded=True)
    assert HL.thumb_touches_folded_fingers(lm) is True


def test_thumb_touches_folded_fingers_when_far():
    lm = _mouse_pose_lm(thumb_close_to_folded=False)
    assert HL.thumb_touches_folded_fingers(lm) is False


def test_mouse_pose_pointer_midpoint():
    lm = _mouse_pose_lm()
    px, py = HL.mouse_pose_pointer(lm)
    assert abs(px - 0.49) < 1e-6
    assert abs(py - 0.20) < 1e-6


# ── Double-tap timing ───────────────────────────────────────


def _pinched_lm(d: float = 0.02) -> list:
    """Thumb-index distance = d (in normalised units)."""
    lm = _zeros()
    lm[4] = (0.40, 0.40, 0)
    lm[8] = (0.40 + d, 0.40, 0)
    return lm


def test_double_tap_fires_on_two_fast_pinches():
    det = HL.DoubleTapDetector(window_ms=400, hold_ms=200)
    # pinch close
    assert det.observe(_pinched_lm(0.02), now_ms=0) is False
    # release
    assert det.observe(_pinched_lm(0.10), now_ms=100) is False
    # pinch close again
    assert det.observe(_pinched_lm(0.02), now_ms=150) is False
    # release → SHOULD fire
    assert det.observe(_pinched_lm(0.10), now_ms=200) is True


def test_double_tap_ignores_slow_pinches():
    det = HL.DoubleTapDetector(window_ms=400, hold_ms=200)
    det.observe(_pinched_lm(0.02), now_ms=0)
    det.observe(_pinched_lm(0.10), now_ms=100)
    det.observe(_pinched_lm(0.02), now_ms=1000)   # too late
    assert det.observe(_pinched_lm(0.10), now_ms=1100) is False


def test_double_tap_ignores_long_holds():
    det = HL.DoubleTapDetector(window_ms=400, hold_ms=150)
    det.observe(_pinched_lm(0.02), now_ms=0)
    # Long hold — release > hold_ms after close. Should NOT count as a tap.
    det.observe(_pinched_lm(0.10), now_ms=500)
    det.observe(_pinched_lm(0.02), now_ms=550)
    assert det.observe(_pinched_lm(0.10), now_ms=600) is False


# ── Voice surface: skill registration ───────────────────────


def test_new_skills_registered():
    names = set(all_skills().keys())
    assert {
        "search_maps_for",
        "maps_gestures_on", "maps_gestures_off", "maps_gesture_status",
        "mouse_gestures_on", "mouse_gestures_off", "mouse_gesture_status",
        "gesture_arm", "gesture_disarm", "gesture_arm_status",
    } <= names


# ── Maps search URL extraction ──────────────────────────────


def test_search_maps_for_extracts_place():
    from skills.maps_gesture_skill import _extract_place
    assert _extract_place("connaught place ko maps mein dikhao") == "connaught place"
    assert _extract_place("open taj mahal in maps") == "taj mahal"
    assert _extract_place("find starbucks on maps") == "starbucks"
    assert _extract_place("maps for india gate") == "india gate"
    assert _extract_place("navigate to airport") == "airport"


def test_search_maps_for_handles_blank():
    from skills.maps_gesture_skill import _extract_place
    assert _extract_place("") == ""
    assert _extract_place("   ") == ""


def test_search_maps_for_prompts_when_blank(monkeypatch):
    handler = all_skills()["search_maps_for"].handler
    out = handler({"raw_text": ""})
    assert "batao" in out.lower() or "kya" in out.lower() or "place" in out.lower()


def test_search_maps_for_opens_browser(monkeypatch):
    opened = {"url": None}
    def fake_open(url):
        opened["url"] = url
        return True
    import skills.maps_gesture_skill as mgs
    monkeypatch.setattr(mgs.webbrowser, "open", fake_open)
    out = mgs.search_maps_for({"raw_text": "connaught place ko maps mein dikhao"})
    assert opened["url"] is not None
    assert "google.com/maps/search/" in opened["url"]
    assert "connaught" in opened["url"].lower()
    assert "opened" in out.lower() or "maps" in out.lower()


# ── Engines: arm/disarm + status without camera ─────────────


def test_maps_engine_arm_disarm():
    from core.maps_gesture_engine import get_maps_gesture_engine
    eng = get_maps_gesture_engine()
    eng.set_armed(False)
    assert eng.is_armed() is False
    eng.set_armed(True)
    assert eng.is_armed() is True


def test_mouse_engine_arm_disarm():
    from core.mouse_gesture_engine import get_mouse_gesture_engine
    eng = get_mouse_gesture_engine()
    eng.set_armed(False)
    assert eng.is_armed() is False
    eng.set_armed(True)
    assert eng.is_armed() is True


def test_gesture_arm_disarm_voice_skills():
    handlers = all_skills()
    out_disarm = handlers["gesture_disarm"].handler({})
    assert "disarm" in out_disarm.lower()
    out_arm = handlers["gesture_arm"].handler({})
    assert "arm" in out_arm.lower()


def test_status_skill_runs():
    handler = all_skills()["gesture_arm_status"].handler
    out = handler({})
    assert "maps" in out.lower() and "mouse" in out.lower()


# ── End-to-end peace toggle through the maps dispatch ───────


def test_peace_toggles_armed_state_on_dispatch():
    from core.maps_gesture_engine import MapsGestureEngine
    eng = MapsGestureEngine()  # fresh, not the singleton
    eng.set_armed(True)
    hand = {"handedness": "right", "lm": _peace_lm()}
    # First peace frame should flip armed → False
    eng._dispatch([hand], now_ms=1000.0)
    assert eng.is_armed() is False
    # Cooldown blocks an immediate second flip
    eng._dispatch([hand], now_ms=1100.0)
    assert eng.is_armed() is False
    # After cooldown, flips back to True
    eng._dispatch([hand], now_ms=3000.0)
    assert eng.is_armed() is True


def test_two_hand_ok_zoom_logs_when_disarmed():
    from core.maps_gesture_engine import MapsGestureEngine
    eng = MapsGestureEngine()
    eng.set_armed(False)
    left = {"handedness": "left",  "lm": _ok_sign_lm(thumb_x=0.30, idx_x=0.32)}
    right = {"handedness": "right", "lm": _ok_sign_lm(thumb_x=0.60, idx_x=0.62)}
    eng._dispatch([left, right], now_ms=1000.0)
    # Move hands apart on next frame.
    left2 = {"handedness": "left",  "lm": _ok_sign_lm(thumb_x=0.20, idx_x=0.22)}
    right2 = {"handedness": "right", "lm": _ok_sign_lm(thumb_x=0.70, idx_x=0.72)}
    eng._dispatch([left2, right2], now_ms=1100.0)
    # Even disarmed, the counter should increment.
    s = eng.stats()
    assert s["zoom_in"] >= 1


def test_mouse_v_pose_with_thumb_tap_counts_click_when_disarmed():
    from core.mouse_gesture_engine import MouseGestureEngine
    eng = MouseGestureEngine()
    eng.set_armed(False)
    # First frame: V-pose, thumb away (open)
    hand = {"handedness": "right", "lm": _mouse_pose_lm(False)}
    eng._dispatch([hand], now_s=10.0)
    # Second frame: V-pose, thumb touches folded fingers → rising edge click
    hand2 = {"handedness": "right", "lm": _mouse_pose_lm(True)}
    eng._dispatch([hand2], now_s=10.2)
    assert eng.stats()["right_click"] >= 1
