"""Tests for the undo stack (core/action_history.py + undo skill + clipboard wiring)."""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.action_history import ActionHistory


# ── core ring buffer ────────────────────────────────────────────────────


def test_record_peek_undo_lifo():
    h = ActionHistory()
    out = []
    h.record("first", lambda: out.append("undo-first") or "undid first")
    h.record("second", lambda: out.append("undo-second") or "undid second")

    assert h.peek_last().label == "second"
    assert len(h) == 2

    msg = h.undo_last()
    assert msg == "undid second"
    assert out == ["undo-second"]          # newest undone first
    assert len(h) == 1
    assert h.peek_last().label == "first"


def test_undo_empty_history():
    h = ActionHistory()
    assert "kuch nahi" in h.undo_last().lower()


def test_undo_window_blocks_stale_action():
    h = ActionHistory()
    h.record("old", lambda: "undone")
    # Backdate the entry beyond the window.
    h.peek_last().ts = time.time() - 600
    msg = h.undo_last(within_s=5)
    assert "window" in msg.lower() or "purana" in msg.lower()
    assert len(h) == 1                      # not popped — still recoverable

    # force (within_s=None) undoes it regardless of age.
    assert h.undo_last(within_s=None) == "undone"
    assert len(h) == 0


def test_undo_handles_failing_undo_fn():
    h = ActionHistory()

    def _boom():
        raise RuntimeError("nope")

    h.record("breaks", _boom)
    msg = h.undo_last()
    assert "fail" in msg.lower()
    assert len(h) == 0                      # popped even though undo raised


def test_ring_buffer_evicts_oldest():
    h = ActionHistory(maxlen=3)
    for i in range(5):
        h.record(f"a{i}", lambda: "x")
    assert len(h) == 3
    assert h.peek_last().label == "a4"


def test_record_rejects_non_callable():
    h = ActionHistory()
    with pytest.raises(TypeError):
        h.record("bad", "not-callable")  # type: ignore[arg-type]


# ── skill registration ──────────────────────────────────────────────────


def test_undo_skill_registered():
    from core.skill_registry import discover_skills, get_skill
    discover_skills("skills")
    assert get_skill("undo_last") is not None


def test_undo_skill_runs_against_singleton():
    import core.action_history as ah
    from skills.undo_skill import undo_last as undo_skill

    ah.clear()
    flag = {"undone": False}
    ah.record("test action", lambda: flag.__setitem__("undone", True) or "test undone")

    msg = undo_skill({"raw_text": "undo that"})
    assert flag["undone"] is True
    assert "undone" in msg.lower()


# ── clipboard wiring (fake pyperclip) ───────────────────────────────────


def test_clipboard_copy_records_reversible_undo(monkeypatch):
    import skills.clipboard as clip
    import core.action_history as ah

    store = {"v": "ORIGINAL"}

    class FakeClip:
        @staticmethod
        def copy(t):
            store["v"] = t

        @staticmethod
        def paste():
            return store["v"]

    monkeypatch.setattr(clip, "pyperclip", FakeClip)
    monkeypatch.setattr(clip, "_AVAILABLE", True)
    ah.clear()

    res = clip.clipboard_copy({"content": "NEW TEXT"})
    assert "Copy kar liya" in res
    assert store["v"] == "NEW TEXT"

    # Undo restores the previous clipboard contents.
    msg = ah.undo_last()
    assert store["v"] == "ORIGINAL"
    assert "wapas" in msg.lower()
