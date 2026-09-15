"""Tier 5 — heads-up overlay, theme switcher, workspace tracker.

Side-effect-safe:
  * HUD tests only import the module and exercise the off-main-thread
    refusal path — no real overlay window is shown.
  * Theme tests use monkeypatched settings.
  * Workspace tracker tests stub _foreground_exe + the time module so
    no real OS polling happens.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "hud_on", "hud_off", "hud_move", "hud_status",
    "theme_dark", "theme_light", "theme_cyber",
    "theme_cycle", "theme_status",
    "workspace_track_on", "workspace_track_off",
    "workspace_summary", "workspace_summary_today",
    "workspace_clear", "workspace_recent",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("hud on",                          "hud_on"),
    ("show hud",                        "hud_on"),
    ("hud off",                         "hud_off"),
    ("hud move",                        "hud_move"),
    ("hud status",                      "hud_status"),
    ("dark theme",                      "theme_dark"),
    ("dark mode on",                    "theme_dark"),
    ("light theme",                     "theme_light"),
    ("cyber theme",                     "theme_cyber"),
    ("cycle theme",                     "theme_cycle"),
    ("theme status",                    "theme_status"),
    ("workspace track on",              "workspace_track_on"),
    ("workspace track off",             "workspace_track_off"),
    ("workspace summary",               "workspace_summary"),
    ("aaj kya kiya",                    "workspace_summary_today"),
    ("workspace clear",                 "workspace_clear"),
    ("workspace recent",                "workspace_recent"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier5(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── HUD ──────────────────────────────────────────────────────────


def test_hud_module_imports():
    import ui.hud_overlay as hud
    assert callable(hud.show_hud)
    assert callable(hud.hide_hud)


def test_hud_show_refused_without_qapp(monkeypatch):
    """Without a QApplication, show_hud must refuse cleanly (return False)."""
    import ui.hud_overlay as hud
    # Patch QApplication.instance to return None so the off-main check fires.
    try:
        from PyQt5.QtWidgets import QApplication
    except Exception:
        pytest.skip("PyQt5 not installed")
    monkeypatch.setattr(QApplication, "instance", staticmethod(lambda: None))
    assert hud.show_hud() is False


def test_hud_state_helpers_noop_when_hidden():
    """set_state / set_intent should be safe when HUD is hidden."""
    import ui.hud_overlay as hud
    hud._HUD_INSTANCE = None
    # No exception expected.
    hud.set_state("LISTENING")
    hud.set_intent("current_time")


def test_hud_status_returns_text():
    from skills.hud_skill import hud_status
    out = hud_status({})
    assert "HUD" in out


# ── theme ──────────────────────────────────────────────────────


def test_theme_list_contains_defaults():
    from core.theme import list_themes
    themes = list_themes()
    for t in ("dark", "light", "cyber"):
        assert t in themes


def test_theme_apply_persists(monkeypatch):
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from core.theme import apply_theme, current_theme
    ok, msg = apply_theme("cyber")
    assert ok
    assert state["ui_theme"] == "cyber"
    assert current_theme() == "cyber"


def test_theme_apply_unknown_returns_error(monkeypatch):
    monkeypatch.setattr("core.settings.set_", lambda k, v: None)
    monkeypatch.setattr("core.settings.get", lambda k, d=None: d)
    from core.theme import apply_theme
    ok, msg = apply_theme("notreal")
    assert ok is False
    assert "notreal" in msg.lower() or "unknown" in msg.lower()


def test_theme_cycle_rotates(monkeypatch):
    state = {"ui_theme": "dark"}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from core.theme import cycle_theme, list_themes
    themes = list_themes()
    seen = set()
    for _ in range(len(themes)):
        nxt, _ = cycle_theme()
        seen.add(nxt)
    assert seen == set(themes), f"cycle didn't visit every theme: {seen}"


def test_theme_get_active_stylesheet_returns_non_empty():
    from core.theme import get_active_stylesheet
    qss = get_active_stylesheet()
    assert isinstance(qss, str)
    assert "QWidget" in qss


# ── workspace tracker ───────────────────────────────────────────


def test_pretty_app_known_exe():
    from core.workspace_tracker import _pretty_app
    assert _pretty_app("code.exe") == "VS Code"
    assert _pretty_app("chrome.exe") == "Chrome"


def test_pretty_app_unknown_falls_back():
    from core.workspace_tracker import _pretty_app
    out = _pretty_app("xyz.exe")
    assert out and "xyz" in out.lower()


def test_pretty_app_handles_empty():
    from core.workspace_tracker import _pretty_app
    assert _pretty_app("") == "?"


def test_workspace_tracker_summary_when_empty():
    from core.workspace_tracker import get_workspace_tracker
    t = get_workspace_tracker()
    t._events.clear()
    t._thread = None
    out = t.summary()
    assert "track" in out.lower() or "activity" in out.lower()


def test_workspace_tracker_summary_aggregates():
    from core.workspace_tracker import get_workspace_tracker
    t = get_workspace_tracker()
    t._events.clear()
    now = time.time()
    t._events.extend([
        {"ts": now - 100, "exe": "code.exe",   "duration_s": 600},
        {"ts": now -  50, "exe": "chrome.exe", "duration_s": 240},
        {"ts": now -  20, "exe": "code.exe",   "duration_s": 300},
    ])
    out = t.summary(window_s=3600)
    assert "VS Code" in out
    assert "Chrome" in out
    # code total (900s = 15m) should rank above chrome (240s = 4m)
    assert out.find("VS Code") < out.find("Chrome")


def test_workspace_tracker_recent_events_returns_tail():
    from core.workspace_tracker import get_workspace_tracker
    t = get_workspace_tracker()
    t._events.clear()
    now = time.time()
    for i in range(15):
        t._events.append({"ts": now - 100 + i, "exe": f"app{i}.exe",
                          "duration_s": 30})
    recent = t.recent_events(5)
    assert len(recent) == 5
    assert recent[-1]["exe"] == "app14.exe"


def test_workspace_tracker_clear_returns_count():
    from core.workspace_tracker import get_workspace_tracker
    t = get_workspace_tracker()
    t._events = [{"ts": 0, "exe": "x.exe", "duration_s": 1}] * 5
    assert t.clear() == 5
    assert t._events == []


def test_workspace_format_duration():
    from core.workspace_tracker import WorkspaceTracker
    assert WorkspaceTracker._fmt_duration(45) == "45s"
    assert WorkspaceTracker._fmt_duration(125) == "2m 05s"
    assert WorkspaceTracker._fmt_duration(3725) == "1h 02m"


def test_workspace_skill_recent_handles_empty(monkeypatch):
    from core.workspace_tracker import get_workspace_tracker
    from skills.workspace_tracker_skill import workspace_recent
    get_workspace_tracker()._events.clear()
    out = workspace_recent({})
    assert "nahi" in out.lower() or "no" in out.lower()


def test_workspace_skill_summary_handles_empty(monkeypatch):
    from core.workspace_tracker import get_workspace_tracker
    from skills.workspace_tracker_skill import workspace_summary
    t = get_workspace_tracker()
    t._events.clear()
    t._thread = None
    out = workspace_summary({})
    assert "track" in out.lower() or "activity" in out.lower()
