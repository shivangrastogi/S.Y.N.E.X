"""Activity digest — "what did you do?" from the structured event log.

AERIS emits one JSON line per dispatched skill via ``log_setup.event(
"skill_dispatch", ...)``. This module reads those lines back, windows them
by wall-clock time, and rolls them into a human Hinglish summary.

Two sources, merged and de-duplicated by ``ts``:

  1. **The rotating file** ``data/logs/aeris.log`` (+ its ``.1 … .5``
     backups) — durable across restarts. Each line is
     ``<asctime> <level> <logger> :: {json...}``; we slice from the first
     ``{`` so the stdlib log prefix is ignored.
  2. **The in-memory ring buffer** (``log_setup.snapshot_events()``) — the
     newest events that may not yet matter for the window but are free to
     fold in.

Pure functions, no Qt, no global state — mirrors ``core/telemetry.py`` so
the GUI dashboard and the voice skill can both consume from here.
"""
from __future__ import annotations

import glob
import json
import logging
import os
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_LOG_PATH = _ROOT / "data" / "logs" / "aeris.log"


# ── reading ────────────────────────────────────────────────────────── #


def _parse_line(line: str) -> Optional[dict]:
    """Extract the JSON payload from one log line, or None if it isn't one.

    Lines look like ``2026-06-26T12:00:00 INFO  aeris.event :: {"ts":...}``.
    We find the first ``{`` and json-decode the remainder so the stdlib
    formatter prefix never trips us up.
    """
    brace = line.find("{")
    if brace == -1:
        return None
    try:
        obj = json.loads(line[brace:])
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) and "event" in obj else None


def _iter_file_events(log_path: Optional[os.PathLike | str] = None) -> Iterable[dict]:
    """Yield every parsed event dict from the live log + rotated backups."""
    base = Path(log_path) if log_path else _LOG_PATH
    # Rotated files are base.1 (newest backup) … base.N (oldest). Read oldest
    # → newest so the natural order is chronological; callers window by ts
    # anyway, so exact order is not load-bearing.
    paths = sorted(
        glob.glob(f"{base}.*"),
        key=lambda p: int(p.rsplit(".", 1)[-1]) if p.rsplit(".", 1)[-1].isdigit() else 0,
        reverse=True,
    )
    paths.append(str(base))
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    obj = _parse_line(line)
                    if obj is not None:
                        yield obj
        except FileNotFoundError:
            continue
        except OSError as e:
            log.debug("[activity_digest] could not read %s: %s", p, e)


def read_events(
    window_h: float = 24.0,
    event_name: Optional[str] = "skill_dispatch",
    *,
    log_path: Optional[os.PathLike | str] = None,
    now: Optional[float] = None,
) -> list[dict]:
    """Return events within the last ``window_h`` hours, newest last.

    Merges the rotating file with the in-memory ring buffer and de-dups on
    ``(ts, event, intent)`` so an event present in both isn't counted twice.
    ``event_name=None`` returns every event kind.
    """
    now = time.time() if now is None else now
    cutoff = now - window_h * 3600.0

    seen: set[tuple] = set()
    out: list[dict] = []

    def _consider(ev: dict) -> None:
        if not isinstance(ev, dict):
            return
        if event_name is not None and ev.get("event") != event_name:
            return
        ts = ev.get("ts")
        if not isinstance(ts, (int, float)) or ts < cutoff or ts > now + 1.0:
            return
        key = (round(float(ts), 3), ev.get("event"), ev.get("intent"))
        if key in seen:
            return
        seen.add(key)
        out.append(ev)

    for ev in _iter_file_events(log_path):
        _consider(ev)

    # Fold in the live ring buffer (only meaningful for the real process).
    try:
        from core.log_setup import snapshot_events
        for ev in snapshot_events():
            _consider(ev)
    except Exception:
        pass

    out.sort(key=lambda e: e.get("ts", 0.0))
    return out


# ── rollup ─────────────────────────────────────────────────────────── #


def digest(window_h: float = 24.0, **kw) -> dict:
    """Roll dispatch events up into counts, top skills, and latency stats."""
    events = read_events(window_h, "skill_dispatch", **kw)
    by_intent: Counter = Counter()
    executed = 0
    latencies: list[float] = []
    for ev in events:
        intent = ev.get("intent") or "?"
        by_intent[intent] += 1
        if ev.get("action") == "executed":
            executed += 1
        lat = ev.get("latency_ms")
        if isinstance(lat, (int, float)):
            latencies.append(float(lat))

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else None
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else None

    return {
        "window_h":   window_h,
        "total":      len(events),
        "executed":   executed,
        "unique":     len(by_intent),
        "top":        by_intent.most_common(5),
        "latency_p50_ms": round(p50, 1) if p50 is not None else None,
        "latency_p95_ms": round(p95, 1) if p95 is not None else None,
    }


def last_dispatch(
    within_h: float = 24.0,
    **kw,
) -> Optional[dict]:
    """Most recent ``skill_dispatch`` event in the window, or None.

    A non-engine consumer (telemetry dashboard, ``/metrics``, the diff skill)
    that doesn't hold a live ``JarvisMainEngine`` reference can still recover
    "what fired last" from the durable event stream.
    """
    events = read_events(within_h, "skill_dispatch", **kw)
    return events[-1] if events else None


def format_chip(ev: Optional[dict]) -> str:
    """Render a one-line "which skill fired" chip for a dispatch event.

    Example: ``weather · 0.91 · 12 ms``. Empty string for None so the GUI
    can simply hide the chip when there's nothing to show.
    """
    if not ev:
        return ""
    parts = [str(ev.get("intent") or "?")]
    conf = ev.get("confidence")
    if isinstance(conf, (int, float)):
        parts.append(f"{conf:.2f}")
    if ev.get("action") and ev.get("action") != "executed":
        parts.append(str(ev["action"]))
    lat = ev.get("latency_ms")
    if isinstance(lat, (int, float)):
        parts.append(f"{lat:.0f} ms")
    return " · ".join(parts)


def _fmt_window(window_h: float) -> str:
    if window_h <= 1.0:
        return "last hour" if window_h == 1.0 else f"last {int(window_h * 60)} min"
    if window_h < 24.0:
        h = int(window_h) if float(window_h).is_integer() else round(window_h, 1)
        return f"last {h} hours"
    if window_h == 24.0:
        return "last 24 hours"
    days = window_h / 24.0
    d = int(days) if float(days).is_integer() else round(days, 1)
    return f"last {d} days"


def summarize(window_h: float = 24.0, **kw) -> str:
    """One-paragraph Hinglish summary of dispatch activity in the window."""
    d = digest(window_h, **kw)
    win = _fmt_window(window_h)
    if d["total"] == 0:
        return f"{win.capitalize()} mein koi command nahi chali, sir."

    top_str = ", ".join(f"{name} ({n}x)" for name, n in d["top"])
    parts = [
        f"{win.capitalize()} mein {d['total']} command",
        f"{d['executed']} execute hui" if d["executed"] else None,
        f"across {d['unique']} skills." if d["unique"] > 1 else "ek hi skill.",
    ]
    line = " — ".join(p for p in parts if p)
    out = f"{line} Top: {top_str}."
    if d["latency_p50_ms"] is not None:
        out += f" Median latency {d['latency_p50_ms']:.0f} ms."
    return out
