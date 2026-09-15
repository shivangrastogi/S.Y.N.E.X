"""Tests for the activity-digest subsystem (core + skill).

Covers:
  * JSON-line parsing tolerant of the stdlib log prefix
  * time-windowing (events outside the window are dropped)
  * de-duplication across the file + ring buffer
  * the rollup math (counts, executed, latency percentiles)
  * natural-language window parsing in the skill
  * the skill being registered and callable
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core import activity_digest as ad


def _write_log(path, events, *, prefix=True):
    """Write events as the real logger would (optional stdlib prefix)."""
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            line = json.dumps(ev, ensure_ascii=False)
            if prefix:
                line = f"2026-06-26T12:00:00 INFO  aeris.event :: {line}"
            fh.write(line + "\n")


def _ev(intent, *, ago_h=0.0, action="executed", latency=10.0, now=None):
    now = time.time() if now is None else now
    return {
        "ts": now - ago_h * 3600.0,
        "event": "skill_dispatch",
        "intent": intent,
        "action": action,
        "latency_ms": latency,
        "confidence": 0.9,
    }


# ── parsing ───────────────────────────────────────────────────────────


def test_parse_line_strips_log_prefix():
    raw = '2026-06-26T12:00:00 INFO  aeris.event :: {"event":"skill_dispatch","intent":"weather"}'
    obj = ad._parse_line(raw)
    assert obj is not None
    assert obj["intent"] == "weather"


def test_parse_line_rejects_non_event_lines():
    assert ad._parse_line("just a plain warning, no json here") is None
    assert ad._parse_line('prefix :: {"no_event_key": 1}') is None


# ── windowing ─────────────────────────────────────────────────────────


def test_window_excludes_old_events(tmp_path, monkeypatch):
    now = time.time()
    log = tmp_path / "aeris.log"
    _write_log(log, [
        _ev("weather", ago_h=0.5, now=now),    # inside 1h
        _ev("timer", ago_h=2.0, now=now),      # outside 1h, inside 24h
        _ev("ancient", ago_h=100.0, now=now),  # outside both
    ])
    # Avoid folding in the live ring buffer for a deterministic count.
    monkeypatch.setattr(ad, "snapshot_events", lambda: [], raising=False)
    import core.log_setup as ls
    monkeypatch.setattr(ls, "snapshot_events", lambda: [])

    one_h = ad.read_events(1.0, log_path=str(log), now=now)
    assert [e["intent"] for e in one_h] == ["weather"]

    day = ad.read_events(24.0, log_path=str(log), now=now)
    assert sorted(e["intent"] for e in day) == ["timer", "weather"]


def test_dedup_same_ts_intent(tmp_path, monkeypatch):
    now = time.time()
    log = tmp_path / "aeris.log"
    dup = _ev("weather", ago_h=0.1, now=now)
    _write_log(log, [dup, dict(dup)])  # identical twice
    import core.log_setup as ls
    monkeypatch.setattr(ls, "snapshot_events", lambda: [])
    out = ad.read_events(24.0, log_path=str(log), now=now)
    assert len(out) == 1


# ── rollup ─────────────────────────────────────────────────────────────


def test_digest_counts_and_latency(tmp_path, monkeypatch):
    now = time.time()
    log = tmp_path / "aeris.log"
    _write_log(log, [
        _ev("weather", ago_h=0.1, latency=10.0, now=now),
        _ev("weather", ago_h=0.2, latency=30.0, now=now),
        _ev("timer", ago_h=0.3, latency=20.0, action="asked_slot", now=now),
    ])
    import core.log_setup as ls
    monkeypatch.setattr(ls, "snapshot_events", lambda: [])

    d = ad.digest(24.0, log_path=str(log), now=now)
    assert d["total"] == 3
    assert d["executed"] == 2          # timer was asked_slot
    assert d["unique"] == 2
    assert d["top"][0] == ("weather", 2)
    assert d["latency_p50_ms"] is not None


def test_summarize_empty_window(tmp_path, monkeypatch):
    log = tmp_path / "aeris.log"
    _write_log(log, [])
    import core.log_setup as ls
    monkeypatch.setattr(ls, "snapshot_events", lambda: [])
    msg = ad.summarize(1.0, log_path=str(log), now=time.time())
    assert "koi command nahi" in msg.lower()


def test_summarize_nonempty(tmp_path, monkeypatch):
    now = time.time()
    log = tmp_path / "aeris.log"
    _write_log(log, [_ev("weather", ago_h=0.1, now=now)])
    import core.log_setup as ls
    monkeypatch.setattr(ls, "snapshot_events", lambda: [])
    msg = ad.summarize(24.0, log_path=str(log), now=now)
    assert "weather" in msg
    assert "1 command" in msg


# ── skill ───────────────────────────────────────────────────────────────


def test_window_parsing():
    from skills.activity_digest_skill import _window_hours
    assert _window_hours("what did you do today") == 24.0
    assert _window_hours("summarise the last hour") == 1.0
    assert _window_hours("aaj kya kiya") == 24.0
    assert _window_hours("what have you done this week") == 24.0 * 7.0
    assert _window_hours("last 3 hours") == 3.0
    assert _window_hours("pichhle 2 din") == 48.0


def test_skill_registered_and_callable():
    from core.skill_registry import discover_skills, get_skill
    discover_skills("skills")
    sk = get_skill("activity_digest")
    assert sk is not None
    out = sk.run({"raw_text": "what did you do today"})
    assert isinstance(out, str) and out


# ── I2: chip + last_dispatch ────────────────────────────────────────────


def test_format_chip_full():
    ev = {"intent": "weather", "confidence": 0.912, "action": "executed", "latency_ms": 12.4}
    assert ad.format_chip(ev) == "weather · 0.91 · 12 ms"


def test_format_chip_shows_non_executed_action():
    ev = {"intent": "set_timer", "confidence": 0.8, "action": "asked_slot", "latency_ms": 5.0}
    chip = ad.format_chip(ev)
    assert "asked_slot" in chip and "set_timer" in chip


def test_format_chip_empty_for_none():
    assert ad.format_chip(None) == ""
    assert ad.format_chip({}) == ""           # no data → hide the chip
    assert ad.format_chip({"intent": "x"}) == "x"


def test_last_dispatch_returns_newest(tmp_path, monkeypatch):
    now = time.time()
    log = tmp_path / "aeris.log"
    _write_log(log, [
        _ev("weather", ago_h=2.0, now=now),
        _ev("timer", ago_h=0.1, now=now),     # newest
    ])
    import core.log_setup as ls
    monkeypatch.setattr(ls, "snapshot_events", lambda: [])
    ev = ad.last_dispatch(24.0, log_path=str(log), now=now)
    assert ev is not None and ev["intent"] == "timer"


def test_last_dispatch_none_when_empty(tmp_path, monkeypatch):
    log = tmp_path / "aeris.log"
    _write_log(log, [])
    import core.log_setup as ls
    monkeypatch.setattr(ls, "snapshot_events", lambda: [])
    assert ad.last_dispatch(24.0, log_path=str(log), now=time.time()) is None
