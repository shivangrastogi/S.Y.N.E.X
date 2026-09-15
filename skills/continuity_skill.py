"""Continuity status by voice — "kaunsi body active hai?"

Read-only window into the ek-mind-do-body layer
(docs/CONTINUITY_ARCHITECTURE.md): which device the DeviceRegistry
considers active, how fresh each body's beat is, and whether the phone
holds a memory slice worth of personal facts.
"""
from __future__ import annotations

import logging
import time

from core.skill_registry import skill

log = logging.getLogger(__name__)


def _age(ts: float) -> str:
    s = max(0, int(time.time() - ts))
    if s < 60:
        return f"{s}s pehle"
    if s < 3600:
        return f"{s // 60} min pehle"
    return f"{s // 3600} ghante pehle"


@skill(
    name="continuity_status",
    description="Report which body (laptop/phone) is active and continuity health.",
    patterns=[
        "continuity status", "continuity check",
        "kaunsi body active hai", "phone active hai kya",
        "kis device pe hoon", "dono device ka status",
        "body status", "mind body status",
    ],
    required_entities=[],
)
def continuity_status(slots: dict) -> str:
    try:
        from core.continuity import get_router, memory_slice
        r = get_router()
        active = r.registry.active_device()
        snap = r.registry.snapshot()
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[continuity_status] failed: %s", e)
        return "Continuity layer abhi read nahi ho paya, sir."

    parts = [f"Abhi active body {'phone' if active == 'phone' else 'laptop'} "
             f"hai, sir"]
    phone = snap.get("phone")
    if phone:
        parts.append(f"phone ka aakhri beat {phone['state']} tha, "
                     f"{_age(phone['ts'])}")
    else:
        parts.append("phone se abhi tak koi presence beat nahi aaya")
    try:
        n = len(memory_slice().get("facts", []))
        if n:
            parts.append(f"memory slice mein {n} personal facts sync-ready hain")
    except Exception:
        pass
    return ". ".join(parts) + "."
