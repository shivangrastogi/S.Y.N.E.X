"""Telemetry aggregator — pulls usage stats from every observable subsystem.

Pure helper functions — no Qt, no global state. The dashboard widget
(``ui/telemetry_dashboard.py``) and any future text-only summariser
both consume from here.

Sections:
  * skill_counts(window_h)     — skills fired in the last N hours (from gesture_trace)
  * gesture_counts(window_h)   — gesture emits + blocks
  * workspace_totals()         — workspace tracker totals
  * memo_count()               — voice memo file count
  * journal_count()            — journal line count
  * kg_size()                  — knowledge-graph triple count
  * face_count()               — registered faces
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent


def _safe_call(fn):
    try:
        return fn()
    except Exception as e:
        log.debug("[telemetry] %s failed: %s", fn.__name__, e)
        return None


def gesture_events(window_h: float = 1.0) -> list[dict]:
    """Return raw gesture_trace events from the last ``window_h`` hours."""
    try:
        from core import gesture_trace as gt
        events = gt.tail(500)
    except Exception:
        return []
    cutoff = datetime.now() - timedelta(hours=window_h)
    out: list[dict] = []
    for ev in events:
        try:
            ts = datetime.fromisoformat(ev.get("ts", ""))
        except (TypeError, ValueError):
            continue
        if ts >= cutoff:
            out.append(ev)
    return out


def gesture_counts(window_h: float = 1.0) -> dict:
    events = gesture_events(window_h)
    by_name: dict[str, int] = {}
    fired = blocked = 0
    for ev in events:
        n = ev.get("gesture") or "?"
        by_name[n] = by_name.get(n, 0) + 1
        if ev.get("status") == "fired":
            fired += 1
        elif ev.get("status") == "blocked":
            blocked += 1
    ranked = sorted(by_name.items(), key=lambda kv: -kv[1])
    return {
        "total":   len(events),
        "fired":   fired,
        "blocked": blocked,
        "ranked":  ranked,           # [(name, count), ...] desc
        "window_h": window_h,
    }


def skill_counts(window_h: float = 1.0) -> dict:
    """Approx counts of skills triggered by gestures — pulls from
    gesture_trace's 'fired' events + cross-references to DEFAULT_ACTIONS."""
    counts: dict[str, int] = {}
    try:
        from core.gesture_engine import DEFAULT_ACTIONS
    except Exception:
        DEFAULT_ACTIONS = {}
    for ev in gesture_events(window_h):
        if ev.get("status") != "fired":
            continue
        g = ev.get("gesture") or ""
        # Every gesture is also a skill name in our world; fall back to
        # the gesture name itself for action keys not yet wired.
        counts[g] = counts.get(g, 0) + 1
    return {
        "ranked":   sorted(counts.items(), key=lambda kv: -kv[1]),
        "total":    sum(counts.values()),
        "window_h": window_h,
    }


def workspace_totals() -> dict:
    try:
        from core.workspace_tracker import get_workspace_tracker
        t = get_workspace_tracker()
        # Top 5 by time over the last hour.
        text = t.summary(window_s=3600.0)
        return {
            "running": t.is_running(),
            "events":  len(t.recent_events(2000)),
            "summary": text,
        }
    except Exception as e:
        return {"running": False, "events": 0, "summary": f"(workspace tracker error: {e})"}


def memo_count() -> int:
    d = _ROOT / "data" / "notes" / "audio"
    if not d.is_dir():
        return 0
    try:
        return sum(1 for p in d.iterdir() if p.suffix.lower() == ".wav")
    except Exception:
        return 0


def journal_count() -> int:
    p = _ROOT / "data" / "notes" / "journal.md"
    if not p.is_file():
        return 0
    try:
        return sum(1 for line in p.open("r", encoding="utf-8")
                   if line.strip().startswith("- "))
    except Exception:
        return 0


def kg_size() -> int:
    try:
        from core.kg_memory import get_kg
        return len(get_kg().all_triples())
    except Exception:
        return 0


def face_count() -> int:
    try:
        from core.face_recognition import get_registry
        return len(get_registry().all_names())
    except Exception:
        return 0


def snapshot(window_h: float = 1.0) -> dict:
    """Single aggregate for the dashboard / CLI digest."""
    return {
        "gesture":   gesture_counts(window_h),
        "skill":     skill_counts(window_h),
        "workspace": workspace_totals(),
        "memos":     memo_count(),
        "journal":   journal_count(),
        "kg":        kg_size(),
        "faces":     face_count(),
        "window_h":  window_h,
    }
