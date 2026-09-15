"""Voice surface for the settings schema."""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="settings_schema_status",
    description="Report current settings schema version + whether a "
                "migration is pending.",
    patterns=[
        "settings schema status", "settings version",
        "schema status", "settings migration status",
        "settings schema kya hai",
    ],
    required_entities=[],
)
def settings_schema_status(_slots: dict) -> str:
    try:
        from core.settings_schema import schema_status, current_version
    except Exception as e:
        return f"settings_schema load fail: {e}"
    st = schema_status()
    missing = ", ".join(st["missing_defaults"]) if st["missing_defaults"] else "(none)"
    return (f"Settings schema v{st['on_disk_version']} → "
            f"current v{st['current_version']}. "
            f"Migration pending: {st['needs_migration']}. "
            f"Missing defaults: {missing}.")


@skill(
    name="settings_schema_migrate",
    description="Run pending settings.json migrations + fill any missing "
                "default keys. Idempotent — safe to call repeatedly.",
    patterns=[
        "migrate settings", "settings migrate karo",
        "run settings migration", "upgrade settings",
        "settings schema upgrade",
    ],
    required_entities=[],
)
def settings_schema_migrate(_slots: dict) -> str:
    try:
        from core import settings as _settings
        from core.settings_schema import ensure_current
    except Exception as e:
        return f"settings load fail: {e}"
    store = _settings.get_settings()
    before = dict(store.all())
    upgraded = ensure_current(before)
    # Write back any new / changed keys.
    changed = 0
    for k, v in upgraded.items():
        if before.get(k) != v:
            store.set(k, v)
            changed += 1
    return f"Migrated — {changed} key(s) updated/added."
