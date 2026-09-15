"""Cross-machine sync voice surface.

Skills:
  * ``sync_export``  — pack customisations to a default-named ZIP
  * ``sync_import``  — restore from a ZIP path
  * ``sync_list``    — list files that would be packed
  * ``sync_default_path`` — print the default export path
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from core.skill_registry import skill

log = logging.getLogger(__name__)


_PATH_RE = re.compile(
    r"(?:to|at|from)\s+([\"']?)(?P<p>[A-Za-z]:[\\\/][^\"'\n]+\.zip)\1",
    re.IGNORECASE,
)


def _path_from(text: str) -> str:
    if not text:
        return ""
    m = _PATH_RE.search(text)
    if m:
        return m.group("p").strip()
    # Bare path token at end of input.
    m2 = re.search(r"([A-Za-z]:[\\\/][^\s\"']+\.zip)", text)
    if m2:
        return m2.group(1).strip()
    return ""


@skill(
    name="sync_export",
    description="Pack all AERIS customisations (settings, custom gestures, "
                "voice ID, knowledge graph, macros, chains, faces) into a "
                "ZIP under ~/Documents (or a custom path).",
    patterns=[
        "sync export", "export sync", "export my settings",
        "backup aeris", "backup everything",
        "sync export to", "export aeris settings",
        "sync backup", "settings backup",
    ],
    required_entities=[],
)
def sync_export(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    path = _path_from(text) or None
    try:
        from core.sync import export_snapshot
    except Exception as e:
        return f"sync load fail: {e}"
    info = export_snapshot(path)
    return info.get("msg") or "Export complete."


@skill(
    name="sync_import",
    description="Restore AERIS customisations from a sync ZIP.",
    patterns=[
        "sync import", "import sync", "restore aeris",
        "restore backup", "import from",
        "sync restore", "settings restore",
        "load backup",
    ],
    required_entities=[],
)
def sync_import(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    path = _path_from(text)
    if not path:
        return ("Path do — e.g. 'sync import C:\\Users\\You\\Documents\\aeris_sync_xxx.zip'.")
    try:
        from core.sync import import_snapshot
    except Exception as e:
        return f"sync load fail: {e}"
    info = import_snapshot(path)
    return info.get("msg") or "Import complete."


@skill(
    name="sync_list",
    description="List every file that the next sync export would pack.",
    patterns=[
        "sync list", "list sync files", "what gets backed up",
        "sync contents", "sync preview",
    ],
    required_entities=[],
)
def sync_list(_slots: dict) -> str:
    try:
        from core.sync import snapshot_files
    except Exception as e:
        return f"sync load fail: {e}"
    files = snapshot_files()
    if not files:
        return "Koi customisation file nahi mili to pack."
    lines = [f"{len(files)} file(s) ready to pack:"]
    for f in files[:30]:
        lines.append(f"  • {f}")
    if len(files) > 30:
        lines.append(f"  ... + {len(files) - 30} more")
    return "\n".join(lines)


@skill(
    name="sync_default_path",
    description="Print the path the next sync export will write to.",
    patterns=[
        "sync default path", "sync path", "where will sync save",
        "default sync path", "sync output path",
    ],
    required_entities=[],
)
def sync_default_path(_slots: dict) -> str:
    try:
        from core.sync import default_export_path
    except Exception as e:
        return f"sync load fail: {e}"
    return f"Next sync export → {default_export_path()}"
