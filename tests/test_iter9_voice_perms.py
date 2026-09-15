"""Iter#9 — conversation recap, log digest, master permissions, voice memo.

Side-effect-safe:
  * recap uses a synthetic ConversationHistory.
  * log digest tests use tmp_path log file.
  * voice-memo tests never open the mic — _record_loop is stubbed.
  * play tests redirect pygame.mixer to a counting stub.
"""
from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "conversation_recap", "conversation_clear",
    "log_digest_today",
    "master_allow_all", "master_kid_mode",
    "master_grant", "master_block",
    "master_permissions_show", "master_permissions_clear",
    "record_voice_memo", "stop_voice_memo",
    "play_last_memo", "play_memo",
    "list_voice_memos", "delete_last_memo",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("recap",                      "conversation_recap"),
    ("kya baat ki thi",            "conversation_recap"),
    ("forget conversation",        "conversation_clear"),
    ("summarize logs",             "log_digest_today"),
    ("aaj ke logs batao",          "log_digest_today"),
    ("allow all gestures for",     "master_allow_all"),
    ("kid mode for",               "master_kid_mode"),
    ("grant peace to shivang",     "master_grant"),
    ("block peace from kid",       "master_block"),
    ("master permissions",         "master_permissions_show"),
    ("clear master permissions",   "master_permissions_clear"),
    ("record voice memo",          "record_voice_memo"),
    ("stop voice memo",            "stop_voice_memo"),
    ("play last memo",             "play_last_memo"),
    ("list voice memos",           "list_voice_memos"),
    ("delete last memo",           "delete_last_memo"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_iter9(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── conversation_recap ────────────────────────────────────────────


def test_recap_no_active_engine():
    from core.conversation import set_active
    set_active(None)  # type: ignore[arg-type]
    from skills.conversation_recap import conversation_recap
    out = conversation_recap({})
    assert "nahi" in out.lower() or "no " in out.lower()


def test_recap_returns_recent_turns():
    from core.conversation import ConversationHistory, set_active
    from skills.conversation_recap import conversation_recap
    h = ConversationHistory(max_turns=4)
    h.add_user("open chrome"); h.add_assistant("Opening Chrome.")
    h.add_user("what time"); h.add_assistant("3 PM.")
    h.add_user("thanks"); h.add_assistant("Anytime!")
    set_active(h)
    out = conversation_recap({"raw_text": "recap last 2"})
    assert "thanks" in out and "Anytime" in out
    assert "open chrome" not in out or out.count("open chrome") == 0


def test_recap_count_extraction():
    from skills.conversation_recap import _extract_count
    assert _extract_count("recap last 3") == 3
    assert _extract_count("show last 5 turns") == 5
    assert _extract_count("recap") == 4   # default
    assert _extract_count("recap last 999") == 20   # capped


# ── log_digest ────────────────────────────────────────────────────


def test_log_digest_no_file(monkeypatch, tmp_path):
    import skills.log_digest as ld
    monkeypatch.setattr(ld, "_LOG_PATH", tmp_path / "nope.log")
    out = ld.log_digest_today({})
    assert "nahi mila" in out.lower() or "no" in out.lower()


def test_log_digest_classifies(monkeypatch, tmp_path):
    import skills.log_digest as ld
    from datetime import date
    today = date.today().isoformat()
    sample = "\n".join([
        f"{today}T08:00:00 INFO  aeris.event :: {{\"event\": \"boot_start\"}}",
        f"{today}T08:01:00 INFO  core.gestures] :: peace fired",
        f"{today}T08:02:00 ERROR core.brain :: something broke",
        f"{today}T08:03:00 INFO  core.face_recognition :: face seen",
        "2020-01-01T00:00:00 INFO  old :: ignored",  # not today
    ])
    p = tmp_path / "today.log"
    p.write_text(sample, encoding="utf-8")
    monkeypatch.setattr(ld, "_LOG_PATH", p)
    out = ld.log_digest_today({})
    assert "4 entries" in out, out
    assert "boots" in out
    assert "errors" in out


# ── master_permissions ───────────────────────────────────────────


def test_kid_mode_sets_safe_list(monkeypatch):
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from skills.master_permissions import master_kid_mode, _KID_SAFE_DEFAULT
    out = master_kid_mode({"raw_text": "kid mode for kid"})
    perms = state["master_permissions"]
    assert "kid" in perms
    # Must be the canonical safe list, no admin gestures.
    assert "palm_fist_lock" not in perms["kid"]
    assert "double_pinch" in perms["kid"]
    assert "kid mode" in out.lower() or "double_pinch" in out


def test_allow_all_grants_full(monkeypatch):
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from skills.master_permissions import master_allow_all
    master_allow_all({"raw_text": "allow all gestures for shivang"})
    assert state["master_permissions"]["shivang"] == ["all"]


def test_block_specific_gesture(monkeypatch):
    state = {"master_permissions": {"kid": ["double_pinch", "peace"]}}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from skills.master_permissions import master_block
    out = master_block({"raw_text": "block peace from kid"})
    assert "peace" not in state["master_permissions"]["kid"]
    assert "double_pinch" in state["master_permissions"]["kid"]
    assert "blocked peace" in out.lower() or "peace" in out.lower()


def test_grant_specific_gesture(monkeypatch):
    state = {"master_permissions": {"kid": ["double_pinch"]}}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from skills.master_permissions import master_grant
    master_grant({"raw_text": "grant peace to kid"})
    assert "peace" in state["master_permissions"]["kid"]


# ── face_gate.gesture_allowed_for ────────────────────────────────


def test_gesture_allowed_for_no_perms(monkeypatch):
    """Empty perms map → backward-compatible: allow everything."""
    from core import face_gate
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: {} if k == "master_permissions" else d)
    assert face_gate.gesture_allowed_for(["shivang"], "palm_fist_lock") is True


def test_gesture_allowed_for_kid_blocked(monkeypatch):
    from core import face_gate
    perms = {"kid": ["double_pinch", "swipe_left"]}
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: perms if k == "master_permissions" else d)
    assert face_gate.gesture_allowed_for(["kid"], "palm_fist_lock") is False
    assert face_gate.gesture_allowed_for(["kid"], "double_pinch") is True


def test_gesture_allowed_for_all(monkeypatch):
    from core import face_gate
    perms = {"shivang": ["all"]}
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: perms if k == "master_permissions" else d)
    assert face_gate.gesture_allowed_for(["shivang"], "palm_fist_lock") is True


def test_gesture_allowed_for_multi_master(monkeypatch):
    """When two masters are in frame, the more-permissive one wins."""
    from core import face_gate
    perms = {"kid": ["double_pinch"], "shivang": ["all"]}
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: perms if k == "master_permissions" else d)
    assert face_gate.gesture_allowed_for(["kid", "shivang"], "palm_fist_lock") is True


# ── voice_memo (no mic, no playback) ─────────────────────────────


def test_voice_memo_record_starts_thread(monkeypatch):
    import skills.voice_memo as vm
    # Replace _record_loop with a no-op so no mic is opened.
    monkeypatch.setattr(vm, "_record_loop",
                        lambda fn, dur, evt: None)
    monkeypatch.setattr(vm, "_MEMO_DIR", vm._MEMO_DIR)
    # Reset state
    with vm._REC_LOCK:
        vm._REC_STATE["active"] = False
    out = vm.record_voice_memo({"raw_text": "record 5 second memo"})
    assert "Recording" in out and "5s" in out
    # Wait for the stubbed thread to finish, then state should be inactive.
    th = vm._REC_STATE.get("thread")
    if th:
        th.join(timeout=2.0)


def test_voice_memo_double_start_blocks(monkeypatch):
    import skills.voice_memo as vm
    # Hold the active flag manually
    with vm._REC_LOCK:
        vm._REC_STATE["active"] = True
        vm._REC_STATE["thread"] = None
    out = vm.record_voice_memo({"raw_text": "record memo"})
    assert "Already" in out or "already" in out
    with vm._REC_LOCK:
        vm._REC_STATE["active"] = False


def test_voice_memo_stop_when_idle():
    import skills.voice_memo as vm
    with vm._REC_LOCK:
        vm._REC_STATE["active"] = False
    out = vm.stop_voice_memo({})
    assert "nahi" in out.lower() or "no " in out.lower()


def test_voice_memo_play_when_empty(monkeypatch, tmp_path):
    import skills.voice_memo as vm
    monkeypatch.setattr(vm, "_MEMO_DIR", tmp_path)
    out = vm.play_last_memo({})
    assert "nahi" in out.lower() or "no " in out.lower()


def test_voice_memo_list_when_empty(monkeypatch, tmp_path):
    import skills.voice_memo as vm
    monkeypatch.setattr(vm, "_MEMO_DIR", tmp_path)
    out = vm.list_voice_memos({})
    assert "nahi" in out.lower() or "no " in out.lower()


def test_voice_memo_duration_parser():
    from skills.voice_memo import _parse_duration
    assert _parse_duration("record 5 second memo") == 5
    assert _parse_duration("record memo for 1 minute") == 60
    assert _parse_duration("record memo") == 10   # default
    assert _parse_duration("record 500 second memo") == 120  # capped
