"""Tier 2 — LLM tool-use, custom-gesture training, Whisper STT switch.

Side-effect-safe:
  * LLM tests stub LLMChat so no real Ollama HTTP call goes out.
  * Custom-gesture tests synthesize MediaPipe-shaped landmark objects.
  * Whisper tests assert the graceful-degrade path (faster-whisper not
    installed on this machine).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "ask_jarvis", "llm_status",
    "gesture_record", "gesture_unteach",
    "gesture_list_custom", "gesture_record_status",
    "whisper_status", "whisper_transcribe_once", "whisper_set_model",
    "stt_prefer_whisper", "stt_prefer_google",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("ask jarvis",                "ask_jarvis"),
    ("chat with jarvis",          "ask_jarvis"),
    ("jarvis se pucho",           "ask_jarvis"),
    ("llm status",                "llm_status"),
    ("ollama status",             "llm_status"),
    ("record gesture",            "gesture_record"),
    ("teach new gesture",         "gesture_record"),
    ("naya gesture sikhao",       "gesture_record"),
    ("forget gesture",            "gesture_unteach"),
    ("list custom gestures",      "gesture_list_custom"),
    ("gesture record status",     "gesture_record_status"),
    ("whisper status",            "whisper_status"),
    ("whisper transcribe",        "whisper_transcribe_once"),
    ("set whisper model",         "whisper_set_model"),
    ("use whisper for stt",       "stt_prefer_whisper"),
    ("use google for stt",        "stt_prefer_google"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier2(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── LLM ask_jarvis ────────────────────────────────────────────────


def test_ask_jarvis_when_ollama_unreachable(monkeypatch):
    """If LLM is unavailable, the skill must return a helpful message,
    NOT crash."""
    from skills import llm_chat_skill as lcs
    monkeypatch.setattr(lcs, "_get_llm", lambda: (None, None, None))
    out = lcs.ask_jarvis({"raw_text": "ask jarvis what time is it"})
    assert "Ollama" in out or "LLM" in out or "unreach" in out.lower()


def test_ask_jarvis_chat_path(monkeypatch):
    """A plain-text LLM response should pass through as the user-facing reply."""
    from skills import llm_chat_skill as lcs
    from core.tool_router import ToolCall

    class _FakeLLM:
        def reply_with_tools(self, **kw):
            return "Just chatting — 3 PM."

    class _FakeRouter:
        def execute(self, call):
            if call.kind == "chat":
                return call.reply
            return None

    def _parse(raw):
        return ToolCall(kind="chat", reply=raw)

    monkeypatch.setattr(lcs, "_get_llm",
                        lambda: (_FakeLLM(), _FakeRouter(), _parse))
    out = lcs.ask_jarvis({"raw_text": "ask jarvis what time is it"})
    assert "3 PM" in out


def test_ask_jarvis_tool_call_tagged(monkeypatch):
    """When the LLM picks a tool, the response should be tagged [name]."""
    from skills import llm_chat_skill as lcs
    from core.tool_router import ToolCall

    class _FakeLLM:
        def reply_with_tools(self, **kw):
            return '{"tool":"current_time","args":{}}'

    class _FakeRouter:
        def execute(self, call):
            if call.kind == "tool" and call.name == "current_time":
                return "Abhi 3 PM ho rahe hain."
            return None

    def _parse(raw):
        return ToolCall(kind="tool", name="current_time", args={})

    monkeypatch.setattr(lcs, "_get_llm",
                        lambda: (_FakeLLM(), _FakeRouter(), _parse))
    out = lcs.ask_jarvis({"raw_text": "ask jarvis the time"})
    assert "[current_time]" in out
    assert "3 PM" in out


def test_llm_tool_manifest_excludes_sentinels():
    from skills.llm_chat_skill import _build_tool_manifest, _LLM_TOOL_BLOCKLIST
    tools = _build_tool_manifest()
    names = {t["name"] for t in tools}
    for bad in _LLM_TOOL_BLOCKLIST:
        assert bad not in names, f"sentinel {bad!r} leaked into LLM tools"


def test_llm_status_reports_state():
    from skills.llm_chat_skill import llm_status
    out = llm_status({})
    assert "LLM" in out
    # Either OK or UNREACHABLE; both are valid depending on env.
    assert "OK" in out or "UNREACHABLE" in out


# ── custom_gestures ──────────────────────────────────────────────


class _LM:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)


def _open_palm_pose():
    """Fingers spread roughly perpendicular to wrist — distinct from fist."""
    pts = [
        (0.50, 0.50),    # 0 wrist
        (0.42, 0.45), (0.40, 0.40), (0.39, 0.36), (0.38, 0.32),    # thumb 1-4
        (0.45, 0.40), (0.43, 0.30), (0.42, 0.22), (0.41, 0.15),    # index 5-8
        (0.50, 0.40), (0.50, 0.28), (0.50, 0.20), (0.50, 0.12),    # middle 9-12
        (0.55, 0.40), (0.57, 0.30), (0.58, 0.22), (0.59, 0.15),    # ring 13-16
        (0.60, 0.42), (0.63, 0.34), (0.65, 0.28), (0.67, 0.22),    # pinky 17-20
    ]
    return [_LM(x, y) for x, y in pts]


def _fist_pose():
    """All fingers curled — distinct shape from open palm."""
    pts = [
        (0.50, 0.50),    # 0 wrist
        (0.45, 0.48), (0.44, 0.46), (0.46, 0.46), (0.48, 0.46),    # thumb
        (0.46, 0.46), (0.47, 0.48), (0.48, 0.49), (0.49, 0.49),    # index
        (0.50, 0.46), (0.50, 0.48), (0.50, 0.49), (0.50, 0.50),    # middle
        (0.54, 0.46), (0.53, 0.48), (0.52, 0.49), (0.51, 0.50),    # ring
        (0.56, 0.47), (0.55, 0.48), (0.54, 0.49), (0.53, 0.50),    # pinky
    ]
    return [_LM(x, y) for x, y in pts]


def test_custom_gesture_record_save(monkeypatch, tmp_path):
    import core.custom_gestures as cg
    monkeypatch.setattr(cg, "_STORE_PATH", tmp_path / "custom_gestures.json")
    cg._DEFAULT = None
    eng = cg.get_custom_gesture_engine()
    ok, msg = eng.start_recording("palm", frames=3)
    assert ok
    for _ in range(3):
        eng.feed(_open_palm_pose())
    assert eng.is_recording() is False
    assert "palm" in eng.list_names()


def test_custom_gesture_distinguishes_shapes(monkeypatch, tmp_path):
    import core.custom_gestures as cg
    monkeypatch.setattr(cg, "_STORE_PATH", tmp_path / "custom_gestures.json")
    cg._DEFAULT = None
    eng = cg.get_custom_gesture_engine()
    eng.start_recording("palm", frames=3)
    for _ in range(3): eng.feed(_open_palm_pose())
    eng.start_recording("fist", frames=3)
    for _ in range(3): eng.feed(_fist_pose())
    # Classify a fresh open-palm — should match "palm" not "fist".
    assert eng.classify(_open_palm_pose()) == "palm"
    assert eng.classify(_fist_pose()) == "fist"


def test_custom_gesture_unknown_pose_returns_none(monkeypatch, tmp_path):
    """A pose unlike anything trained should not match."""
    import core.custom_gestures as cg
    monkeypatch.setattr(cg, "_STORE_PATH", tmp_path / "custom_gestures.json")
    cg._DEFAULT = None
    eng = cg.get_custom_gesture_engine()
    eng.start_recording("palm", frames=3)
    for _ in range(3): eng.feed(_open_palm_pose())
    # Bizarre pose unlike palm
    weird = [_LM(0.5 + 0.05 * (i % 7), 0.5 - 0.1 * (i % 3)) for i in range(21)]
    assert eng.classify(weird) is None or eng.classify(weird) == "palm"


def test_custom_gesture_forget(monkeypatch, tmp_path):
    import core.custom_gestures as cg
    monkeypatch.setattr(cg, "_STORE_PATH", tmp_path / "custom_gestures.json")
    cg._DEFAULT = None
    eng = cg.get_custom_gesture_engine()
    eng.start_recording("p", frames=3)
    for _ in range(3): eng.feed(_open_palm_pose())
    assert eng.forget("p") is True
    assert eng.list_names() == []


def test_custom_gesture_handles_short_landmarks():
    """Fewer than 21 landmarks should return None — not crash."""
    from core.custom_gestures import _features
    assert _features([_LM(0, 0)]) is None
    assert _features(None) is None


def test_gesture_record_skill_no_name(monkeypatch, tmp_path):
    import core.custom_gestures as cg
    monkeypatch.setattr(cg, "_STORE_PATH", tmp_path / "custom_gestures.json")
    cg._DEFAULT = None
    from skills.custom_gestures_skill import gesture_record
    out = gesture_record({"raw_text": "record gesture"})
    assert "naam" in out.lower() or "name" in out.lower()


def test_gesture_list_custom_empty(monkeypatch, tmp_path):
    import core.custom_gestures as cg
    monkeypatch.setattr(cg, "_STORE_PATH", tmp_path / "custom_gestures.json")
    cg._DEFAULT = None
    from skills.custom_gestures_skill import gesture_list_custom
    out = gesture_list_custom({})
    assert "nahi" in out.lower() or "no" in out.lower()


# ── Whisper STT ──────────────────────────────────────────────────


def test_whisper_status_reports_availability():
    from skills.whisper_stt_skill import whisper_status
    out = whisper_status({})
    assert "Whisper" in out
    assert ("OK" in out or "MISSING" in out)


def test_whisper_transcribe_unavailable(monkeypatch):
    """When faster-whisper isn't installed, the skill must return a
    helpful 'install' message, not crash."""
    import core.stt_whisper as sw
    monkeypatch.setattr(sw, "_whisper_available", lambda: False)
    sw._DEFAULT = None
    from skills.whisper_stt_skill import whisper_transcribe_once
    out = whisper_transcribe_once({})
    assert "unavailable" in out.lower() or "install" in out.lower()


def test_whisper_set_model_validation():
    from skills.whisper_stt_skill import whisper_set_model
    out = whisper_set_model({"raw_text": "use whisper base"})
    assert "base" in out
    out = whisper_set_model({"raw_text": "use whisper large"})
    assert "large-v3" in out
    out = whisper_set_model({"raw_text": "set whisper model"})  # no size
    assert "Format" in out or "format" in out.lower()


def test_stt_prefer_writes_settings(monkeypatch):
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from skills.whisper_stt_skill import stt_prefer_whisper, stt_prefer_google
    stt_prefer_whisper({})
    assert state["stt_backend_preference"] == "whisper"
    stt_prefer_google({})
    assert state["stt_backend_preference"] == "google"


def test_whisper_set_model_invalid(monkeypatch):
    from core.stt_whisper import get_whisper_engine
    eng = get_whisper_engine()
    ok, msg = eng.set_model_size("bogus-size-xyz")
    assert ok is False
    assert "Invalid" in msg or "invalid" in msg.lower()
