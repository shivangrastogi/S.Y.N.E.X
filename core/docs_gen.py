"""Auto-generate ``docs/SKILLS.md`` from the live skill registry.

Walks every registered skill, groups them by category (using the same
``_CATEGORIES`` map ``skills/help_catalog`` uses), emits a clean
markdown table. Idempotent — running it twice produces identical bytes.

Public API:
    write_skill_docs(path=None) -> dict   {ok, path, skills, categories}
    default_path() -> Path
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent


def default_path() -> Path:
    return _ROOT / "docs" / "SKILLS.md"


def _category_map() -> dict[str, str]:
    """Mirror ``skills/help_catalog._CATEGORIES``. Inline a fallback so
    we don't crash if help_catalog hasn't been imported yet."""
    try:
        from skills.help_catalog import _CATEGORIES  # type: ignore
        return dict(_CATEGORIES)
    except Exception:
        return {}


def _classify(name: str, cmap: dict[str, str]) -> str:
    if name in cmap:
        return cmap[name]
    # Lightweight name-based fallback
    n = name.lower()
    if n.startswith(("gesture_", "practice_", "custom_gesture")):
        return "Gestures"
    if n.startswith(("tts_", "voice_", "speaker_")):
        return "Voice / STT"
    if n.startswith(("master_", "permission", "face_gate", "register_face")):
        return "Faces / Permissions"
    if n.startswith(("workspace_", "telemetry", "log_digest")):
        return "Telemetry"
    if n.startswith(("plugin_", "chain")):
        return "Extensibility"
    if n.startswith(("sync_", "doc_", "translate")):
        return "Productivity"
    if n.startswith(("hud_", "theme_", "open_", "transcript_", "ar_")):
        return "UI"
    if n.startswith(("phone_", "notification_", "presence_")):
        return "System"
    return "Other"


def write_skill_docs(path: Optional[str] = None) -> dict:
    try:
        from core.skill_registry import all_skills
    except Exception as e:
        return {"ok": False, "msg": f"skill_registry import fail: {e}"}
    cmap = _category_map()
    skills = all_skills()
    by_cat: dict[str, list[tuple[str, str, str]]] = {}
    for name in sorted(skills.keys()):
        sk = skills[name]
        cat = _classify(name, cmap)
        first_pat = (sk.patterns[0] if sk.patterns else "(programmatic)")
        desc = (sk.description or "").strip().replace("\n", " ")
        by_cat.setdefault(cat, []).append((name, desc, first_pat))

    lines: list[str] = [
        "# AERIS skill catalog",
        "",
        f"_Auto-generated from the live skill registry on {datetime.now().isoformat(timespec='seconds')}._",
        "",
        f"**{len(skills)} skills across {len(by_cat)} categories.**",
        "",
        "To regenerate: `regenerate skill docs` (voice) or "
        "`python -c \"from core.docs_gen import write_skill_docs; write_skill_docs()\"`.",
        "",
    ]
    for cat in sorted(by_cat.keys()):
        entries = by_cat[cat]
        lines.append(f"## {cat}  ({len(entries)})")
        lines.append("")
        lines.append("| Skill | Example trigger | Description |")
        lines.append("|---|---|---|")
        for name, desc, pat in entries:
            # Markdown-escape pipes inside cells.
            pat_clean = pat.replace("|", "\\|")
            desc_clean = (desc or "—").replace("|", "\\|")
            lines.append(f"| `{name}` | `{pat_clean}` | {desc_clean} |")
        lines.append("")

    target = Path(path) if path else default_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return {
        "ok": True,
        "path": str(target),
        "skills": len(skills),
        "categories": len(by_cat),
        "bytes": target.stat().st_size,
    }
