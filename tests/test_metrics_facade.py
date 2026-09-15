"""Tests for the metrics façade + health-server disconnect hardening."""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core import metrics


def _write_log(path, events):
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(f"2026-06-26T12:00:00 INFO  aeris.event :: {json.dumps(ev)}\n")


def _no_ring(monkeypatch):
    import core.log_setup as ls
    monkeypatch.setattr(ls, "snapshot_events", lambda: [])


def test_snapshot_unifies_sections(tmp_path, monkeypatch):
    _no_ring(monkeypatch)
    now = time.time()
    log = tmp_path / "aeris.log"
    _write_log(log, [
        {"ts": now - 30, "event": "skill_dispatch", "intent": "weather",
         "action": "executed", "latency_ms": 12.0},
        {"ts": now - 20, "event": "routine_fire", "routine": "brief"},
    ])
    snap = metrics.snapshot(24.0, log_path=str(log), now=now)
    assert snap["window_h"] == 24.0
    assert snap["digest"]["total"] == 1          # only skill_dispatch counts here
    assert snap["changes"]["total"] == 2         # all events
    assert snap["last_dispatch"]["intent"] == "weather"
    assert "weather" in snap["summary"]
    assert "routine" in snap["narrative"]
    assert isinstance(snap["totals"], dict)


def test_snapshot_section_failure_is_isolated(monkeypatch):
    # If one source blows up, snapshot still returns the others with defaults.
    import core.activity_digest as ad
    monkeypatch.setattr(ad, "digest", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    snap = metrics.snapshot(1.0)
    assert snap["digest"] == {}                  # failed section → default
    assert "changes" in snap


def test_thin_reexports_present():
    for name in ("digest", "summarize", "changes", "last_dispatch", "format_chip"):
        assert callable(getattr(metrics, name))


# ── health-server disconnect hardening ──────────────────────────────────


def test_handler_swallows_client_disconnect(monkeypatch):
    import core.health_server as hs

    # Build a handler instance without running the socket machinery.
    handler = hs._Handler.__new__(hs._Handler)
    handler.path = "/health"

    # _serve_json raises a client-gone error as if the socket closed mid-write.
    def _boom(*a, **k):
        raise ConnectionAbortedError("client went away")

    monkeypatch.setattr(handler, "_serve_json", _boom)
    monkeypatch.setattr(hs, "_collect_health", lambda: {"ok": True})

    # Must NOT raise and must NOT attempt a second (error) response.
    handler.do_GET()


def test_handler_real_error_still_reported(monkeypatch):
    import core.health_server as hs

    handler = hs._Handler.__new__(hs._Handler)
    handler.path = "/health"

    calls = {"n": 0}

    def _serve(obj, status=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("genuine bug")     # first call (the health body) fails
        # second call is the error response — succeeds

    monkeypatch.setattr(handler, "_serve_json", _serve)
    monkeypatch.setattr(hs, "_collect_health", lambda: {"ok": True})

    handler.do_GET()
    assert calls["n"] == 2                       # error response WAS attempted
