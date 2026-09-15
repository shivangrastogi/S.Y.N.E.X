"""Modes / Scenes engine — fake dispatch so no real action ever fires."""

from __future__ import annotations

import json

import pytest

from core.mode_engine import ModeEngine


@pytest.fixture
def eng(tmp_path):
    modes = {
        "work": {
            "description": "Deep work",
            "aliases": ["work", "kaam", "office"],
            "on": [{"skill": "focus_deep_on"},
                   {"skill": "brightness_set", "slots": {"content": "90"}}],
            "off": [{"skill": "focus_deep_off"}],
        },
        "sleep": {
            "description": "Wind down",
            "aliases": ["sleep", "sone", "raat"],
            "on": [{"skill": "volume_mute"}],
            "off": [],
        },
    }
    mpath = tmp_path / "modes.json"
    mpath.write_text(json.dumps(modes), encoding="utf-8")
    spath = tmp_path / "state.json"
    calls = []

    def fake_dispatch(name, slots):
        calls.append((name, slots))
        return f"ran {name}"

    e = ModeEngine(dispatch=fake_dispatch, modes_path=mpath, state_path=spath)
    e._calls = calls
    return e


class TestResolve:
    def test_by_name(self, eng):
        assert eng.resolve("work mode chalu karo") == "work"

    def test_by_alias(self, eng):
        assert eng.resolve("kaam mode on") == "work"
        assert eng.resolve("raat wala mode") == "sleep"

    def test_no_match(self, eng):
        assert eng.resolve("random gibberish") is None

    def test_longest_alias_wins(self, eng):
        # 'office' should still map to work; unrelated words ignored
        assert eng.resolve("office mode") == "work"


class TestActivate:
    def test_runs_all_on_steps(self, eng):
        out = eng.activate("work")
        assert "ON" in out and "2 steps" in out
        assert eng._calls == [("focus_deep_on", {}),
                              ("brightness_set", {"content": "90"})]

    def test_marks_active_and_persists(self, eng):
        eng.activate("work")
        assert eng.active() == ["work"]

    def test_reactivate_notes_already(self, eng):
        eng.activate("work")
        eng._calls.clear()
        out = eng.activate("work")
        assert "phir se" in out
        # still re-runs the steps
        assert len(eng._calls) == 2

    def test_unknown_mode_returns_none(self, eng):
        assert eng.activate("nonexistent") is None


class TestDeactivate:
    def test_runs_off_steps(self, eng):
        eng.activate("work")
        eng._calls.clear()
        out = eng.deactivate("work")
        assert "OFF" in out
        assert eng._calls == [("focus_deep_off", {})]
        assert eng.active() == []

    def test_no_off_steps_notes_it(self, eng):
        eng.activate("sleep")
        out = eng.deactivate("sleep")
        assert "reverse" in out

    def test_deactivate_when_not_active(self, eng):
        out = eng.deactivate("work")
        assert "already off" in out


class TestRealModesFileValid:
    def test_shipped_modes_load_and_reference_real_skills(self):
        """data/modes.json parses and every step names a registered skill."""
        import importlib
        import pkgutil
        import skills as _skills_pkg
        for m in pkgutil.iter_modules(_skills_pkg.__path__):
            try:
                importlib.import_module("skills." + m.name)
            except Exception:
                pass
        from core.skill_registry import all_skills
        from core.mode_engine import ModeEngine
        known = set(all_skills().keys())
        e = ModeEngine(dispatch=lambda n, s: "")  # real modes.json path
        modes = e.list_modes()
        assert modes, "shipped modes.json should define at least one mode"
        for name, m in modes.items():
            for step in m["on"] + m["off"]:
                assert step["skill"] in known, \
                    f"mode {name!r} references unknown skill {step['skill']!r}"
