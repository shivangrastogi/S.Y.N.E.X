"""Cross-skill chain engine — "when X fires, also do Y, Z".

Reads ``data/chains.json``; each chain has a ``trigger`` (gesture name,
custom-gesture token, or skill name) and a ``then`` list of ``{skill,
slots}`` entries to run in order. The gesture engine fans every emit
out to listeners — we register one listener that consults the chain
table and dispatches matching follow-ups.

Loop protection: a chain step that itself triggers another chain is
allowed, but each unique step is rate-limited to once per 1.5 s to
prevent runaway recursion if the user accidentally creates a cycle.

Public API:
    eng = get_chain_engine()
    eng.start()                     # attach listener to GestureEngine
    eng.reload()                    # re-read data/chains.json
    eng.list_chains() -> dict
    eng.fire_for(event_name) -> list[str]   # run matching chains, return logs
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_CHAINS_PATH = _ROOT / "data" / "chains.json"

_RECURSION_GUARD_S = 1.5


class ChainEngine:
    def __init__(self):
        self._lock = threading.RLock()
        self._chains: dict[str, dict] = {}
        self._listener_attached = False
        # name → monotonic ts of last fire (for the loop guard)
        self._last_fired_at: dict[str, float] = {}
        self.reload()

    # ── lifecycle ─────────────────────────────────────────────────

    def reload(self) -> int:
        with self._lock:
            self._chains = self._load()
            return len(self._chains)

    def _load(self) -> dict[str, dict]:
        if not _CHAINS_PATH.exists():
            return {}
        try:
            with open(_CHAINS_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            log.warning("[chain_engine] parse failed: %s", e)
            return {}
        out: dict[str, dict] = {}
        for k, v in raw.items():
            if k.startswith("_") or not isinstance(v, dict):
                continue
            if "trigger" not in v or "then" not in v:
                continue
            steps = v.get("then") or []
            if not isinstance(steps, list):
                continue
            out[k] = {
                "description": str(v.get("description", "")),
                "trigger": str(v["trigger"]),
                "then": steps,
            }
        return out

    def list_chains(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._chains)

    def start(self) -> bool:
        """Subscribe to GestureEngine emits. Idempotent."""
        if self._listener_attached:
            return True
        try:
            from core.gesture_engine import get_gesture_engine
            get_gesture_engine().add_listener(self._on_event)
            self._listener_attached = True
            log.info("[chain_engine] listening on GestureEngine emits.")
            return True
        except Exception as e:
            log.info("[chain_engine] could not attach to gesture engine: %s", e)
            return False

    # ── runtime ───────────────────────────────────────────────────

    def _on_event(self, name: str) -> None:
        try:
            self.fire_for(name)
        except Exception as e:
            log.debug("[chain_engine] fire_for raised: %s", e)

    def fire_for(self, event_name: str) -> list[str]:
        """Run every chain whose trigger matches ``event_name``. Returns
        a list of "[chain] step -> result" log lines for diagnostics."""
        if not event_name:
            return []
        now = time.monotonic()
        last = self._last_fired_at.get(event_name, 0.0)
        if (now - last) < _RECURSION_GUARD_S:
            log.debug("[chain_engine] %s suppressed by recursion guard", event_name)
            return []
        self._last_fired_at[event_name] = now

        with self._lock:
            matched = [(cname, c) for cname, c in self._chains.items()
                       if c.get("trigger") == event_name]
        if not matched:
            return []
        logs: list[str] = []
        for cname, chain in matched:
            for step in (chain.get("then") or []):
                if not isinstance(step, dict):
                    continue
                sk_name = step.get("skill")
                slots = step.get("slots") or {}
                if not sk_name:
                    continue
                result = self._dispatch(str(sk_name), dict(slots))
                logs.append(f"[{cname}] {sk_name} → {result[:80]}")
        return logs

    def _dispatch(self, skill_name: str, slots: dict) -> str:
        try:
            from core.skill_registry import get_skill
        except Exception as e:
            return f"registry import fail: {e}"
        sk = get_skill(skill_name)
        if sk is None:
            return f"(skill {skill_name!r} not registered)"
        try:
            return (sk.run(slots) or "").strip() or "(no output)"
        except Exception as e:
            return f"ERR: {e}"


_DEFAULT: Optional[ChainEngine] = None


def get_chain_engine() -> ChainEngine:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ChainEngine()
    return _DEFAULT
