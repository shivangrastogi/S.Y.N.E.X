"""Tests for reversible memory-forget (core/memory.py) + undo integration."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.memory import UserMemory


@pytest.fixture
def mem(tmp_path):
    return UserMemory(path=str(tmp_path / "user_memory.json"))


# ── low-level forget / restore ──────────────────────────────────────────


def test_forget_returns_removed_entry(mem):
    mem.set("name", "Shivang")
    entry = mem.forget("name")
    assert entry is not None and entry["value"] == "Shivang"
    assert mem.get("name") is None


def test_forget_missing_returns_none(mem):
    assert mem.forget("nonexistent") is None


def test_restore_puts_fact_back(mem):
    mem.set("location", "Delhi")
    entry = mem.forget("location")
    mem.restore_fact("location", entry)
    assert mem.get("location") == "Delhi"


def test_forget_persists_across_reload(mem, tmp_path):
    mem.set("employer", "Acme")
    mem.forget("employer")
    reloaded = UserMemory(path=str(tmp_path / "user_memory.json"))
    assert reloaded.get("employer") is None


# ── detect_and_forget NL patterns ───────────────────────────────────────


def test_detect_forget_english(mem):
    mem.set("name", "Shivang")
    ack = mem.detect_and_forget("forget my name")
    assert ack and "bhool" in ack.lower()
    assert mem.get("name") is None


def test_detect_forget_hinglish_alias(mem):
    mem.set("location", "Delhi")           # "ghar" aliases to location
    ack = mem.detect_and_forget("mera ghar bhool jao")
    assert ack is not None
    assert mem.get("location") is None


def test_detect_forget_no_match_returns_none(mem):
    assert mem.detect_and_forget("what is my name") is None
    assert mem.detect_and_forget("open chrome") is None


def test_detect_forget_unknown_fact(mem):
    ack = mem.detect_and_forget("forget my birthday")
    assert ack is not None and "yaad hi nahi" in ack.lower()


# ── undo integration (I4 seam) ──────────────────────────────────────────


def test_forget_is_undoable(mem):
    import core.action_history as ah
    ah.clear()
    mem.set("name", "Shivang")

    ack = mem.detect_and_forget("forget my name")
    assert mem.get("name") is None
    assert ah.peek_last() is not None       # an undo was registered

    msg = ah.undo_last()
    assert mem.get("name") == "Shivang"     # restored!
    assert "wapas" in msg.lower()
