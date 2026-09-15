"""Tests for Ollama reachability probe + /health field + status skill."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import core.llm_chat as llm
from core.llm_chat import LLMChat, LLMConfig


class _FakeResp:
    def __init__(self, models):
        self._models = models

    def raise_for_status(self):
        pass

    def json(self):
        return {"models": [{"name": n} for n in self._models]}


def _patch_tags(monkeypatch, models=None, raise_exc=None):
    def _get(url, timeout=None):
        if raise_exc is not None:
            raise raise_exc
        return _FakeResp(models or [])
    monkeypatch.setattr(llm.requests, "get", _get)
    # These tests exercise the OLLAMA probe branches specifically. The
    # default backend is now "embedded" (in-process llama.cpp) and the
    # llm_enabled master switch may be off — force the ollama path so
    # the mocked HTTP layer is actually reached.
    monkeypatch.setattr(LLMChat, "_backend", staticmethod(lambda: "ollama"))
    monkeypatch.setattr(LLMChat, "_llm_enabled", staticmethod(lambda: True))


# ── probe branches ──────────────────────────────────────────────────────


def test_probe_unreachable(monkeypatch):
    _patch_tags(monkeypatch, raise_exc=llm.requests.ConnectionError("boom"))
    p = LLMChat(LLMConfig(model="phi3:mini")).probe()
    assert p["status"] == "unreachable"
    assert p["reachable"] is False
    assert "ollama serve" in p["message"]


def test_probe_no_model(monkeypatch):
    _patch_tags(monkeypatch, models=["llama3:latest"])
    p = LLMChat(LLMConfig(model="phi3:mini")).probe()
    assert p["status"] == "no_model"
    assert p["reachable"] is True
    assert p["model_present"] is False
    assert "ollama pull phi3:mini" in p["message"]
    assert "llama3" in p["models"]


def test_probe_ok(monkeypatch):
    _patch_tags(monkeypatch, models=["phi3:mini", "nomic-embed"])
    p = LLMChat(LLMConfig(model="phi3:mini")).probe()
    assert p["status"] == "ok"
    assert p["model_present"] is True


def test_is_available_uses_probe(monkeypatch):
    _patch_tags(monkeypatch, models=["phi3:latest"])
    assert LLMChat(LLMConfig(model="phi3:mini")).is_available() is True
    _patch_tags(monkeypatch, models=["other"])
    assert LLMChat(LLMConfig(model="phi3:mini")).is_available() is False


# ── cached probe ────────────────────────────────────────────────────────


def test_probe_cached_caches(monkeypatch):
    calls = {"n": 0}

    def _fake_probe(self):
        calls["n"] += 1
        return {"status": "ok", "reachable": True, "model_present": True,
                "model": "phi3:mini", "models": [], "message": "", "host": "h"}

    monkeypatch.setattr(LLMChat, "probe", _fake_probe)
    llm._PROBE_CACHE["result"] = None
    llm._PROBE_CACHE["ts"] = 0.0

    a = llm.probe_cached(ttl=100.0)
    b = llm.probe_cached(ttl=100.0)
    assert a == b
    assert calls["n"] == 1                  # second call served from cache


# ── /health field ───────────────────────────────────────────────────────


def test_health_includes_ollama(monkeypatch):
    import core.health_server as hs
    monkeypatch.setattr(
        llm, "probe_cached",
        lambda ttl=15.0: {"status": "no_model", "reachable": True,
                          "model": "phi3:mini", "model_present": False},
    )
    h = hs._collect_health()
    assert "llm_ollama" in h
    assert h["llm_ollama"]["status"] == "no_model"


# ── skill ───────────────────────────────────────────────────────────────


def test_llm_status_skill(monkeypatch):
    """The surviving llm_status (llm_chat_skill.py — backend-aware) reports
    the probe's status + actionable message. The Ollama-only duplicate in
    llm_status_skill.py was retired in the 2026-07-04 dedupe."""
    from core.skill_registry import discover_skills, get_skill
    discover_skills("skills")
    sk = get_skill("llm_status")
    assert sk is not None

    monkeypatch.setattr(
        LLMChat, "probe",
        lambda self: {"status": "unreachable", "reachable": False,
                      "model": "phi3:mini", "model_present": False,
                      "models": [], "message": "down — start: ollama serve",
                      "host": "http://localhost:11434"},
    )
    out = sk.run({})
    assert "unreachable" in out.lower()
    assert "ollama serve" in out.lower()   # probe message surfaced verbatim
