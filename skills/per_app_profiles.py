"""Per-application gesture profile management.

Lets the user say "in Code, bind peace to format" — when VS Code is the
foreground app, the peace gesture runs format-document instead of its
global binding.

Settings shape (``gesture_profiles_per_app`` key):
    {
      "code":     {"peace": "git_status", "double_pinch": "git_log"},
      "chrome":   {"peace": "screenshot_window"}
    }

Skills:
  * ``profile_bind`` — "in code bind peace to git_status"
  * ``profile_unbind`` — "in code unbind peace"
  * ``profile_list`` — show all per-app maps
  * ``profile_clear`` — wipe the whole per-app map
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core import settings as _settings
from core.skill_registry import skill, get_skill

log = logging.getLogger(__name__)


_BIND_RE = re.compile(
    r"(?:in|for|inside)\s+(?P<app>[\w.\- ]+?)\s+"
    r"(?:bind|map|set)\s+"
    r"(?P<gesture>[a-z_][a-z0-9_]*)"
    r"\s+(?:to|=)\s+"
    r"(?P<skill>[a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
_UNBIND_RE = re.compile(
    r"(?:in|for|inside)\s+(?P<app>[\w.\- ]+?)\s+"
    r"(?:unbind|remove|drop|reset)\s+"
    r"(?P<gesture>[a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def _load() -> dict:
    raw = _settings.get("gesture_profiles_per_app") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            out[str(k).strip().lower()] = {str(g): str(s) for g, s in v.items()
                                            if g and s}
    return out


def _save(perms: dict) -> None:
    _settings.set_("gesture_profiles_per_app", perms)


def _known_gestures() -> list[str]:
    try:
        from core.gesture_engine import DEFAULT_ACTIONS
        return sorted(DEFAULT_ACTIONS.keys())
    except Exception:
        return []


# ── profile_bind ───────────────────────────────────────────────────


@skill(
    name="profile_bind",
    description="Bind a gesture to a skill ONLY when a specific app is in "
                "foreground (e.g. 'in code bind peace to git_status').",
    patterns=[
        "in code bind", "in chrome bind", "for vs code bind",
        "in code map", "for chrome map", "inside code bind",
        "per app bind", "profile bind",
    ],
    required_entities=[],
)
def profile_bind(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    m = _BIND_RE.search(text)
    if not m:
        return ("Format: 'in <app> bind <gesture> to <skill>'. "
                "e.g. 'in code bind peace to git_status'.")
    app = m.group("app").strip().lower()
    gesture = m.group("gesture").lower()
    skill_name = m.group("skill").lower()
    if gesture not in _known_gestures():
        return f"'{gesture}' unknown gesture."
    if get_skill(skill_name) is None:
        return f"'{skill_name}' registered skill nahi hai."
    profiles = _load()
    profiles.setdefault(app, {})[gesture] = skill_name
    _save(profiles)
    return f"In {app}: {gesture} → {skill_name}."


# ── profile_unbind ─────────────────────────────────────────────────


@skill(
    name="profile_unbind",
    description="Remove a per-app gesture override.",
    patterns=[
        "in code unbind", "for chrome unbind", "in vs code unbind",
        "profile unbind", "remove app gesture", "remove per app gesture",
        "profile remove",
    ],
    required_entities=[],
)
def profile_unbind(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    m = _UNBIND_RE.search(text)
    if not m:
        return "Format: 'in <app> unbind <gesture>'."
    app = m.group("app").strip().lower()
    gesture = m.group("gesture").lower()
    profiles = _load()
    if app not in profiles or gesture not in profiles.get(app, {}):
        return f"In {app}: {gesture} had no override."
    del profiles[app][gesture]
    if not profiles[app]:
        del profiles[app]
    _save(profiles)
    return f"In {app}: removed {gesture} override."


# ── profile_list ───────────────────────────────────────────────────


@skill(
    name="profile_list",
    description="List every per-app gesture profile override.",
    patterns=[
        "list profiles", "show profiles", "profiles dikhao",
        "per app gestures", "per app profiles",
        "list per app profiles", "app gesture profiles",
    ],
    required_entities=[],
)
def profile_list(_slots: dict) -> str:
    profiles = _load()
    if not profiles:
        return "Koi per-app profile nahi — every app uses global gesture bindings."
    lines = [f"{len(profiles)} app profile(s):"]
    for app in sorted(profiles):
        lines.append(f"  • {app}:")
        for g, s in sorted(profiles[app].items()):
            lines.append(f"      {g:20s} → {s}")
    return "\n".join(lines)


# ── profile_clear ──────────────────────────────────────────────────


@skill(
    name="profile_clear",
    description="Wipe all per-app gesture profile overrides.",
    patterns=[
        "clear profiles", "reset profiles", "profiles clear karo",
        "wipe per app profiles", "clear all app gesture profiles",
    ],
    required_entities=[],
)
def profile_clear(_slots: dict) -> str:
    _save({})
    return "Cleared — every app reverts to global gesture bindings."
