"""Macros — chain multiple skills into a single voice command.

The macro book is JSON at ``data/macros.json``. Each macro has a
``description`` and a list of ``steps``, where each step is
``{"skill": <registered name>, "slots": {...}}``. Slots are optional.

The engine fetches each skill from the global registry, calls its
handler with the supplied slots, and concatenates the returned strings
into one summary reply. Failures in one step never abort the chain —
the macro continues so the user still gets the rest of the routine.

Distinct from ``skills/automation_skill.py`` ``routine_*`` skills,
which schedule cron-style automation. Macros run NOW, on demand.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from typing import Optional

from core.skill_registry import skill, get_skill

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MACROS_PATH = os.path.join(_ROOT, "data", "macros.json")

_CACHE_LOCK = threading.Lock()
_CACHE: Optional[dict] = None


def _load_macros(force: bool = False) -> dict:
    """Read data/macros.json into memory. Drops any ``_comment`` keys.
    Cached so disk I/O doesn't happen on every invocation."""
    global _CACHE
    with _CACHE_LOCK:
        if _CACHE is not None and not force:
            return _CACHE
        if not os.path.exists(_MACROS_PATH):
            _CACHE = {}
            return _CACHE
        try:
            with open(_MACROS_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            log.warning("[macros] %s parse failed: %s", _MACROS_PATH, e)
            _CACHE = {}
            return _CACHE
        _CACHE = {k: v for k, v in raw.items() if not k.startswith("_")}
        return _CACHE


def _resolve_macro_name(query: str) -> Optional[str]:
    """Map user-spoken text to a macro key. Tries: exact match, slug match
    (spaces → underscores), then substring."""
    if not query:
        return None
    macros = _load_macros()
    q = query.strip().lower()
    if q in macros:
        return q
    slug = re.sub(r"\s+", "_", q)
    if slug in macros:
        return slug
    for name in macros:
        if name.replace("_", " ") == q:
            return name
    # Substring (most specific first to avoid "end" matching "end_of_day"
    # AND "weekend").
    for name in sorted(macros, key=len, reverse=True):
        if q in name.replace("_", " ") or name.replace("_", " ") in q:
            return name
    return None


def _strip_run_verb(text: str) -> str:
    """Strip leading 'run macro' / 'macro' / 'execute' tokens."""
    if not text:
        return ""
    return re.sub(
        r"^(?:please\s+)?"
        r"(?:run|execute|start|do|trigger|fire|chala?o|chala\s+do|macro\s+chala?o)\s+"
        r"(?:macro\s+|routine\s+)?",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    ).strip(" ?:,")


# ── run_macro ──────────────────────────────────────────────────────


@skill(
    name="run_macro",
    description="Execute a saved macro from data/macros.json (a chain of skills).",
    patterns=[
        "run macro", "execute macro", "macro chalao", "macro chalu karo",
        "run macro morning routine", "morning routine chalao",
        "macro morning routine",
        "run macro focus deep", "focus deep chalao",
        "macro focus deep",
        "run macro end of day", "end of day chalao",
        "macro end of day",
        "run macro media break", "media break chalao",
        "trigger morning routine", "start focus deep",
        "do my morning routine", "kick off morning routine",
    ],
    required_entities=[],
)
def run_macro(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    query = _strip_run_verb(text)
    if not query:
        return ("Kaunsa macro chalana hai? Available: "
                + ", ".join(sorted(_load_macros().keys()) or ["(none — data/macros.json khaali hai)"]))
    macro_name = _resolve_macro_name(query)
    if not macro_name:
        avail = ", ".join(sorted(_load_macros().keys())) or "(none)"
        return f"'{query}' naam ka macro nahi mila. Available: {avail}"
    macro = _load_macros()[macro_name]
    steps = macro.get("steps") or []
    if not steps:
        return f"Macro {macro_name!r} mein koi steps nahi hain."

    lines = [f"▶ Macro: {macro_name}"]
    if macro.get("description"):
        lines.append(f"  ({macro['description']})")

    for i, step in enumerate(steps, 1):
        sk_name = step.get("skill")
        sk_slots = dict(step.get("slots") or {})
        if not sk_name:
            lines.append(f"  {i}. (no skill specified — skipped)")
            continue
        sk = get_skill(sk_name)
        if sk is None:
            lines.append(f"  {i}. {sk_name}: ✗ skill not registered")
            continue
        try:
            result = sk.run(sk_slots)
            first_line = (result or "").splitlines()[0] if result else "(no output)"
            lines.append(f"  {i}. {sk_name}: {first_line}")
        except Exception as e:
            lines.append(f"  {i}. {sk_name}: ✗ {type(e).__name__}: {e}")
    return "\n".join(lines)


# ── list_macros ────────────────────────────────────────────────────


@skill(
    name="list_macros",
    description="List every macro saved in data/macros.json.",
    patterns=[
        "list macros", "show macros", "available macros", "what macros",
        "macros dikhao", "kaunse macros hain", "macro list",
        "which macros are available",
    ],
    required_entities=[],
)
def list_macros(_slots: dict) -> str:
    macros = _load_macros()
    if not macros:
        return ("Koi macro defined nahi hai. "
                "Edit kar data/macros.json or run 'reload macros'.")
    lines = [f"{len(macros)} macro(s) available:"]
    for name in sorted(macros):
        m = macros[name]
        desc = m.get("description") or "(no description)"
        n_steps = len(m.get("steps") or [])
        lines.append(f"  • {name:18s} ({n_steps} steps) — {desc}")
    return "\n".join(lines)


# ── reload_macros ──────────────────────────────────────────────────


@skill(
    name="reload_macros",
    description="Reload macros from disk (after editing data/macros.json).",
    patterns=[
        "reload macros", "macros reload karo", "refresh macros",
        "macro list reload", "reload macro book",
    ],
    required_entities=[],
)
def reload_macros(_slots: dict) -> str:
    macros = _load_macros(force=True)
    return f"Reloaded — {len(macros)} macros available."
