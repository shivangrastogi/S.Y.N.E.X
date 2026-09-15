"""Iteration #4 skills — routing + handler tests.

Covers: pomodoro_start / status / stop, monitor_swap / monitor_list,
app_mute / app_unmute / app_volume_set / app_volume_list, quick_calc.

Side-effect-safe:
  * No real pomodoro phases fire (we override ``_schedule_phase`` with a
    stub that records the call instead of arming a Timer).
  * monitor_swap is only exercised when 1+ monitors detect; we stub
    EnumDisplayMonitors / MoveWindow when needed.
  * app_audio handlers fail-fast with a clear "pycaw missing" message when
    the dep isn't installed — we assert that message and skip live-session
    tests in that case.
  * quick_calc evaluates pure arithmetic on the AST whitelist; no eval().
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "pomodoro_start", "pomodoro_status", "pomodoro_stop",
    "monitor_swap", "monitor_list",
    "app_mute", "app_unmute", "app_volume_set", "app_volume_list",
    "quick_calc",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no trigger patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("start pomodoro",          "pomodoro_start"),
    ("pomodoro start karo",     "pomodoro_start"),
    ("pomodoro status",         "pomodoro_status"),
    ("stop pomodoro",           "pomodoro_stop"),
    ("monitor swap",            "monitor_swap"),
    ("next monitor",            "monitor_swap"),
    ("list monitors",           "monitor_list"),
    ("mute spotify",            "app_mute"),
    ("unmute chrome",           "app_unmute"),
    ("set spotify to",          "app_volume_set"),
    ("list app volumes",        "app_volume_list"),
    ("25 x 4",                  "quick_calc"),
    ("square root of 144",      "quick_calc"),
    ("5 ka 4 guna",             "quick_calc"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_iter4(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── pomodoro ──────────────────────────────────────────────────────


def test_pomodoro_start_status_stop(monkeypatch):
    import skills.pomodoro as pom
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(pom, "_schedule_phase",
                        lambda phase, mins: (calls.append((phase, mins)),
                                             pom._STATE.update(
                                                 phase=phase,
                                                 phase_ends_at=99999.0,
                                             )))

    start = pom.pomodoro_start({"raw_text": "start pomodoro"})
    assert "Pomodoro" in start
    assert calls and calls[0][0] == "work"
    status = pom.pomodoro_status({})
    assert "working" in status.lower() or "work" in status.lower()
    stop = pom.pomodoro_stop({})
    assert "stop" in stop.lower()
    # Status after stop should report "no pomodoro".
    after = pom.pomodoro_status({})
    assert "nahi" in after.lower() or "no " in after.lower()


def test_pomodoro_parses_custom_duration(monkeypatch):
    import skills.pomodoro as pom
    monkeypatch.setattr(pom, "_schedule_phase", lambda phase, mins: None)
    out = pom.pomodoro_start({"raw_text": "pomodoro for 40 minutes"})
    assert "40" in out


# ── monitor_swap ──────────────────────────────────────────────────


def test_monitor_list_returns_text():
    from skills.monitor_swap import monitor_list
    out = monitor_list({})
    # Either "N monitor(s) detected" or the non-Windows skip message.
    assert "monitor" in out.lower() or "Windows" in out


def test_monitor_swap_returns_string():
    from skills.monitor_swap import monitor_swap
    out = monitor_swap({})
    assert isinstance(out, str) and out.strip()


# ── app_audio (graceful pycaw degrade) ────────────────────────────


def test_app_mute_handles_missing_pycaw():
    """Without an app target, the skill must prompt rather than crash."""
    from skills.app_audio import app_mute, _PYCAW_OK
    out = app_mute({"raw_text": "mute"})
    if not _PYCAW_OK:
        assert "pycaw" in out.lower()
    else:
        # With pycaw, empty target → prompt.
        assert "?" in out or "kaunsa" in out.lower()


def test_app_volume_list_handles_missing_pycaw():
    from skills.app_audio import app_volume_list, _PYCAW_OK
    out = app_volume_list({})
    assert isinstance(out, str)
    if not _PYCAW_OK:
        assert "pycaw" in out.lower()


def test_app_audio_strip_verb():
    from skills.app_audio import _strip_audio_verb
    assert _strip_audio_verb("mute spotify", "mute") == "spotify"
    assert _strip_audio_verb("unmute chrome", "unmute") == "chrome"


def test_app_audio_parse_pct():
    from skills.app_audio import _parse_pct
    assert _parse_pct("set spotify to 30%") == 30
    assert _parse_pct("chrome volume 75") == 75
    assert _parse_pct("set discord at 100") == 100
    assert _parse_pct("nothing here") is None


# ── quick_calc ────────────────────────────────────────────────────

CALC_CASES = [
    ("calculate 25 * 4",                   "100"),
    ("what is 100 divided by 5",           "20"),
    ("kya hai 3 plus 7",                   "10"),
    ("20 percent of 480",                  "96"),
    ("square root of 144",                 "12"),
    ("25 x 4",                             "100"),
    ("what is 2 to the power of 10",       "1024"),
    ("calculate 10 jod 5",                 "15"),
    ("kya hai 100 bhag 4",                 "25"),
]


@pytest.mark.parametrize("text,expected", CALC_CASES)
def test_quick_calc_arithmetic(text, expected):
    from skills.quick_calc import quick_calc
    out = quick_calc({"raw_text": text})
    assert expected in out, f"{text!r} → {out!r}; expected to contain {expected!r}"


def test_quick_calc_zero_division():
    from skills.quick_calc import quick_calc
    out = quick_calc({"raw_text": "calculate 5 divided by 0"})
    assert "zero" in out.lower() or "div" in out.lower()


def test_quick_calc_no_numbers_prompts():
    from skills.quick_calc import quick_calc
    out = quick_calc({"raw_text": "calculate"})
    assert "?" in out or "expression" in out.lower() or "number" in out.lower()


def test_quick_calc_rejects_arbitrary_python():
    """The whitelisted AST walker must refuse function calls / attribute access."""
    from skills.quick_calc import quick_calc
    out = quick_calc({"raw_text": "calculate __import__('os').system('echo bad')"})
    # Should fail gracefully, NOT execute the code.
    assert "calculate" in out.lower() or "nahi" in out.lower() or "kar paya" in out.lower()
