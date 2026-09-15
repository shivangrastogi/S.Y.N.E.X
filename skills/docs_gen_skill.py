"""Voice command to regenerate the skill catalog markdown."""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="regenerate_skill_docs",
    description="Regenerate docs/SKILLS.md from the live skill registry.",
    patterns=[
        "regenerate skill docs", "regen skill docs",
        "rebuild skill docs", "regenerate skills md",
        "skill docs regen", "update skill docs",
        "docs regen", "regenerate docs",
    ],
    required_entities=[],
)
def regenerate_skill_docs(_slots: dict) -> str:
    try:
        from core.docs_gen import write_skill_docs
    except Exception as e:
        return f"docs_gen load fail: {e}"
    info = write_skill_docs()
    if not info["ok"]:
        return info.get("msg") or "Regen fail."
    return (f"Wrote {info['skills']} skill(s) across {info['categories']} "
            f"categor(ies) to {info['path']} ({info['bytes']} bytes).")
