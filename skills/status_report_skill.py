"""\"How are you doing?\" — unified self-status of AERIS.

One spoken line covering LLM reachability, memory pressure, and recent activity.
Distinct from `diagnostics` (which dumps subsystem detail) — this is the quick
"are you healthy?" check.

Examples:
    "how are you doing"
    "are you ok"
    "system status"
    "tum kaise ho"
    "sab theek hai"
    "health check"
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="status_report",
    description="One-line health summary: LLM, memory pressure, recent activity.",
    patterns=[
        "how are you doing", "are you okay",
        "status report", "how's it going",
        "tum kaise ho", "sab theek hai", "aap kaise ho",
        "are you healthy", "you good",
    ],
    required_entities=[],
)
def status_report(_slots: dict) -> str:
    try:
        from core.status_report import summarize_status
        return summarize_status(window_h=1.0)
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[status_report] failed: %s", e)
        return "Main theek hoon, sir — par detailed status abhi nahi nikal paya."
