"""Iteration #2 skills — routing + handler tests.

Covers: repeat_last, git_log, git_diff, git_pull, git_commit_quick,
clipboard_say, clipboard_stats, clipboard_open_url, weather_for_city.

Side-effect-safe: git_pull and git_commit_quick are NOT invoked here
(they'd touch the live working tree). We test the routing surface
and helper parsers.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


# ── registration ──────────────────────────────────────────────────

NEW_SKILLS = [
    "repeat_last",
    "git_log", "git_diff", "git_pull", "git_commit_quick",
    "clipboard_say", "clipboard_stats", "clipboard_open_url",
    "weather_for_city",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no trigger patterns"


# ── brain routing ─────────────────────────────────────────────────

ROUTING_CASES = [
    ("repeat",               "repeat_last"),
    ("repeat last command",  "repeat_last"),
    ("phir se",              "repeat_last"),
    ("do that again",        "repeat_last"),
    ("git log",              "git_log"),
    ("recent commits",       "git_log"),
    ("git diff",             "git_diff"),
    ("git pull",             "git_pull"),
    ("git pull karo",        "git_pull"),
    ("git commit",           "git_commit_quick"),
    ("commit changes",       "git_commit_quick"),
    ("say clipboard",        "clipboard_say"),
    ("read clipboard",       "clipboard_say"),
    ("clipboard sunao",      "clipboard_say"),
    ("clipboard size",       "clipboard_stats"),
    ("clipboard stats",      "clipboard_stats"),
    ("open clipboard url",   "clipboard_open_url"),
    ("weather in mumbai",    "weather_for_city"),
    ("delhi ka mausam",      "weather_for_city"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_iter2(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── repeat_last ────────────────────────────────────────────────────

def test_repeat_last_returns_no_history_message():
    """With no active history attached, the skill must degrade gracefully."""
    from core.conversation import set_active
    set_active(None)  # type: ignore[arg-type]
    from skills.repeat_last import repeat_last
    out = repeat_last({})
    assert "history" in out.lower() or "engine" in out.lower()


def test_repeat_last_returns_sentinel_for_last_real_command():
    """Set up a history with one real command followed by 'repeat' triggers
    — the skill must skip over the trigger phrases and return the real one."""
    from core.conversation import ConversationHistory, set_active
    h = ConversationHistory(max_turns=4)
    h.add_user("open chrome", "neutral"); h.add_assistant("Opening Chrome.")
    h.add_user("phir se", "neutral"); h.add_assistant("Replaying...")
    h.add_user("repeat", "neutral"); h.add_assistant("Replaying...")
    set_active(h)
    from skills.repeat_last import repeat_last
    out = repeat_last({})
    assert out == "[repeat:open chrome]"


def test_repeat_last_handles_only_triggers():
    """If every recent user message is itself a 'repeat' trigger, the skill
    must NOT recurse forever — bail with a helpful message."""
    from core.conversation import ConversationHistory, set_active
    h = ConversationHistory(max_turns=10)
    for _ in range(6):
        h.add_user("repeat", "neutral"); h.add_assistant("…")
    set_active(h)
    from skills.repeat_last import repeat_last
    out = repeat_last({})
    assert "repeat" in out.lower() and ("asli" in out.lower() or "real" in out.lower())


# ── git_log / git_diff smoke ──────────────────────────────────────

def test_git_log_returns_text():
    from skills.dev_tools import git_log
    out = git_log({})
    # Either "Last 10 commits:" header OR a failure string starting with
    # "git log failed"; either is acceptable. The contract is non-empty str.
    assert isinstance(out, str) and out.strip()


def test_git_diff_returns_text():
    from skills.dev_tools import git_diff
    out = git_diff({})
    assert isinstance(out, str) and out.strip()


def test_git_commit_quick_requires_message():
    """Empty raw_text → must prompt for message, not actually commit."""
    from skills.dev_tools import git_commit_quick
    out = git_commit_quick({"raw_text": "git commit"})
    assert "message" in out.lower()


# ── weather_for_city ──────────────────────────────────────────────

def test_weather_extract_city_english():
    from skills.weather_for_city import _extract_city
    assert _extract_city("weather in mumbai") == "mumbai"
    assert _extract_city("what is the weather in london") == "london"


def test_weather_extract_city_hinglish():
    from skills.weather_for_city import _extract_city
    assert _extract_city("mumbai ka mausam") == "mumbai"
    assert _extract_city("delhi ka weather") == "delhi"
    assert _extract_city("mausam batao bangalore") == "bangalore"


def test_weather_for_city_no_city_prompts():
    """When the text doesn't contain a city, the skill must prompt for one
    instead of falling through to the default location (that's weather_local's
    job)."""
    from skills.weather_for_city import weather_for_city
    out = weather_for_city({"raw_text": "weather"})
    assert "sheher" in out.lower() or "city" in out.lower()
