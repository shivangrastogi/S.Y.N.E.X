"""Tests for routines introspection (core/routines_view.py + skill)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core import routines_view as rv


_FIXTURE = {
    "routines": [
        {
            "id": "morning", "name": "Morning Workspace",
            "trigger": {"kind": "time", "params": {"cron": "0 9 * * 1-5"}},
            "actions": [{"kind": "notify", "params": {"title": "gm"}},
                        {"kind": "open_app", "params": {"value": "code"}}],
            "enabled": True,
        },
        {
            "id": "evening", "name": "Coding Mode",
            "trigger": {"kind": "time", "params": {"cron": "0 19 * * *"}},
            "actions": [{"kind": "open_app", "params": {"value": "code"}}],
            "enabled": False,
        },
        {
            "id": "batt", "name": "Battery Saver",
            "trigger": {"kind": "battery_below", "params": {"percent": 20}},
            "actions": [{"kind": "notify", "params": {"title": "low"}}],
            "enabled": True,
        },
    ]
}


@pytest.fixture
def routines_path(tmp_path):
    p = tmp_path / "routines.json"
    p.write_text(json.dumps(_FIXTURE), encoding="utf-8")
    return str(p)


# ── loading / cron ──────────────────────────────────────────────────────


def test_load_routines(routines_path):
    rs = rv.load_routines(routines_path)
    assert [r.id for r in rs] == ["morning", "evening", "batt"]


def test_load_missing_file_is_empty():
    assert rv.load_routines("/no/such/file.json") == []


def test_cron_hour():
    assert rv.cron_hour("0 9 * * 1-5") == 9
    assert rv.cron_hour("0 19 * * *") == 19
    assert rv.cron_hour("*/5 * * * *") is None
    assert rv.cron_hour("garbage") is None


# ── routines_at ─────────────────────────────────────────────────────────


def test_routines_at_hour(routines_path):
    hits = rv.routines_at(9, routines_path)
    assert [r.id for r in hits] == ["morning"]
    assert rv.routines_at(19, routines_path)[0].id == "evening"
    assert rv.routines_at(3, routines_path) == []     # nothing at 3am


def test_summarize_at(routines_path):
    assert "Morning Workspace" in rv.summarize_at(9, routines_path)
    assert "09:00" in rv.summarize_at(9, routines_path)
    assert "kuch schedule nahi" in rv.summarize_at(3, routines_path).lower()


# ── summarize_routines ──────────────────────────────────────────────────


def test_summarize_all(routines_path):
    s = rv.summarize_routines(routines_path)
    assert "3 routine(s), 2 enabled" in s
    assert "Morning Workspace" in s and "Battery Saver" in s


def test_summarize_enabled_only(routines_path):
    s = rv.summarize_routines(routines_path, enabled_only=True)
    assert "Coding Mode" not in s          # it's disabled
    assert "Morning Workspace" in s


def test_summarize_empty(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text('{"routines": []}', encoding="utf-8")
    assert "koi" in rv.summarize_routines(str(p)).lower()


# ── skill ───────────────────────────────────────────────────────────────


def test_hour_parsing():
    from skills.routines_view_skill import _parse_hour
    assert _parse_hour("what fires at 9am") == 9
    assert _parse_hour("what's scheduled at 7 pm") == 19
    assert _parse_hour("21:00") == 21
    assert _parse_hour("9 baje kya hota hai") == 9
    assert _parse_hour("12 am") == 0
    assert _parse_hour("show my routines") is None


def test_skill_registered_and_callable():
    from core.skill_registry import discover_skills, get_skill
    discover_skills("skills")
    sk = get_skill("routines_view")
    assert sk is not None
    out = sk.run({"raw_text": "show my routines"})
    assert isinstance(out, str) and out
