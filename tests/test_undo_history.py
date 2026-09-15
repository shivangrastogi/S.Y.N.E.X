"""Tests for the undo-history accessor + skill."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import core.action_history as ah
from core.action_history import ActionHistory


# ── labels() accessor ───────────────────────────────────────────────────


def test_labels_newest_first():
    h = ActionHistory()
    h.record("first", lambda: "x")
    h.record("second", lambda: "x")
    h.record("third", lambda: "x")
    assert h.labels() == ["third", "second", "first"]


def test_labels_empty():
    assert ActionHistory().labels() == []


def test_labels_reflects_undo_pop():
    h = ActionHistory()
    h.record("a", lambda: "x")
    h.record("b", lambda: "x")
    h.undo_last()
    assert h.labels() == ["a"]


# ── skill ───────────────────────────────────────────────────────────────


def test_skill_empty():
    ah.clear()
    from skills.undo_history_skill import undo_history
    assert "kuch undo karne ko nahi" in undo_history({}).lower()


def test_skill_single():
    ah.clear()
    ah.record("clipboard set to 'hi'", lambda: "x")
    from skills.undo_history_skill import undo_history
    out = undo_history({})
    assert "clipboard set to 'hi'" in out


def test_skill_multiple_lists_newest_first():
    ah.clear()
    ah.record("volume → 50%", lambda: "x")
    ah.record("brightness → 70%", lambda: "x")
    from skills.undo_history_skill import undo_history
    out = undo_history({})
    # newest first → brightness appears before volume
    assert out.index("brightness") < out.index("volume")
    assert "2 cheezein" in out


def test_skill_caps_at_five():
    ah.clear()
    for i in range(8):
        ah.record(f"action {i}", lambda: "x")
    from skills.undo_history_skill import undo_history
    out = undo_history({})
    assert "+3 aur" in out                     # 8 total, 5 shown, +3 more


def test_skill_registered():
    from core.skill_registry import discover_skills, get_skill
    discover_skills("skills")
    assert get_skill("undo_history") is not None
