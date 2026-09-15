"""Tests for reversible brightness control via the mockable seam."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import skills.brightness_control as bc
import core.action_history as ah


@pytest.fixture
def fake_brightness(monkeypatch):
    state = {"b": 70}                          # start at 70 %
    monkeypatch.setattr(bc, "_get_brightness", lambda: state["b"])

    def _set(pct):
        state["b"] = max(0, min(100, int(pct)))
        return True

    monkeypatch.setattr(bc, "_set_brightness", _set)
    ah.clear()
    return state


def test_set_changes_and_is_undoable(fake_brightness):
    res = bc.brightness_set({"content": "30"})
    assert "30%" in res
    assert fake_brightness["b"] == 30
    assert ah.peek_last() is not None
    msg = ah.undo_last()
    assert fake_brightness["b"] == 70
    assert "70%" in msg


def test_bad_input_no_undo(fake_brightness):
    assert "batao" in bc.brightness_set({"content": "bright"}).lower()
    assert ah.peek_last() is None


def test_brighter_and_undo(fake_brightness):
    bc.brightness_up({})
    assert fake_brightness["b"] == 80
    ah.undo_last()
    assert fake_brightness["b"] == 70          # restored to pre-change


def test_dimmer_and_undo(fake_brightness):
    bc.brightness_down({})
    assert fake_brightness["b"] == 60
    ah.undo_last()
    assert fake_brightness["b"] == 70


def test_clamped_at_100(fake_brightness):
    fake_brightness["b"] = 95
    bc.brightness_up({})
    assert fake_brightness["b"] == 100


def test_set_failure_registers_no_undo(monkeypatch):
    monkeypatch.setattr(bc, "_get_brightness", lambda: 50)
    monkeypatch.setattr(bc, "_set_brightness", lambda p: False)
    ah.clear()
    res = bc.brightness_set({"content": "40"})
    assert "nahi ho saka" in res.lower()
    assert ah.peek_last() is None


def test_brightness_unreadable(monkeypatch):
    monkeypatch.setattr(bc, "_get_brightness", lambda: None)
    res = bc.brightness_up({})
    assert "read nahi hua" in res.lower()
