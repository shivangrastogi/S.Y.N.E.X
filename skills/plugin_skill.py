"""Voice commands for the plugin marketplace.

Plugins live under data/plugins/<name>/skill.py and stay dormant until
explicitly enabled. New skills they register go into the global registry
so the brain routes to them like any built-in.

Skills:
  * ``plugin_list``      — discovered plugins + enabled/loaded state
  * ``plugin_enable``    — enable + load a plugin by name
  * ``plugin_disable``   — disable (restart for full unload)
  * ``plugin_path``      — print the plugins folder path
  * ``plugin_load_all``  — load every enabled plugin (idempotent)
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _extract(text: str, *triggers: str) -> str:
    if not text:
        return ""
    s = text.strip()
    sl = s.lower()
    for trig in sorted(triggers, key=len, reverse=True):
        if sl.startswith(trig):
            return s[len(trig):].strip(" .,?\"'")
    return ""


@skill(
    name="plugin_list",
    description="List discovered AERIS plugins under data/plugins/.",
    patterns=[
        "list plugins", "show plugins", "plugins dikhao",
        "what plugins are available", "plugin list",
        "kaunse plugins hain",
    ],
    required_entities=[],
)
def plugin_list(_slots: dict) -> str:
    try:
        from core.plugin_loader import list_plugins, plugin_dir
    except Exception as e:
        return f"plugin_loader load fail: {e}"
    rows = list_plugins()
    if not rows:
        return (f"Koi plugin nahi mila under {plugin_dir()}. "
                f"Drop <name>/skill.py there + 'enable plugin <name>'.")
    lines = [f"{len(rows)} plugin(s) discovered:"]
    for r in rows:
        flags = ("ENABLED" if r["enabled"] else "disabled")
        if r["loaded"]:
            flags += "+loaded"
        elif r["enabled"]:
            flags += " (load failed?)"
        lines.append(f"  • {r['name']:24s} {flags:24s} {r['path']}")
    return "\n".join(lines)


@skill(
    name="plugin_enable",
    description="Enable a plugin by name (also loads it now if possible).",
    patterns=[
        "enable plugin", "plugin enable",
        "plugin chalu karo", "activate plugin",
        "enable plugin demo",
    ],
    required_entities=[],
)
def plugin_enable(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract(text, "enable plugin", "plugin enable",
                    "activate plugin", "plugin chalu karo")
    if not name:
        return "Format: 'enable plugin <name>'."
    try:
        from core.plugin_loader import enable
    except Exception as e:
        return f"plugin_loader load fail: {e}"
    ok, msg = enable(name)
    return msg


@skill(
    name="plugin_disable",
    description="Disable a plugin (won't load on next restart).",
    patterns=[
        "disable plugin", "plugin disable",
        "plugin band karo", "deactivate plugin",
        "disable plugin demo",
    ],
    required_entities=[],
)
def plugin_disable(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    name = _extract(text, "disable plugin", "plugin disable",
                    "deactivate plugin", "plugin band karo")
    if not name:
        return "Format: 'disable plugin <name>'."
    try:
        from core.plugin_loader import disable
    except Exception as e:
        return f"plugin_loader load fail: {e}"
    ok, msg = disable(name)
    return msg


@skill(
    name="plugin_path",
    description="Print the plugins folder absolute path.",
    patterns=[
        "plugin path", "plugin folder", "plugins kahan hai",
        "where are plugins",
    ],
    required_entities=[],
)
def plugin_path(_slots: dict) -> str:
    try:
        from core.plugin_loader import plugin_dir
    except Exception as e:
        return f"plugin_loader load fail: {e}"
    return f"Plugins folder: {plugin_dir()}"


@skill(
    name="plugin_load_all",
    description="Load every enabled plugin (idempotent).",
    patterns=[
        "load all plugins", "load plugins",
        "plugins load karo", "load enabled plugins",
    ],
    required_entities=[],
)
def plugin_load_all(_slots: dict) -> str:
    try:
        from core.plugin_loader import load_enabled
    except Exception as e:
        return f"plugin_loader load fail: {e}"
    n = load_enabled()
    return f"Loaded {n} enabled plugin(s)."
