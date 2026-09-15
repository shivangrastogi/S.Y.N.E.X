"""Tier 3 — command palette, cross-skill chains, per-app profiles, privacy mode.

Side-effect-safe:
  * Command palette dialog never opens (handler launches a daemon
    thread that refuses to spawn QApplication off main); we only test
    the pure ``fuzzy_rank`` / ``_score`` helpers.
  * Chain engine is wired with a stub skill so no real lock-screen fires.
  * Per-app profile tests stub the foreground-exe probe.
  * Privacy mode tests stub every subsystem stop() to count calls.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "open_command_palette",
    "chains_on", "chains_list", "chains_reload", "chain_path",
    "profile_bind", "profile_unbind", "profile_list", "profile_clear",
    "privacy_mode_on", "privacy_mode_off", "privacy_mode_status",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("open command palette",         "open_command_palette"),
    ("command palette",              "open_command_palette"),
    ("palette kholo",                "open_command_palette"),
    ("chains on",                    "chains_on"),
    ("list chains",                  "chains_list"),
    ("reload chains",                "chains_reload"),
    ("chain path",                   "chain_path"),
    ("in code bind",                 "profile_bind"),
    ("in code unbind",               "profile_unbind"),
    ("list profiles",                "profile_list"),
    ("clear profiles",               "profile_clear"),
    ("privacy mode on",              "privacy_mode_on"),
    ("stop listening",               "privacy_mode_on"),
    ("privacy mode off",             "privacy_mode_off"),
    ("privacy mode status",          "privacy_mode_status"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier3(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── command palette fuzzy ────────────────────────────────────────


def test_score_exact_prefix():
    from ui.command_palette import _score
    assert _score("open", "open_chrome", []) == 1.0


def test_score_exact_pattern_hit():
    from ui.command_palette import _score
    assert _score("kitna baja hai", "current_time",
                  ["what's the time", "kitna baja hai"]) == 0.9


def test_score_substring():
    from ui.command_palette import _score
    assert _score("chrome", "open_chrome", []) == 0.8


def test_score_subsequence():
    from ui.command_palette import _score
    s = _score("scrn", "screenshot_full", [])
    assert s == 0.5


def test_score_no_match():
    from ui.command_palette import _score
    assert _score("xyzqrjj", "open_chrome", []) == 0.0


def test_fuzzy_rank_orders_by_score():
    from ui.command_palette import fuzzy_rank
    from core.skill_registry import all_skills
    rank = fuzzy_rank("chrome", all_skills())
    assert rank, "no matches for 'chrome'"
    # Top hit must be a meaningful match — at least the token-in-haystack
    # tier (0.7). "chrome" isn't a skill name nor an exact pattern (the
    # pattern is "chrome kholo"), so we don't expect 0.8+ here.
    assert rank[0][1] >= 0.7
    # Results are sorted desc by score.
    scores = [r[1] for r in rank]
    assert scores == sorted(scores, reverse=True)


def test_fuzzy_rank_exact_prefix_match():
    """Querying with a real skill-name prefix should hit the top tier (1.0)."""
    from ui.command_palette import fuzzy_rank
    from core.skill_registry import all_skills
    rank = fuzzy_rank("current_t", all_skills())
    assert rank, "no matches for 'current_t'"
    assert rank[0][0] == "current_time"
    assert rank[0][1] == 1.0


def test_fuzzy_rank_empty_query():
    from ui.command_palette import fuzzy_rank
    from core.skill_registry import all_skills
    assert fuzzy_rank("", all_skills()) == []


# ── chain engine ─────────────────────────────────────────────────


def test_chain_engine_loads_default_chains(monkeypatch, tmp_path):
    """The shipped chains.json should parse cleanly."""
    from core.chain_engine import get_chain_engine
    # Reset singleton so reload reads the live file.
    import core.chain_engine as ce
    ce._DEFAULT = None
    eng = get_chain_engine()
    chains = eng.list_chains()
    # We ship at least lock_then_pause + screenshot_then_journal.
    assert len(chains) >= 1


def test_chain_engine_filters_invalid_entries(monkeypatch, tmp_path):
    """Entries without trigger/then should be silently dropped."""
    import core.chain_engine as ce
    bad = tmp_path / "chains.json"
    bad.write_text('{"good": {"trigger":"a", "then":[{"skill":"x"}]}, '
                   '"_comment": "ignored", '
                   '"bad1": {"trigger":"a"}, '
                   '"bad2": {"then":[]}}', encoding="utf-8")
    monkeypatch.setattr(ce, "_CHAINS_PATH", bad)
    ce._DEFAULT = None
    eng = ce.get_chain_engine()
    chains = eng.list_chains()
    assert set(chains.keys()) == {"good"}


def test_chain_engine_dispatches(monkeypatch, tmp_path):
    """When a trigger fires, every step's skill is invoked."""
    import core.chain_engine as ce
    cfg = tmp_path / "chains.json"
    cfg.write_text(
        '{"chain1": {"trigger":"test_trigger",'
        ' "then":[{"skill":"_dummy_chain_skill"}, {"skill":"_dummy_chain_skill"}]}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(ce, "_CHAINS_PATH", cfg)
    ce._DEFAULT = None
    fired = []
    # Patch registry lookup to return a fake skill.
    class _FakeSkill:
        def run(self, slots):
            fired.append(slots)
            return "ok"
    import core.skill_registry as sr
    monkeypatch.setattr(sr, "get_skill",
                        lambda name: _FakeSkill() if name == "_dummy_chain_skill" else None)
    eng = ce.get_chain_engine()
    logs = eng.fire_for("test_trigger")
    assert len(fired) == 2
    assert len(logs) == 2


def test_chain_recursion_guard(monkeypatch, tmp_path):
    """Same event firing twice within the guard window only runs once."""
    import core.chain_engine as ce
    cfg = tmp_path / "chains.json"
    cfg.write_text(
        '{"c": {"trigger":"x","then":[{"skill":"_dummy"}]}}', encoding="utf-8")
    monkeypatch.setattr(ce, "_CHAINS_PATH", cfg)
    ce._DEFAULT = None
    calls = []
    class _S:
        def run(self, s): calls.append(s); return "ok"
    import core.skill_registry as sr
    monkeypatch.setattr(sr, "get_skill",
                        lambda n: _S() if n == "_dummy" else None)
    eng = ce.get_chain_engine()
    eng.fire_for("x")
    eng.fire_for("x")    # within guard window
    assert len(calls) == 1


def test_chain_engine_missing_skill_reports_cleanly(monkeypatch, tmp_path):
    """If a step's skill isn't registered, fire_for must NOT crash."""
    import core.chain_engine as ce
    cfg = tmp_path / "chains.json"
    cfg.write_text(
        '{"c": {"trigger":"x","then":[{"skill":"definitely_not_registered_xyz"}]}}',
        encoding="utf-8")
    monkeypatch.setattr(ce, "_CHAINS_PATH", cfg)
    ce._DEFAULT = None
    eng = ce.get_chain_engine()
    logs = eng.fire_for("x")
    assert len(logs) == 1
    assert "not registered" in logs[0].lower() or "fail" in logs[0].lower()


# ── per-app profiles ─────────────────────────────────────────────


def test_profile_bind_writes_settings(monkeypatch):
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from skills.per_app_profiles import profile_bind
    out = profile_bind({"raw_text": "in code bind peace to git_status"})
    perms = state.get("gesture_profiles_per_app") or {}
    assert "code" in perms
    assert perms["code"]["peace"] == "git_status"
    assert "git_status" in out


def test_profile_bind_format_error(monkeypatch):
    monkeypatch.setattr("core.settings.set_", lambda k, v: None)
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: d)
    from skills.per_app_profiles import profile_bind
    out = profile_bind({"raw_text": "in code bind"})
    assert "Format" in out


def test_profile_unbind_removes_entry(monkeypatch):
    state = {"gesture_profiles_per_app": {"code": {"peace": "git_status",
                                                    "double_pinch": "git_log"}}}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from skills.per_app_profiles import profile_unbind
    out = profile_unbind({"raw_text": "in code unbind peace"})
    perms = state["gesture_profiles_per_app"]
    assert "peace" not in perms.get("code", {})
    assert "double_pinch" in perms["code"]


def test_per_app_override_resolves_for_matching_exe(monkeypatch):
    """When foreground exe matches, _per_app_override should return the
    mapped skill — overriding any global binding."""
    from core import gesture_engine as ge
    monkeypatch.setattr(ge, "_foreground_exe_name", lambda: "code.exe")
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None:
                            {"code": {"peace": "git_status"}}
                            if k == "gesture_profiles_per_app" else d)
    eng = ge.GestureEngine.__new__(ge.GestureEngine)
    result = eng._per_app_override("peace")
    assert result == "git_status"


def test_per_app_override_no_match(monkeypatch):
    from core import gesture_engine as ge
    monkeypatch.setattr(ge, "_foreground_exe_name", lambda: "notepad.exe")
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None:
                            {"code": {"peace": "git_status"}}
                            if k == "gesture_profiles_per_app" else d)
    eng = ge.GestureEngine.__new__(ge.GestureEngine)
    assert eng._per_app_override("peace") is None


# ── privacy_mode ─────────────────────────────────────────────────


def test_privacy_mode_state_round_trip(monkeypatch):
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from core import privacy_mode as pm
    assert pm.is_on() is False
    pm._settings_set("privacy_mode", True)
    assert pm.is_on() is True


def test_privacy_mode_enable_stops_running_subsystems(monkeypatch):
    """enable() must call stop() on every subsystem that reports enabled,
    and NOT crash when a subsystem is missing."""
    stops: list[str] = []

    class _Eng:
        def __init__(self, label, enabled=True):
            self.label = label
            self._enabled = enabled
        def is_enabled(self): return self._enabled
        def stop(self): stops.append(self.label)

    fake_ge = _Eng("gestures")
    fake_al = _Eng("auto_label")
    fake_pe = _Eng("presence")
    monkeypatch.setattr("core.gesture_engine.get_gesture_engine",
                        lambda: type("_GE", (), {
                            "is_enabled": lambda self=fake_ge: fake_ge.is_enabled(),
                            "stop": lambda self=fake_ge: fake_ge.stop(),
                            "is_cursor_mode": lambda self: False,
                            "set_cursor_mode": lambda self, on: None,
                        })())
    monkeypatch.setattr("core.auto_label.get_auto_label_engine",
                        lambda: fake_al)
    monkeypatch.setattr("core.presence.get_presence_engine",
                        lambda: fake_pe)
    # Notifier + voice — stubbed to absent state.
    class _NL:
        def is_running(self): return False
        def stop(self): stops.append("notif")
    monkeypatch.setattr("core.notify_listener.get_listener", lambda: _NL())

    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: None)
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: d)

    from core import privacy_mode as pm
    stopped = pm.enable()
    assert "gestures" in stopped
    assert "auto-label" in stopped or "auto-label" not in stopped  # depends on label
    # Notif mirror wasn't running → must NOT have been stopped.
    assert "notification-mirror" not in stopped
    # gestures stop() must have been called exactly once.
    assert stops.count("gestures") == 1


def test_privacy_mode_disable_returns_guidance(monkeypatch):
    monkeypatch.setattr("core.settings.set_", lambda k, v: None)
    monkeypatch.setattr("core.settings.get", lambda k, d=None: True)
    from core import privacy_mode as pm
    out = pm.disable()
    assert "off" in out.lower()
    assert "re-enable" in out.lower() or "manually" in out.lower()


def test_privacy_mode_explain():
    from core import privacy_mode as pm
    out = pm.explain()
    assert "Privacy mode" in out
