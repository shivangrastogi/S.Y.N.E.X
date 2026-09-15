"""Dependency validator voice surface."""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="dep_check",
    description="Report every optional dependency + which skills go dark "
                "when it's missing.",
    patterns=[
        "dep check", "dependency check", "check dependencies",
        "dependencies dikhao", "what is missing",
        "missing dependencies", "dep status",
    ],
    required_entities=[],
)
def dep_check(_slots: dict) -> str:
    try:
        from core.dep_validator import list_deps, health_score
    except Exception as e:
        return f"dep_validator load fail: {e}"
    rows = list_deps()
    score = health_score()
    installed = sum(1 for r in rows if r["installed"])
    missing = [r for r in rows if not r["installed"]]
    lines = [f"Dependency health: {score}/100 · {installed}/{len(rows)} installed."]
    if missing:
        lines.append("Missing:")
        for r in missing:
            n = r["affected_count"]
            label = f"{n} skill(s)" if n else "no skills affected"
            lines.append(f"  • {r['dep']:24s} ({label})  →  {r['fix']}")
    else:
        lines.append("All optional dependencies are installed. ")
    return "\n".join(lines)


@skill(
    name="dep_skills_dark",
    description="List skills that are currently broken because of a "
                "missing optional dependency.",
    patterns=[
        "dark skills", "broken skills", "skills dark",
        "what skills are broken", "kya kya skills dark hain",
        "list broken skills",
    ],
    required_entities=[],
)
def dep_skills_dark(_slots: dict) -> str:
    try:
        from core.dep_validator import missing_skills
    except Exception as e:
        return f"dep_validator load fail: {e}"
    dark = missing_skills()
    if not dark:
        return "Koi skill broken nahi — saari deps installed hain."
    lines = [f"{len(dark)} skill(s) dark due to missing deps:"]
    for name in sorted(dark):
        deps = ", ".join(dark[name])
        lines.append(f"  • {name:30s} needs: {deps}")
    return "\n".join(lines)
