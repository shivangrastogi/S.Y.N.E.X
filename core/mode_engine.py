"""Modes / Scenes engine — one voice command → many actions.

A *mode* is a user-named bundle of skill steps: "work mode" might close
distracting apps, set DND, and bump brightness. Unlike ``chain_engine``
(which fires follow-ups when a trigger event happens), modes are activated
BY NAME on demand: "work mode chalu karo" / "work mode off".

Reads ``data/modes.json``; remembers what's active in ``data/mode_state.json``
so a mode survives a restart and ``deactivate`` can reverse it.

Design mirrors chain_engine: each step is ``{"skill": name, "slots": {...}}``
dispatched through the skill registry. The dispatcher is injectable so unit
tests never fire real actions.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_MODES_PATH = _ROOT / "data" / "modes.json"
_STATE_PATH = _ROOT / "data" / "mode_state.json"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _registry_dispatch(skill_name: str, slots: dict) -> str:
    """Default dispatcher — run a skill by name via the registry."""
    try:
        from core.skill_registry import get_skill
    except Exception as e:  # pragma: no cover - import guard
        return f"registry import fail: {e}"
    sk = get_skill(skill_name)
    if sk is None:
        return f"(skill {skill_name!r} not registered)"
    try:
        return (sk.run(dict(slots)) or "").strip() or "(no output)"
    except Exception as e:
        return f"ERR: {e}"


class ModeEngine:
    def __init__(self, dispatch: Optional[Callable[[str, dict], str]] = None,
                 modes_path: Optional[Path] = None,
                 state_path: Optional[Path] = None):
        self._lock = threading.RLock()
        self._dispatch = dispatch or _registry_dispatch
        self._modes_path = Path(modes_path) if modes_path else _MODES_PATH
        self._state_path = Path(state_path) if state_path else _STATE_PATH
        self._modes: dict[str, dict] = {}
        self.reload()

    # ── loading ───────────────────────────────────────────────────
    def reload(self) -> int:
        with self._lock:
            self._modes = self._load()
            return len(self._modes)

    def _load(self) -> dict[str, dict]:
        if not self._modes_path.exists():
            return {}
        try:
            raw = json.loads(self._modes_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("[mode_engine] parse failed: %s", e)
            return {}
        out: dict[str, dict] = {}
        for key, v in raw.items():
            if key.startswith("_") or not isinstance(v, dict):
                continue
            on = v.get("on") or []
            if not isinstance(on, list) or not on:
                continue
            out[key] = {
                "description": str(v.get("description", "")),
                "aliases": [str(a) for a in (v.get("aliases") or [])] + [key],
                "on": on,
                "off": v.get("off") or [],
            }
        return out

    def list_modes(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._modes)

    # ── state ─────────────────────────────────────────────────────
    def _read_state(self) -> set[str]:
        if not self._state_path.exists():
            return set()
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return set(data.get("active", []))
        except Exception:
            return set()

    def _write_state(self, active: set[str]) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps({"active": sorted(active)}, indent=2),
                encoding="utf-8")
        except Exception as e:  # pragma: no cover - disk guard
            log.debug("[mode_engine] state write failed: %s", e)

    def active(self) -> list[str]:
        return sorted(self._read_state())

    # ── resolution ────────────────────────────────────────────────
    def resolve(self, text: str) -> Optional[str]:
        """Find which mode a phrase refers to, by name or alias."""
        nt = _norm(text)
        if not nt:
            return None
        with self._lock:
            best = None
            best_len = 0
            for key, m in self._modes.items():
                for alias in m["aliases"]:
                    na = _norm(alias)
                    if na and na in nt and len(na) > best_len:
                        best, best_len = key, len(na)
        return best

    # ── run ───────────────────────────────────────────────────────
    def _run_steps(self, steps: list) -> list[str]:
        logs: list[str] = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            name = step.get("skill")
            if not name:
                continue
            res = self._dispatch(str(name), dict(step.get("slots") or {}))
            logs.append(f"{name}: {res[:60]}")
        return logs

    def activate(self, name: str) -> str:
        with self._lock:
            mode = self._modes.get(name)
            if not mode:
                return None
            active = self._read_state()
            already = name in active
            logs = self._run_steps(mode["on"])
            active.add(name)
            self._write_state(active)
        label = name.replace("_", " ").title()
        head = f"'{label}' mode {'phir se ' if already else ''}ON."
        detail = f" ({len(logs)} step{'s' if len(logs) != 1 else ''})" if logs else ""
        return head + detail

    def deactivate(self, name: str) -> str:
        with self._lock:
            mode = self._modes.get(name)
            if not mode:
                return None
            active = self._read_state()
            was_active = name in active
            logs = self._run_steps(mode["off"])
            active.discard(name)
            self._write_state(active)
        label = name.replace("_", " ").title()
        if not was_active:
            base = f"'{label}' mode already off tha."
        else:
            base = f"'{label}' mode OFF."
        if not mode["off"]:
            base += " (isko reverse karne ke steps set nahi the.)"
        return base


_DEFAULT: Optional[ModeEngine] = None


def get_mode_engine() -> ModeEngine:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ModeEngine()
    return _DEFAULT
