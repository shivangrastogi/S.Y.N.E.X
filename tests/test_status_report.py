"""Tests for the unified status report (core/status_report.py + skill)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import core.status_report as sr


def _patch_all(monkeypatch, *, llm, pressure, rss, total, unique):
    monkeypatch.setattr(sr, "_llm_section", lambda: {"status": llm, "model": "phi3:mini"})
    monkeypatch.setattr(sr, "_resource_section", lambda: {"pressure": pressure, "rss_mb": rss})
    monkeypatch.setattr(sr, "_activity_section", lambda w: {"total": total, "unique": unique})


def test_status_all_healthy(monkeypatch):
    _patch_all(monkeypatch, llm="ok", pressure="ok", rss=800, total=5, unique=3)
    out = sr.summarize_status()
    assert "All good" in out
    assert "LLM chat ready" in out
    assert "5 command" in out
    assert "800 MB" in out


def test_status_llm_offline(monkeypatch):
    _patch_all(monkeypatch, llm="unreachable", pressure="ok", rss=700, total=0, unique=0)
    out = sr.summarize_status()
    assert "offline" in out.lower()
    assert "command" not in out          # no activity clause when total == 0


def test_status_no_model(monkeypatch):
    _patch_all(monkeypatch, llm="no_model", pressure="warning", rss=1200, total=0, unique=0)
    out = sr.summarize_status()
    assert "model" in out.lower()
    assert "high" in out.lower()         # warning pressure phrasing


def test_status_critical_pressure(monkeypatch):
    _patch_all(monkeypatch, llm="ok", pressure="critical", rss=1500, total=2, unique=1)
    out = sr.summarize_status()
    assert "pressure high" in out.lower()


def test_status_graceful_when_all_unknown(monkeypatch):
    _patch_all(monkeypatch, llm="unknown", pressure="unknown", rss=None, total=0, unique=0)
    out = sr.summarize_status()
    assert "theek" in out.lower()        # falls back to the all-good default


def test_system_status_shape(monkeypatch):
    _patch_all(monkeypatch, llm="ok", pressure="ok", rss=800, total=1, unique=1)
    s = sr.system_status()
    assert set(s.keys()) == {"llm", "resource", "activity"}


def test_section_failure_degrades_to_default(monkeypatch):
    # If the underlying source of a section raises, that section returns its
    # guarded default rather than propagating — verified directly on the
    # resource section by making get_monitor import-fail.
    import sys
    monkeypatch.setitem(sys.modules, "core.resource_monitor", None)
    out = sr._resource_section()
    assert out == {"pressure": "unknown", "rss_mb": None}
    # And the whole report still composes to a string.
    assert isinstance(sr.summarize_status(), str)


def test_skill_registered_and_callable():
    from core.skill_registry import discover_skills, get_skill
    discover_skills("skills")
    sk = get_skill("status_report")
    assert sk is not None
    assert isinstance(sk.run({}), str)
