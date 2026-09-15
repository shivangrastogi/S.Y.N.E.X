"""Settings schema + migration — keeps settings.json forward-compatible.

Each schema version describes the canonical shape of the settings file
and a ``migrate_from_<N>(d)`` function that converts a v(N-1) blob into
v(N). On AERIS start we read the file, look at ``__schema_version`` (or
treat absent as version 0), and run every pending migration in order.

Adding a new version:
  1. Bump ``CURRENT_VERSION`` by one
  2. Add a ``migrate_from_<previous_version>`` callable
  3. Update the canonical-shape comment

Public API:
    ensure_current(settings_dict) -> dict   # mutates + returns
    current_version() -> int
    schema_status() -> dict
"""
from __future__ import annotations

import logging
from typing import Callable

log = logging.getLogger(__name__)


CURRENT_VERSION = 2
_SCHEMA_KEY = "__schema_version"


# ── canonical defaults ────────────────────────────────────────────


# Default values that should always be present at the current version.
# Missing keys get filled in; existing values are left alone.
_DEFAULTS = {
    _SCHEMA_KEY:      CURRENT_VERSION,
    "assistant_name": "AERIS",
    "wake_word":      "aeris",
    "speech_rate":    175,
    "voice_volume":   1.0,
    "tts_voice":      "",
    "default_browser": "system",
    "language":       "hinglish",
    "gesture_sensitivity": "normal",
    "master_users":   [],
    "master_gate_strict": False,
    "master_permissions": {},
    "gesture_profiles_per_app": {},
    "plugins_enabled": [],
    "ui_theme":       "dark",
    "privacy_mode":   False,
    "gpu_offload":    False,
}


# ── migrations ────────────────────────────────────────────────────


def _migrate_from_0(d: dict) -> dict:
    """v0 → v1 — early files had bare strings for master_users or no key
    at all; canonicalise to a list."""
    val = d.get("master_users")
    if isinstance(val, str):
        d["master_users"] = [val] if val.strip() else []
    elif val is None:
        d["master_users"] = []
    elif not isinstance(val, list):
        # Anything weird (dict, number) → reset.
        d["master_users"] = []
    return d


def _migrate_from_1(d: dict) -> dict:
    """v1 → v2 — introduce master_permissions + ui_theme + privacy_mode
    + gesture_profiles_per_app. Convert old kid_mode list to permissions."""
    if "master_permissions" not in d:
        # Old behaviour: settings had a ``kid_mode_list`` of names that
        # were restricted to a safe subset. Map → master_permissions.
        kids = d.pop("kid_mode_list", None) or []
        if isinstance(kids, list) and kids:
            safe = [
                "double_pinch", "swipe_left", "swipe_right",
                "swipe_up", "swipe_down", "peace", "three_up",
                "thumbs_up", "thumbs_down", "wave",
            ]
            d["master_permissions"] = {
                str(k).strip().lower(): list(safe) for k in kids
                if str(k).strip()
            }
        else:
            d["master_permissions"] = {}
    d.setdefault("ui_theme", "dark")
    d.setdefault("privacy_mode", False)
    d.setdefault("gesture_profiles_per_app", {})
    return d


_MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    0: _migrate_from_0,
    1: _migrate_from_1,
}


# ── public API ────────────────────────────────────────────────────


def current_version() -> int:
    return CURRENT_VERSION


def detect_version(d: dict) -> int:
    """Return the on-disk schema version. Absent / non-int → 0."""
    v = d.get(_SCHEMA_KEY)
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def ensure_current(d: dict | None) -> dict:
    """Bring ``d`` up to the current schema version. Mutates + returns.

    Missing defaults are filled in *after* migration so user-set keys
    aren't overwritten.
    """
    if d is None:
        d = {}
    if not isinstance(d, dict):
        d = {}
    cur = detect_version(d)
    while cur < CURRENT_VERSION:
        fn = _MIGRATIONS.get(cur)
        if fn is None:
            log.warning("[settings_schema] no migration from v%d", cur)
            break
        try:
            d = fn(d)
        except Exception as e:
            log.warning("[settings_schema] migration v%d → v%d failed: %s",
                        cur, cur + 1, e)
            break
        cur += 1
    # Stamp the version + fill any missing defaults.
    d[_SCHEMA_KEY] = CURRENT_VERSION
    for k, v in _DEFAULTS.items():
        d.setdefault(k, v)
    return d


def schema_status(d: dict | None = None) -> dict:
    """Diagnostic — explains current version + migration gap."""
    if d is None:
        try:
            from core import settings as _settings
            d = _settings.get_settings().all()
        except Exception:
            d = {}
    on_disk = detect_version(d)
    missing = [k for k in _DEFAULTS if k not in d]
    return {
        "current_version": CURRENT_VERSION,
        "on_disk_version": on_disk,
        "needs_migration": on_disk < CURRENT_VERSION,
        "missing_defaults": missing,
    }
