"""Locks in the two 'ambient / embedded argument' fixes from the 2026-08-01
routing pass so they can't silently regress:

* ``_fs_query`` — recovers a file-search query from the raw phrase (any word
  position) when the entity extractor left ``content`` empty, instead of the
  skill dead-ending at a "kaunsa file?" prompt though the user named the file.
* ``clipboard_transform`` — derives its mode word from the raw phrase and no
  longer gates on a ``content`` slot the extractor can never fill (the text to
  transform lives in the OS clipboard, not the command).

Both are pure/near-pure — no engine, runs in the fast lane. See
memory: aeris_routing_audit (2026-08-01 clipboard + file_search notes).
"""
from __future__ import annotations

import pytest

from skills.productivity_extras import (
    _fs_query, _proc_name, clipboard_transform, kill_process,
)


# ── _fs_query: query recovery from the raw phrase ───────────────────────
@pytest.mark.parametrize("slots,expected", [
    # An extracted content slot always wins.
    ({"content": "report.pdf"}, "report.pdf"),
    ({"content": "budget", "raw_text": "file dhundo budget"}, "budget"),
    # Prefix phrasings — trigger words before the name.
    ({"raw_text": "file dhundo report"}, "report"),
    ({"raw_text": "find files named readme"}, "readme"),
    ({"raw_text": "search for file invoice"}, "invoice"),
    ({"raw_text": "locate file config"}, "config"),
    # Postfix Hinglish — name before the trigger words (front-peel would miss).
    ({"raw_text": "report file kahaan hai"}, "report"),
    ({"raw_text": "mera resume kahaan hai"}, "resume"),
    # Filename fragments with dots/dashes survive tokenisation.
    ({"raw_text": "file dhundo main-window.py"}, "main-window.py"),
    # Bare trigger with no name → empty (handler then prompts).
    ({"raw_text": "file dhundo"}, ""),
    ({"raw_text": "find files"}, ""),
])
def test_fs_query_recovers_name(slots, expected):
    assert _fs_query(slots) == expected


def test_fs_query_empty_slots():
    assert _fs_query({}) == ""


# ── clipboard_transform: mode derived from raw phrase, no dead gate ──────
# The handler reaches its body now (required_entities=[]), so with no mode word
# it returns a "transform batao" hint rather than the old slot-fill prompt.
def test_clipboard_transform_no_mode_returns_hint():
    out = clipboard_transform({"raw_text": "clipboard transform karo"})
    assert "transform" in out.lower()
    # Must NOT be the old required-entity prompt that never ran the handler.
    assert "kaunsa transform" not in out.lower()


@pytest.mark.parametrize("phrase,mode_word", [
    ("clipboard uppercase karo", "upper"),
    ("clipboard ko lowercase karo", "lower"),
    ("clipboard reverse karo", "reverse"),
    ("clipboard slug karo", "slug"),
])
def test_clipboard_transform_detects_mode(phrase, mode_word, monkeypatch):
    """The handler should detect the mode and act on clipboard contents. We stub
    pyperclip so the test is deterministic and needs no real clipboard."""
    fake = {"buf": "Hello World"}

    class _FakeClip:
        @staticmethod
        def paste():
            return fake["buf"]

        @staticmethod
        def copy(v):
            fake["buf"] = v

    monkeypatch.setitem(__import__("sys").modules, "pyperclip", _FakeClip)
    out = clipboard_transform({"raw_text": phrase})
    # Reached the body and reported the detected mode — not a clarify prompt.
    assert mode_word in out.lower()
    assert "kaunsa transform" not in out.lower()


# ── kill_process: name recovery + safety (no real process is ever killed) ──
@pytest.mark.parametrize("slots,expected", [
    ({"content": "firefox"}, "firefox"),
    ({"raw_text": "kill firefox"}, "firefox"),
    ({"raw_text": "chrome band karo"}, "chrome"),
    ({"raw_text": "force quit discord"}, "discord"),
    ({"raw_text": "terminate spotify"}, "spotify"),
    ({"raw_text": "kill"}, ""),          # bare verb → no name
])
def test_proc_name_recovers_target(slots, expected):
    assert _proc_name(slots) == expected


def test_kill_process_bare_prompts():
    out = kill_process({"raw_text": "kill"})
    assert "kaunsa process" in out.lower()


def test_kill_process_blocks_system_critical():
    # Must refuse a system-critical target — and NOT actually terminate anything.
    out = kill_process({"raw_text": "kill explorer"})
    assert "system-critical" in out.lower()


def test_kill_process_unknown_name_is_safe():
    # A name that matches nothing running: reports "not found", kills nothing.
    out = kill_process({"raw_text": "kill zzqqxxfakeproc"})
    assert "nahi mila" in out.lower()
