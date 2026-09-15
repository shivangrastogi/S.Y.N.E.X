"""Iteration #3 skills — routing + handler tests.

Covers: scheduled_lock (lock_after / cancel_lock / lock_status),
journal (note_append / journal_show / journal_path), and
windows_power_utils (window_pin_top, window_unpin_top, summarize_window,
whoami_info, wallpaper_set, process_kill).

Side-effect-safe: no real lock is fired (we patch LockWorkStation), the
journal writes to a temp file, no real processes are killed, no
wallpaper changes are committed.
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
    "lock_after", "cancel_lock", "lock_status",
    "note_append", "journal_show", "journal_path",
    "window_pin_top", "window_unpin_top",
    "summarize_window", "whoami_info",
    "wallpaper_set",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no trigger patterns"


# ── brain routing ─────────────────────────────────────────────────

ROUTING_CASES = [
    ("lock after 5 minutes",   "lock_after"),
    ("lock in 2 mins",         "lock_after"),
    ("schedule lock",          "lock_after"),
    ("cancel lock",            "cancel_lock"),
    ("lock cancel",            "cancel_lock"),
    ("lock status",            "lock_status"),
    ("log this",               "note_append"),
    ("add to journal",         "note_append"),
    ("journal me likho",       "note_append"),
    ("show journal",           "journal_show"),
    ("journal path",           "journal_path"),
    ("pin window",             "window_pin_top"),
    ("always on top",          "window_pin_top"),
    ("unpin window",           "window_unpin_top"),
    ("summarize window",       "summarize_window"),
    ("whoami",                 "whoami_info"),
    ("who am i",               "whoami_info"),
    ("system identity",        "whoami_info"),
    ("set wallpaper",          "wallpaper_set"),
    ("change wallpaper",       "wallpaper_set"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_iter3(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── lock_after / cancel_lock (no real lock fires) ─────────────────


def test_lock_after_schedules_then_cancel(monkeypatch):
    import skills.scheduled_lock as sl

    fired = []
    monkeypatch.setattr(sl, "_do_lock", lambda: fired.append("LOCKED"))
    # Schedule something far enough out that we can cancel before it fires.
    out = sl.lock_after({"raw_text": "lock after 30 minutes"})
    assert "30" in out or "minute" in out.lower()
    status = sl.lock_status({})
    assert "lock" in status.lower()
    cancelled = sl.cancel_lock({})
    assert "cancel" in cancelled.lower()
    # Nothing should have fired (timer was cancelled).
    assert fired == []


def test_lock_after_parses_various_intervals(monkeypatch):
    import skills.scheduled_lock as sl
    monkeypatch.setattr(sl, "_do_lock", lambda: None)
    for text, min_sec, max_sec in [
        ("lock after 5 minutes", 300, 300),
        ("lock in 30s",          30,  60),    # min clamped at 5; 30 is fine
        ("lock me in 2 hours",   7200, 7200),
        ("10 minute me lock karo", 600, 600),
    ]:
        sl.lock_after({"raw_text": text})
        secs = sl._parse_seconds(text)
        assert min_sec <= secs <= max_sec, f"{text!r} → {secs}s"
        sl.cancel_lock({})


# ── journal ────────────────────────────────────────────────────────


def test_journal_append_and_show(monkeypatch, tmp_path):
    import skills.journal as j
    fake_path = tmp_path / "journal.md"
    monkeypatch.setattr(j, "_JOURNAL_DIR", tmp_path)
    monkeypatch.setattr(j, "_JOURNAL_PATH", fake_path)

    r1 = j.note_append({"raw_text": "log finished the gesture engine refactor"})
    assert "Logged" in r1
    r2 = j.note_append({"raw_text": "note that prod is down"})
    assert "Logged" in r2

    show = j.journal_show({})
    assert "finished the gesture engine refactor" in show
    # Verify the leading "that" was stripped.
    assert "prod is down" in show
    assert "that prod is down" not in show

    path_msg = j.journal_path({})
    assert str(fake_path) in path_msg


def test_journal_show_when_empty(monkeypatch, tmp_path):
    import skills.journal as j
    fake_path = tmp_path / "journal.md"
    monkeypatch.setattr(j, "_JOURNAL_DIR", tmp_path)
    monkeypatch.setattr(j, "_JOURNAL_PATH", fake_path)
    out = j.journal_show({})
    assert "khaali" in out.lower() or "empty" in out.lower()


def test_journal_append_no_text_prompts(monkeypatch, tmp_path):
    import skills.journal as j
    monkeypatch.setattr(j, "_JOURNAL_PATH", tmp_path / "journal.md")
    out = j.note_append({"raw_text": "log"})
    assert "?" in out or "kya" in out.lower() or "what" in out.lower()


# ── windows_power_utils ────────────────────────────────────────────


def test_window_pin_top_returns_string(monkeypatch):
    import skills.windows_power_utils as wpu
    monkeypatch.setattr(wpu, "_set_topmost", lambda topmost: (True, "Test Window"))
    out = wpu.window_pin_top({})
    assert "Test Window" in out
    out2 = wpu.window_unpin_top({})
    assert "Test Window" in out2


def test_summarize_window_handles_no_window(monkeypatch):
    import skills.windows_power_utils as wpu
    monkeypatch.setattr(wpu, "_foreground_info", lambda: ("", "", 0))
    out = wpu.summarize_window({})
    assert "nahi" in out.lower() or "no" in out.lower()


def test_whoami_returns_nonempty():
    from skills.windows_power_utils import whoami_info
    out = whoami_info({})
    assert "User" in out
    assert "Host" in out
    assert "IP" in out


def test_wallpaper_set_no_query_prompts():
    """'set wallpaper' alone strips to '' → must prompt for path, NOT search
    the filesystem for an image named 'set wallpaper'."""
    from skills.windows_power_utils import wallpaper_set, _strip_wallpaper_verb
    # First validate the verb-stripper handles the bare verb.
    assert _strip_wallpaper_verb("set wallpaper") == ""
    out = wallpaper_set({"raw_text": "set wallpaper"})
    assert ("?" in out or "kaunsi" in out.lower()
            or "path" in out.lower() or "image" in out.lower())


def test_wallpaper_resolver_handles_absolute_path(tmp_path):
    from skills.windows_power_utils import _resolve_image_path
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert _resolve_image_path(str(img)) == str(img)
