"""Tier 8 — settings schema/migration, dep validator, docs generator,
first-run wizard.

Side-effect-safe:
  * Schema tests use synthetic dicts (no live settings.json mutation).
  * Dep validator tests just inspect the pure helpers.
  * Docs generator writes to tmp_path.
  * Wizard tests only import + assert main-thread refusal.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "settings_schema_status", "settings_schema_migrate",
    "dep_check", "dep_skills_dark",
    "regenerate_skill_docs",
    "open_first_run_wizard",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("settings schema status",          "settings_schema_status"),
    ("migrate settings",                "settings_schema_migrate"),
    ("dep check",                       "dep_check"),
    ("dependency check",                "dep_check"),
    ("dark skills",                     "dep_skills_dark"),
    ("regenerate skill docs",           "regenerate_skill_docs"),
    ("docs regen",                      "regenerate_skill_docs"),
    ("first run wizard",                "open_first_run_wizard"),
    ("setup wizard",                    "open_first_run_wizard"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier8(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── settings schema ──────────────────────────────────────────────


def test_schema_current_version_is_numeric():
    from core.settings_schema import current_version
    v = current_version()
    assert isinstance(v, int) and v >= 1


def test_schema_detect_version_handles_missing():
    from core.settings_schema import detect_version
    assert detect_version({}) == 0
    assert detect_version({"__schema_version": 3}) == 3
    # Non-int → treated as 0.
    assert detect_version({"__schema_version": "bad"}) == 0


def test_schema_migrates_v0_master_users_string():
    """v0 might have ``master_users: 'shivang'`` (a bare string) — should
    canonicalise to a list."""
    from core.settings_schema import ensure_current
    out = ensure_current({"master_users": "shivang"})
    assert out["master_users"] == ["shivang"]
    assert out["__schema_version"] == 2


def test_schema_migrates_v0_master_users_none():
    from core.settings_schema import ensure_current
    out = ensure_current({"master_users": None})
    assert out["master_users"] == []


def test_schema_migrates_v1_kid_mode_list():
    """v1 → v2 should convert kid_mode_list into per-master permissions."""
    from core.settings_schema import ensure_current
    out = ensure_current({"__schema_version": 1, "kid_mode_list": ["kid"]})
    perms = out["master_permissions"]
    assert "kid" in perms
    assert "double_pinch" in perms["kid"]
    assert "palm_fist_lock" not in perms["kid"]    # restricted away
    assert "kid_mode_list" not in out              # consumed by migration


def test_schema_fills_missing_defaults():
    from core.settings_schema import ensure_current, _DEFAULTS
    out = ensure_current({})
    for k in _DEFAULTS:
        assert k in out


def test_schema_idempotent():
    from core.settings_schema import ensure_current
    out1 = ensure_current({"master_users": "a"})
    out2 = ensure_current(dict(out1))
    assert out1 == out2


def test_schema_status_skill_returns_text():
    from skills.settings_schema_skill import settings_schema_status
    out = settings_schema_status({})
    assert "schema" in out.lower()


# ── dep validator ────────────────────────────────────────────────


def test_dep_list_returns_rows():
    from core.dep_validator import list_deps
    rows = list_deps()
    assert len(rows) > 10
    sample = rows[0]
    for key in ("dep", "installed", "fix", "affected", "affected_count"):
        assert key in sample


def test_dep_health_score_in_range():
    from core.dep_validator import health_score
    s = health_score()
    assert 0 <= s <= 100


def test_dep_missing_skills_returns_dict():
    from core.dep_validator import missing_skills
    out = missing_skills()
    assert isinstance(out, dict)
    # If anything is broken, each value is a list of dep names.
    for sk, deps in out.items():
        assert isinstance(deps, list)
        assert all(isinstance(d, str) for d in deps)


def test_dep_check_skill_returns_text():
    from skills.dep_validator_skill import dep_check
    out = dep_check({})
    assert "Dependency health" in out


def test_dep_skills_dark_skill_returns_text():
    from skills.dep_validator_skill import dep_skills_dark
    out = dep_skills_dark({})
    assert isinstance(out, str) and out.strip()


# ── docs generator ───────────────────────────────────────────────


def test_docs_default_path_is_under_docs():
    from core.docs_gen import default_path
    p = default_path()
    assert "docs" in str(p)
    assert p.name == "SKILLS.md"


def test_docs_write_produces_markdown(tmp_path):
    from core.docs_gen import write_skill_docs
    target = tmp_path / "SKILLS.md"
    info = write_skill_docs(str(target))
    assert info["ok"] is True
    assert info["skills"] >= 100
    assert info["categories"] >= 1
    text = target.read_text(encoding="utf-8")
    assert text.startswith("# AERIS skill catalog")
    # Should contain a markdown table header somewhere.
    assert "| Skill |" in text
    # Bundled known skill is listed.
    assert "current_time" in text


def test_docs_regen_skill_returns_text(tmp_path, monkeypatch):
    import core.docs_gen as dg
    monkeypatch.setattr(dg, "default_path",
                        lambda: tmp_path / "SKILLS.md")
    from skills.docs_gen_skill import regenerate_skill_docs
    out = regenerate_skill_docs({})
    assert "wrote" in out.lower() or "skill" in out.lower()


def test_docs_classify_fallback():
    from core.docs_gen import _classify
    # Known map should win
    assert _classify("current_time", {"current_time": "Quick info"}) == "Quick info"
    # Name-based fallback
    assert _classify("gesture_record", {}) == "Gestures"
    assert _classify("phone_pair_on", {}) == "System"
    assert _classify("totally_unknown_thing", {}) == "Other"


# ── first run wizard ────────────────────────────────────────────


def test_wizard_module_imports():
    import ui.first_run_wizard as w
    assert callable(w.open_first_run_wizard)


def test_wizard_refuses_without_qapp(monkeypatch):
    """No QApplication on the main thread → wizard returns False cleanly."""
    try:
        from PyQt5.QtWidgets import QApplication
    except Exception:
        pytest.skip("PyQt5 not installed")
    import threading as _th
    # Simulate a worker-thread caller via a quick monkeypatched "current
    # thread is not main thread" check — easier: directly invoke from a
    # worker.
    monkeypatch.setattr(QApplication, "instance", staticmethod(lambda: None))
    import ui.first_run_wizard as w
    result: list = []
    def _bg():
        result.append(w.open_first_run_wizard())
    th = _th.Thread(target=_bg, daemon=True)
    th.start(); th.join(timeout=2.0)
    assert result == [False]


def test_first_run_skill_returns_immediately():
    import time
    from skills.first_run_skill import open_first_run_wizard
    t0 = time.monotonic()
    out = open_first_run_wizard({})
    assert time.monotonic() - t0 < 0.5
    assert "wizard" in out.lower()
