"""Iteration #1 skills — routing + handler tests.

Covers: find_file, recent_files, run_macro, list_macros, reload_macros,
voice_slower/faster/louder/softer/status/reset.

Side-effect-free: macros that would launch external apps are NOT actually
executed here; we test the resolver / parser surfaces. Voice tuning tests
clean up after themselves so live settings don't drift.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


# ── registration ──────────────────────────────────────────────────

NEW_SKILLS = [
    "find_file", "recent_files",
    "run_macro", "list_macros", "reload_macros",
    "voice_slower", "voice_faster",
    "voice_louder", "voice_softer",
    "voice_status", "voice_reset",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── brain routing for the iteration #1 skills ─────────────────────

ROUTING_CASES = [
    ("recent files",            "recent_files"),
    ("latest files",            "recent_files"),
    ("list macros",             "list_macros"),
    ("macros dikhao",           "list_macros"),
    ("reload macros",           "reload_macros"),
    ("speak slower",            "voice_slower"),
    ("dheere bolo",             "voice_slower"),
    ("speak faster",            "voice_faster"),
    ("voice loud karo",         "voice_louder"),
    ("voice low karo",          "voice_softer"),
    ("voice status",            "voice_status"),
    ("reset voice",             "voice_reset"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_iter1(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── find_file resolver ───────────────────────────────────────────

def test_find_file_strip_verb_recovers_query():
    from skills.file_finder import _strip_open_verb
    assert _strip_open_verb("find file resume") == "resume"
    assert _strip_open_verb("open my resume") == "resume"
    assert _strip_open_verb("find document quarterly report") == "quarterly report"
    assert _strip_open_verb("where is the contract") == "contract"


def test_find_file_score_basic():
    from skills.file_finder import _score
    assert _score("resume_2024.pdf", "resume") == 1.0
    assert _score("q1_report.xlsx", "q1") == 1.0
    assert _score("totally_unrelated.txt", "resume") == 0.0


# ── macros engine ────────────────────────────────────────────────

def test_macros_load():
    from skills.macros import _load_macros
    macros = _load_macros(force=True)
    assert "morning_routine" in macros
    assert "focus_deep" in macros
    assert "end_of_day" in macros
    assert "_comment" not in macros


def test_macro_name_resolver():
    from skills.macros import _resolve_macro_name
    assert _resolve_macro_name("morning routine") == "morning_routine"
    assert _resolve_macro_name("morning_routine") == "morning_routine"
    assert _resolve_macro_name("focus deep") == "focus_deep"
    assert _resolve_macro_name("end of day") == "end_of_day"
    assert _resolve_macro_name("nope") is None


def test_macro_strip_verb():
    from skills.macros import _strip_run_verb
    assert _strip_run_verb("run macro morning routine") == "morning routine"
    assert _strip_run_verb("execute macro focus deep") == "focus deep"
    assert _strip_run_verb("morning routine") == "morning routine"


def test_list_macros_handler_returns_nonempty():
    from skills.macros import list_macros
    out = list_macros({})
    assert "morning_routine" in out
    assert "focus_deep" in out


# ── voice tuning round-trip (cleans up settings) ──────────────────

def test_voice_tuning_round_trip(monkeypatch):
    """Slow + fast then reset should leave rate exactly where it started."""
    from core import settings as _settings
    from skills.voice_tuning import voice_slower, voice_faster, voice_status, voice_reset
    original_rate = _settings.get("speech_rate") or 175
    original_vol  = _settings.get("voice_volume", 1.0) or 1.0
    try:
        voice_slower({})
        voice_faster({})
        # After equal slow+fast, rate should be back at original
        assert int(_settings.get("speech_rate")) == int(original_rate)
        out = voice_status({})
        assert "wpm" in out and "volume" in out
    finally:
        # Reset so the live settings.json doesn't carry test artefacts.
        _settings.set_("speech_rate", int(original_rate))
        _settings.set_("voice_volume", float(original_vol))


def test_voice_louder_clamps_at_max():
    from core import settings as _settings
    from skills.voice_tuning import voice_louder
    original_vol = _settings.get("voice_volume", 1.0) or 1.0
    try:
        _settings.set_("voice_volume", 1.0)  # already max
        out = voice_louder({})
        assert "maximum" in out.lower() or "100%" in out
    finally:
        _settings.set_("voice_volume", float(original_vol))


def test_voice_softer_clamps_at_min():
    from core import settings as _settings
    from skills.voice_tuning import voice_softer
    original_vol = _settings.get("voice_volume", 1.0) or 1.0
    try:
        _settings.set_("voice_volume", 0.1)  # at minimum
        out = voice_softer({})
        assert "minimum" in out.lower() or "10%" in out
    finally:
        _settings.set_("voice_volume", float(original_vol))


# ── TTS live settings reader ──────────────────────────────────────

def test_tts_live_voice_settings_reads_store():
    from core import settings as _settings
    from core.tts import _live_voice_settings
    original_rate = _settings.get("speech_rate") or 175
    original_vol  = _settings.get("voice_volume", 1.0) or 1.0
    try:
        _settings.set_("speech_rate", 200)
        _settings.set_("voice_volume", 0.5)
        rate, vol = _live_voice_settings()
        assert rate == 200
        assert abs(vol - 0.5) < 0.01
    finally:
        _settings.set_("speech_rate", int(original_rate))
        _settings.set_("voice_volume", float(original_vol))
