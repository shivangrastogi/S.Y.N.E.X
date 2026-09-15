"""Unified self-status — "AERIS, how are you doing?"

Composes the three health signals a user actually cares about into one spoken
line:

  * **LLM** — is Ollama reachable + model pulled (``llm_chat.probe_cached``)?
  * **Memory pressure** — RSS + the ResourceMonitor's level (ok/warning/critical).
  * **Activity** — how busy has it been (the I8 metrics façade digest).

Every signal is best-effort and independently guarded, so a missing subsystem
degrades one clause rather than blanking the whole report. Pure aggregation +
formatting — unit-testable by monkeypatching the three sources.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


def _llm_section() -> dict:
    try:
        from core.llm_chat import probe_cached
        p = probe_cached(ttl=15.0)
        return {"status": p.get("status"), "model": p.get("model")}
    except Exception as e:
        log.debug("[status] llm section failed: %s", e)
        return {"status": "unknown", "model": None}


def _resource_section() -> dict:
    try:
        from core.resource_monitor import get_monitor
        m = get_monitor()
        samples = m.snapshot()
        rss_mb = round(samples[-1].rss_bytes / (1024 * 1024), 0) if samples else None
        return {"pressure": m.level_name(), "rss_mb": rss_mb}
    except Exception as e:
        log.debug("[status] resource section failed: %s", e)
        return {"pressure": "unknown", "rss_mb": None}


def _activity_section(window_h: float) -> dict:
    try:
        from core.metrics import digest
        d = digest(window_h)
        return {"total": d.get("total", 0), "unique": d.get("unique", 0)}
    except Exception as e:
        log.debug("[status] activity section failed: %s", e)
        return {"total": 0, "unique": 0}


def system_status(window_h: float = 1.0) -> dict:
    """One consolidated health blob across LLM / memory / activity."""
    return {
        "llm":      _llm_section(),
        "resource": _resource_section(),
        "activity": _activity_section(window_h),
    }


def summarize_status(window_h: float = 1.0) -> str:
    """Spoken Hinglish one-liner of overall health."""
    s = system_status(window_h)
    parts: list[str] = []

    # Resources
    res = s["resource"]
    pressure = res.get("pressure")
    rss = res.get("rss_mb")
    if pressure and pressure != "unknown":
        nice = {"ok": "All good", "normal": "All good",
                "warning": "Memory thoda high", "critical": "Memory pressure high"}.get(
            pressure, pressure)
        if rss:
            parts.append(f"{nice} (RSS {int(rss)} MB)")
        else:
            parts.append(nice)

    # LLM
    llm = s["llm"].get("status")
    if llm == "ok":
        parts.append("LLM chat ready")
    elif llm == "no_model":
        parts.append(f"Ollama up par model pull karna hai")
    elif llm == "unreachable":
        parts.append("LLM offline (Ollama band)")

    # Activity
    act = s["activity"]
    if act.get("total"):
        parts.append(f"pichhle ghante {act['total']} command across {act['unique']} skills")

    if not parts:
        return "Sab theek lag raha hai, sir — detailed metrics abhi available nahi."
    return "Status: " + "; ".join(parts) + "."
