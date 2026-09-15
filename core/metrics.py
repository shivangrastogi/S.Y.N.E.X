"""Unified metrics façade.

Three modules grew up around the structured event stream:

  * ``activity_digest`` — skill-dispatch counts, latency, last_dispatch, chip.
  * ``change_log``      — multi-category "what changed" narrative.
  * ``telemetry``       — gesture / workspace / memo / KG / face tallies.

Consumers (the ``/metrics`` endpoint, a future dashboard, a "stats" skill)
shouldn't need to know which module owns which number. This façade is the one
front door: ``snapshot(window_h)`` returns everything, and the thin wrappers
re-export the most-used calls so callers import one module.

Pure aggregation — every section is best-effort so one busted subsystem can't
blank the whole snapshot.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


def _safe(fn, default):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        log.debug("[metrics] section failed: %s", e)
        return default


def snapshot(window_h: float = 24.0, **kw) -> dict:
    """One consolidated metrics blob across all telemetry sources."""
    from core import activity_digest as ad
    from core import change_log as cl

    return {
        "window_h":      window_h,
        "digest":        _safe(lambda: ad.digest(window_h, **kw), {}),
        "changes":       _safe(lambda: cl.changes(window_h, **kw), {}),
        "last_dispatch": _safe(lambda: ad.last_dispatch(window_h, **kw), None),
        "summary":       _safe(lambda: ad.summarize(window_h, **kw), ""),
        "narrative":     _safe(lambda: cl.summarize_changes(window_h, **kw), ""),
        "totals":        _safe(_legacy_totals, {}),
    }


def _legacy_totals() -> dict:
    """Pull the non-event tallies from the older telemetry module."""
    from core import telemetry as t
    out: dict = {}
    for name in ("workspace_totals", "memo_count", "journal_count",
                 "kg_size", "face_count"):
        fn = getattr(t, name, None)
        if callable(fn):
            out[name] = _safe(fn, None)
    return out


# ── thin re-exports so callers import one module ──────────────────────── #


def digest(window_h: float = 24.0, **kw) -> dict:
    from core import activity_digest as ad
    return ad.digest(window_h, **kw)


def summarize(window_h: float = 24.0, **kw) -> str:
    from core import activity_digest as ad
    return ad.summarize(window_h, **kw)


def changes(window_h: float = 24.0, **kw) -> dict:
    from core import change_log as cl
    return cl.changes(window_h, **kw)


def last_dispatch(window_h: float = 24.0, **kw):
    from core import activity_digest as ad
    return ad.last_dispatch(window_h, **kw)


def format_chip(ev: Optional[dict]) -> str:
    from core import activity_digest as ad
    return ad.format_chip(ev)
