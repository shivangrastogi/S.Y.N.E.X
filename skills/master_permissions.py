"""Master permissions / kid mode — per-master gesture allowlists.

Builds on top of ``master_users`` (the allowlist). Each named master can
have a list of allowed gestures; the gesture engine consults the list
on every emit via ``face_gate.gesture_allowed_for``.

Skills:
  * ``master_allow_all <name>``      — give a master every gesture
  * ``master_kid_mode <name>``       — restrict to safe gestures only
  * ``master_block <name> <gesture>``— remove a specific gesture
  * ``master_grant <name> <gesture>``— add a specific gesture
  * ``master_permissions_show``      — read back current map
  * ``master_permissions_clear``     — wipe the map (everyone → all)

Settings shape (``master_permissions`` key):
    {
      "shivang": ["all"],
      "kid":     ["double_pinch", "swipe_left", "swipe_right"]
    }
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core import settings as _settings
from core.skill_registry import skill

log = logging.getLogger(__name__)


# Conservative "kid-safe" default — interactive gestures only, no
# system-altering ones (no lock, no volume, no alt-tab).
_KID_SAFE_DEFAULT = [
    "double_pinch",      # play/pause
    "swipe_left", "swipe_right",
    "swipe_up", "swipe_down",
    "peace",             # screenshot
    "three_up",          # next track
    "thumbs_up", "thumbs_down",
    "wave",
]


def _load_perms() -> dict:
    raw = _settings.get("master_permissions") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for k, v in raw.items():
        if isinstance(v, list):
            out[str(k).strip().lower()] = [str(g).strip() for g in v]
    return out


def _save_perms(perms: dict[str, list[str]]) -> None:
    _settings.set_("master_permissions", perms)


def _known_gestures() -> list[str]:
    try:
        from core.gesture_engine import DEFAULT_ACTIONS
        return sorted(DEFAULT_ACTIONS.keys())
    except Exception:
        return []


def _extract_name(text: str, *triggers: str) -> str:
    if not text:
        return ""
    t = text.strip().lower()
    for trig in sorted(triggers, key=len, reverse=True):
        if t.startswith(trig):
            return t[len(trig):].strip(" .,?'\"")
    return ""


# ── master_allow_all ───────────────────────────────────────────────


@skill(
    name="master_allow_all",
    description="Grant a master full access to every gesture.",
    patterns=[
        "allow all gestures for", "master allow all",
        "give X all gestures", "X ko sab gestures de do",
        "X ko full access", "master full access",
    ],
    required_entities=[],
)
def master_allow_all(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract_name(
        text,
        "allow all gestures for", "master allow all",
        "give all gestures to", "give full access to",
        "master full access for", "master full access",
    )
    if not name:
        # Try Hinglish "X ko ... " patterns.
        m = re.search(r"([\w\s.\-']{2,40}?)\s+ko\s+(?:sab|full|all)\s+", text,
                      re.IGNORECASE)
        if m:
            name = m.group(1).strip()
    name = (name or "").strip().lower()
    if not name:
        return "Kis master ko? e.g. 'allow all gestures for shivang'."
    perms = _load_perms()
    perms[name] = ["all"]
    _save_perms(perms)
    return f"'{name}' → all gestures allowed."


# ── master_kid_mode ────────────────────────────────────────────────


@skill(
    name="master_kid_mode",
    description="Restrict a master to a small set of safe gestures "
                "(no lock screen, no volume control, no app-switch).",
    patterns=[
        "kid mode for", "set kid mode", "X ko kid mode pe rakho",
        "child mode for", "restrict X gestures",
        "limit X gestures", "X ko sirf safe gestures do",
    ],
    required_entities=[],
)
def master_kid_mode(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract_name(
        text,
        "kid mode for", "child mode for", "set kid mode for",
        "restrict gestures for", "limit gestures for",
        "kid mode", "child mode",
    )
    if not name:
        m = re.search(r"([\w\s.\-']{2,40}?)\s+ko\s+(?:kid|child|safe)\s+", text,
                      re.IGNORECASE)
        if m:
            name = m.group(1).strip()
    name = (name or "").strip().lower()
    if not name:
        return "Kis master ko kid mode pe? e.g. 'kid mode for kid'."
    perms = _load_perms()
    perms[name] = list(_KID_SAFE_DEFAULT)
    _save_perms(perms)
    return (f"'{name}' → kid mode. Allowed: "
            + ", ".join(_KID_SAFE_DEFAULT) + ".")


# ── master_grant / master_block ────────────────────────────────────


_GRANT_RE = re.compile(
    r"(?:grant|allow|add)\s+(?P<gesture>[a-z_][a-z0-9_]*)\s+(?:to|for)\s+(?P<name>[\w\s.\-']+)",
    re.IGNORECASE,
)
_BLOCK_RE = re.compile(
    r"(?:block|deny|remove)\s+(?P<gesture>[a-z_][a-z0-9_]*)\s+(?:from|for)\s+(?P<name>[\w\s.\-']+)",
    re.IGNORECASE,
)


@skill(
    name="master_grant",
    description="Grant a specific gesture to a master (adds to their allowlist).",
    patterns=[
        "grant gesture", "allow gesture", "add gesture for",
        "grant peace to shivang", "allow double_pinch for kid",
    ],
    required_entities=[],
)
def master_grant(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    m = _GRANT_RE.search(text)
    if not m:
        return "Format: 'grant <gesture> to <name>'. e.g. 'grant peace to kid'."
    gesture = m.group("gesture").strip().lower()
    name = m.group("name").strip().lower()
    if gesture not in _known_gestures():
        return f"'{gesture}' unknown gesture."
    perms = _load_perms()
    cur = perms.get(name, [])
    if "all" in cur or "*" in cur:
        return f"'{name}' already has all gestures."
    if gesture in cur:
        return f"'{name}' already has {gesture}."
    cur.append(gesture)
    perms[name] = cur
    _save_perms(perms)
    return f"Granted {gesture} to {name}. Now: {', '.join(cur)}."


@skill(
    name="master_block",
    description="Block a specific gesture for a master (removes from their allowlist).",
    patterns=[
        "block gesture", "deny gesture", "remove gesture for",
        "block peace from kid", "deny lock from kid",
    ],
    required_entities=[],
)
def master_block(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    m = _BLOCK_RE.search(text)
    if not m:
        return "Format: 'block <gesture> from <name>'."
    gesture = m.group("gesture").strip().lower()
    name = m.group("name").strip().lower()
    perms = _load_perms()
    cur = perms.get(name)
    if cur is None:
        return f"'{name}' had no explicit permissions — default is allow-all."
    if "all" in cur or "*" in cur:
        # Convert "all" → explicit list of all gestures minus the blocked one.
        cur = [g for g in _known_gestures() if g != gesture]
    else:
        cur = [g for g in cur if g != gesture]
    perms[name] = cur
    _save_perms(perms)
    return f"Blocked {gesture} for {name}. Now: {', '.join(cur) or '(none)'}."


# ── master_permissions_show / clear ────────────────────────────────


@skill(
    name="master_permissions_show",
    description="Show the per-master gesture allowlist.",
    patterns=[
        "master permissions", "show master permissions",
        "permissions dikhao", "kaun kaun gesture chala sakta hai",
        "gesture permissions", "master permission list",
    ],
    required_entities=[],
)
def master_permissions_show(_slots: dict) -> str:
    perms = _load_perms()
    if not perms:
        return ("Koi per-master permission set nahi — sab masters can fire "
                "every gesture (default allow-all).")
    lines = [f"{len(perms)} master permission entries:"]
    for name in sorted(perms):
        allowed = perms[name]
        if "all" in allowed or "*" in allowed:
            lines.append(f"  • {name:18s} → all gestures")
        elif not allowed:
            lines.append(f"  • {name:18s} → (nothing — fully blocked)")
        else:
            lines.append(f"  • {name:18s} → {', '.join(sorted(allowed))}")
    return "\n".join(lines)


@skill(
    name="master_permissions_clear",
    description="Wipe per-master gesture permissions (everyone reverts to allow-all).",
    patterns=[
        "clear master permissions", "reset master permissions",
        "permissions clear karo", "remove all master permissions",
    ],
    required_entities=[],
)
def master_permissions_clear(_slots: dict) -> str:
    _save_perms({})
    return "Master permissions cleared — every master can fire every gesture."
