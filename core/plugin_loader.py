"""External plugin loader — load user/community skills from a sandbox dir.

Plugins live under ``data/plugins/<name>/skill.py``. Each file uses the
same ``@skill`` decorator as the built-in skills. A plugin can ship
additional Python modules in the same directory and import them with
``from . import helper`` — we set up the package shim transparently.

Allowlist: only plugins whose name appears in settings ``plugins_enabled``
get loaded. New plugins drop into the directory but stay dormant until
the user explicitly says "enable plugin <name>". This protects the
brain from misbehaving / malicious skills.

Public API:
    list_plugins() -> list[dict]   # discovered, with status flag
    enable(name)
    disable(name)
    load_enabled() -> int          # discover + import every enabled plugin
    plugin_dir() -> str            # absolute path to data/plugins
"""
from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PLUGIN_DIR = _ROOT / "data" / "plugins"

# Package prefix under which we register loaded plugin modules. Lets
# plugins do `from aeris_plugins.<name> import helper` if they ship
# multi-file packages.
_PKG = "aeris_plugins"

_LOADED: set[str] = set()


def plugin_dir() -> str:
    _PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    return str(_PLUGIN_DIR)


def _enabled_set() -> set[str]:
    try:
        from core import settings as _settings
        raw = _settings.get("plugins_enabled") or []
    except Exception:
        raw = []
    if not isinstance(raw, list):
        return set()
    return {str(x).strip().lower() for x in raw if str(x).strip()}


def _save_enabled(names: set[str]) -> None:
    try:
        from core import settings as _settings
        _settings.set_("plugins_enabled", sorted(names))
    except Exception:
        pass


def _discover_dirs() -> list[Path]:
    if not _PLUGIN_DIR.is_dir():
        return []
    out: list[Path] = []
    for child in _PLUGIN_DIR.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith((".", "_")):
            continue
        if (child / "skill.py").is_file():
            out.append(child)
    return sorted(out)


def list_plugins() -> list[dict]:
    enabled = _enabled_set()
    rows: list[dict] = []
    for d in _discover_dirs():
        name = d.name
        rows.append({
            "name":     name,
            "path":     str(d),
            "enabled":  name.lower() in enabled,
            "loaded":   name in _LOADED,
            "has_readme": (d / "README.md").is_file(),
        })
    return rows


def enable(name: str) -> tuple[bool, str]:
    name = (name or "").strip().lower()
    if not name:
        return False, "Name nahi diya."
    discovered = {p.name.lower() for p in _discover_dirs()}
    if name not in discovered:
        return False, (f"'{name}' plugin nahi mila under {plugin_dir()}.")
    enabled = _enabled_set()
    enabled.add(name)
    _save_enabled(enabled)
    loaded = load_one(name)
    return True, (f"Enabled '{name}'." + (" (loaded)" if loaded else " (failed to load)"))


def disable(name: str) -> tuple[bool, str]:
    name = (name or "").strip().lower()
    if not name:
        return False, "Name nahi diya."
    enabled = _enabled_set()
    if name not in enabled:
        return False, f"'{name}' was not enabled."
    enabled.discard(name)
    _save_enabled(enabled)
    # We can't unregister already-loaded skills cleanly (the @skill
    # decorator mutated the global REGISTRY at import time). Tell the
    # user to restart for a clean state.
    return True, (f"Disabled '{name}'. Restart AERIS for the skill to "
                  f"fully unregister.")


def load_one(name: str) -> bool:
    """Import a single plugin by name. Returns True on success."""
    name = (name or "").strip()
    if not name:
        return False
    d = _PLUGIN_DIR / name
    skill_py = d / "skill.py"
    if not skill_py.is_file():
        log.info("[plugins] '%s' has no skill.py", name)
        return False
    mod_name = f"{_PKG}.{name}"
    if mod_name in sys.modules:
        # Already imported; skip.
        _LOADED.add(name)
        return True
    try:
        # Make sure the parent package exists as a virtual namespace.
        if _PKG not in sys.modules:
            spec = importlib.util.spec_from_loader(_PKG, loader=None)
            pkg = importlib.util.module_from_spec(spec)
            pkg.__path__ = [str(_PLUGIN_DIR)]    # type: ignore
            sys.modules[_PKG] = pkg
        spec = importlib.util.spec_from_file_location(
            mod_name, skill_py,
            submodule_search_locations=[str(d)],
        )
        if spec is None or spec.loader is None:
            log.warning("[plugins] cannot build spec for %s", skill_py)
            return False
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        _LOADED.add(name)
        log.info("[plugins] loaded plugin '%s'", name)
        return True
    except Exception as e:
        log.warning("[plugins] failed to load '%s': %s", name, e)
        return False


def load_enabled() -> int:
    """Walk the plugins dir and import every enabled plugin. Idempotent."""
    enabled = _enabled_set()
    n = 0
    for d in _discover_dirs():
        if d.name.lower() in enabled:
            if load_one(d.name):
                n += 1
    return n
