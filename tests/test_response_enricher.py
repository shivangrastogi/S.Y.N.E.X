"""Response enricher — cache hits, LLM stubbing, fallback, skill wiring."""
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core import response_enricher as enr
from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Redirect the on-disk cache + reset in-memory state per test."""
    cache = tmp_path / "response_cache.json"
    monkeypatch.setattr(enr, "_CACHE_PATH", cache)
    monkeypatch.setattr(enr, "_STATE", {})
    # Force enabled regardless of user settings on disk.
    monkeypatch.setattr(enr, "is_enabled", lambda: True)
    yield


def test_falls_back_to_base_when_llm_unavailable_and_cache_empty(monkeypatch):
    monkeypatch.setattr(enr, "_via_llm", lambda *a, **k: None)
    out = enr.enriched_reply("greeting", "BASE")
    assert out == "BASE"


def test_caches_llm_output_and_returns_it(monkeypatch):
    monkeypatch.setattr(enr, "_via_llm", lambda *a, **k: "Hi sir, kaisa din?")
    out = enr.enriched_reply("greeting", "BASE")
    assert out == "Hi sir, kaisa din?"
    saved = enr._slot("greeting")["entries"]
    assert any(e["text"] == "Hi sir, kaisa din?" for e in saved)


def test_persists_to_disk(monkeypatch):
    monkeypatch.setattr(enr, "_via_llm", lambda *a, **k: "Salaam sir!")
    enr.enriched_reply("greeting", "BASE")
    raw = json.loads(Path(enr._CACHE_PATH).read_text(encoding="utf-8"))
    assert "greeting" in raw
    assert any(e["text"] == "Salaam sir!" for e in raw["greeting"]["entries"])


def test_picks_from_cache_when_enough_entries(monkeypatch):
    # Seed three cached lines and ensure LLM is NOT called.
    for line in ["one", "two", "three"]:
        enr._append_to_cache("greeting", line)

    sentinel = {"called": False}
    def _spy(*a, **k):
        sentinel["called"] = True
        return "shouldnotsee"
    monkeypatch.setattr(enr, "_via_llm", _spy)

    out = enr.enriched_reply("greeting", "BASE")
    assert out in {"one", "two", "three"}
    assert sentinel["called"] is False


def test_avoids_repeating_recent_picks(monkeypatch):
    for line in ["alpha", "beta", "gamma", "delta", "epsilon"]:
        enr._append_to_cache("greeting", line)
    monkeypatch.setattr(enr, "_via_llm", lambda *a, **k: None)

    seen: list[str] = []
    for _ in range(3):
        seen.append(enr.enriched_reply("greeting", "BASE"))
    # Three picks in a row should be three distinct lines because the
    # recent-avoid window is 3 wide.
    assert len(set(seen)) == 3


def test_clear_cache_removes_entries():
    enr._append_to_cache("greeting", "x")
    enr._append_to_cache("greeting", "y")
    n = enr.clear_cache("greeting")
    assert n == 2
    assert "greeting" not in enr._STATE


def test_stats_reports_counts(monkeypatch):
    monkeypatch.setattr(enr, "_llm_available_safe", lambda: False)
    enr._append_to_cache("greeting", "x")
    enr._append_to_cache("greeting", "y")
    enr._append_to_cache("farewell", "z")
    s = enr.stats()
    assert s["enabled"] is True
    assert s["total"] == 3
    by = {row["slot"]: row["count"] for row in s["slots"]}
    assert by == {"greeting": 2, "farewell": 1}


def test_disabled_returns_base(monkeypatch):
    monkeypatch.setattr(enr, "is_enabled", lambda: False)
    monkeypatch.setattr(enr, "_via_llm", lambda *a, **k: "should not call")
    assert enr.enriched_reply("greeting", "BASE") == "BASE"


def test_llm_exception_falls_back(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(enr, "_via_llm", _boom)
    assert enr.enriched_reply("greeting", "BASE") == "BASE"


# ── Skill wiring ────────────────────────────────────────────────


def test_greeting_skill_invokes_enricher(monkeypatch):
    monkeypatch.setattr(enr, "_via_llm", lambda *a, **k: "Enriched reply!")
    handler = all_skills()["greeting"].handler
    out = handler({})
    assert out == "Enriched reply!"


def test_greeting_skill_falls_back_when_enricher_returns_base(monkeypatch):
    monkeypatch.setattr(enr, "_via_llm", lambda *a, **k: None)
    handler = all_skills()["greeting"].handler
    out = handler({})
    # When the enricher cannot produce, the skill should return its base.
    assert "sir" in out.lower()


def test_executor_greet_invokes_enricher(monkeypatch):
    monkeypatch.setattr(enr, "_via_llm", lambda *a, **k: "Enriched greet!")
    # Build a bare-bones executor; greet() only needs `self`.
    from core.executor import ActionExecutor
    out = ActionExecutor.greet(object.__new__(ActionExecutor))
    assert out == "Enriched greet!"


def test_enricher_skills_registered():
    names = set(all_skills().keys())
    assert {"enrich_responses_on", "enrich_responses_off",
            "enrich_cache_clear", "enrich_status"} <= names
