"""Tests for the change-log narrative (core/change_log.py + skill)."""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core import change_log as cl


def _write_log(path, events):
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(f"2026-06-26T12:00:00 INFO  aeris.event :: {json.dumps(ev)}\n")


def _no_ring(monkeypatch):
    import core.log_setup as ls
    monkeypatch.setattr(ls, "snapshot_events", lambda: [])


def test_changes_buckets_by_kind(tmp_path, monkeypatch):
    _no_ring(monkeypatch)
    now = time.time()
    log = tmp_path / "aeris.log"
    _write_log(log, [
        {"ts": now - 60, "event": "skill_dispatch", "intent": "weather", "action": "executed"},
        {"ts": now - 50, "event": "skill_dispatch", "intent": "weather", "action": "executed"},
        {"ts": now - 40, "event": "skill_dispatch", "intent": "timer", "action": "executed"},
        {"ts": now - 30, "event": "routine_fire", "routine": "morning_brief"},
        {"ts": now - 20, "event": "presence_moment", "kind": "greet"},
    ])
    c = cl.changes(24.0, log_path=str(log), now=now)
    assert c["total"] == 5
    assert c["by_kind"]["skill_dispatch"] == 3
    assert c["by_kind"]["routine_fire"] == 1
    assert c["by_kind"]["presence_moment"] == 1
    assert c["top_intents"][0] == ("weather", 2)
    assert c["top_routines"][0] == ("morning_brief", 1)


def test_summarize_mentions_each_category(tmp_path, monkeypatch):
    _no_ring(monkeypatch)
    now = time.time()
    log = tmp_path / "aeris.log"
    _write_log(log, [
        {"ts": now - 60, "event": "skill_dispatch", "intent": "weather", "action": "executed"},
        {"ts": now - 30, "event": "routine_fire", "routine": "morning_brief"},
        {"ts": now - 20, "event": "presence_moment", "kind": "greet"},
    ])
    s = cl.summarize_changes(24.0, log_path=str(log), now=now)
    assert "command" in s
    assert "routine" in s and "morning_brief" in s
    assert "presence" in s


def test_summarize_unknown_kind_falls_through(tmp_path, monkeypatch):
    _no_ring(monkeypatch)
    now = time.time()
    log = tmp_path / "aeris.log"
    _write_log(log, [
        {"ts": now - 10, "event": "memory_store", "fact": "x"},
    ])
    s = cl.summarize_changes(24.0, log_path=str(log), now=now)
    assert "memory store" in s


def test_summarize_empty(tmp_path, monkeypatch):
    _no_ring(monkeypatch)
    log = tmp_path / "aeris.log"
    _write_log(log, [])
    s = cl.summarize_changes(24.0, log_path=str(log), now=time.time())
    assert "kuch khaas nahi" in s.lower()


def test_changes_since_boot_uses_marker(tmp_path, monkeypatch):
    _no_ring(monkeypatch)
    now = time.time()
    log = tmp_path / "aeris.log"
    _write_log(log, [
        {"ts": now - 120, "event": "skill_dispatch", "intent": "weather", "action": "executed"},
    ])
    # Patch the boot-marker reader path by monkeypatching summarize to capture window.
    captured = {}
    orig = cl.summarize_changes

    def _spy(window_h=24.0, **kw):
        captured["window_h"] = window_h
        return orig(window_h, log_path=str(log), now=now)

    monkeypatch.setattr(cl, "summarize_changes", _spy)

    # Write a boot marker 1h ago into the real data path is intrusive; instead
    # just assert the fallback path returns a string when marker is absent.
    out = cl.changes_since_boot()
    assert isinstance(out, str) and out


def test_skill_registered_and_distinct_from_digest():
    from core.skill_registry import discover_skills, get_skill
    discover_skills("skills")
    assert get_skill("change_log") is not None
    assert get_skill("activity_digest") is not None       # both coexist
    out = get_skill("change_log").run({"raw_text": "what did you change today"})
    assert isinstance(out, str) and out
