"""Tests for reversible volume control via the mockable get/set seam."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import skills.volume_control as vc
import core.action_history as ah


@pytest.fixture
def fake_volume(monkeypatch):
    """An in-memory master volume the seam reads/writes — no pycaw/hardware."""
    state = {"v": 0.50}                       # start at 50 %
    monkeypatch.setattr(vc, "get_volume", lambda: state["v"])

    def _set(scalar):
        state["v"] = max(0.0, min(1.0, scalar))
        return True

    monkeypatch.setattr(vc, "set_volume", _set)
    ah.clear()
    return state


# ── absolute set ────────────────────────────────────────────────────────


def test_volume_set_changes_and_is_undoable(fake_volume):
    res = vc.volume_set({"content": "30"})
    assert "30%" in res
    assert fake_volume["v"] == pytest.approx(0.30)

    # An undo was registered restoring the prior 50 %.
    assert ah.peek_last() is not None
    msg = ah.undo_last()
    assert fake_volume["v"] == pytest.approx(0.50)
    assert "50%" in msg


def test_volume_set_bad_input(fake_volume):
    assert "batao" in vc.volume_set({"content": "loud"}).lower()
    assert ah.peek_last() is None             # nothing changed → no undo


# ── relative up / down ──────────────────────────────────────────────────


def test_volume_up_and_undo(fake_volume):
    res = vc.volume_up({})
    assert fake_volume["v"] == pytest.approx(0.60)
    assert "60%" in res
    ah.undo_last()
    assert fake_volume["v"] == pytest.approx(0.50)


def test_volume_down_and_undo(fake_volume):
    vc.volume_down({})
    assert fake_volume["v"] == pytest.approx(0.40)
    ah.undo_last()
    assert fake_volume["v"] == pytest.approx(0.50)


def test_volume_clamped_at_bounds(fake_volume):
    fake_volume["v"] = 0.95
    vc.volume_up({})
    assert fake_volume["v"] == pytest.approx(1.0)   # capped, not 1.05


# ── seam falls back gracefully when pycaw absent ────────────────────────


def test_set_fallback_when_no_endpoint(monkeypatch):
    # get_volume None (no pycaw) → volume_set takes the media-key fallback and
    # registers NO undo (we can't know the prior absolute level).
    monkeypatch.setattr(vc, "get_volume", lambda: None)
    monkeypatch.setattr(vc, "set_volume", lambda s: False)
    monkeypatch.setattr(vc, "_press_key", lambda *a, **k: None)
    ah.clear()
    res = vc.volume_set({"content": "40"})
    assert "fallback" in res.lower()
    assert ah.peek_last() is None
