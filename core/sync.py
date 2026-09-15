"""Cross-machine sync — pack/unpack the user's customisations into a ZIP.

Captures every settings-shaped artifact AERIS persists:
  * data/settings.json
  * data/custom_gestures.json
  * data/voice_registry.json
  * data/knowledge_graph.json
  * data/macros.json
  * data/chains.json
  * data/face_registry.json + data/face_registry_insight.json
  * data/notes/  (entire folder — journal, voice memos, etc.)
  * data/news_sources.json
  * data/user_patterns.json

Each file is optional; missing files are simply skipped on export.

Public API:
    export_snapshot(path) -> dict           # files written
    import_snapshot(path) -> dict           # files restored
    snapshot_files() -> list[str]           # what would be packed
    default_export_path() -> str            # ~/Documents/aeris_sync_<ts>.zip
"""
from __future__ import annotations

import logging
import os
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_DATA = _ROOT / "data"

# Files we know about — order-stable so the ZIP is deterministic.
_PACK_FILES = [
    "settings.json",
    "custom_gestures.json",
    "voice_registry.json",
    "knowledge_graph.json",
    "macros.json",
    "chains.json",
    "face_registry.json",
    "face_registry_insight.json",
    "news_sources.json",
    "user_patterns.json",
    "entities.json",
]

# Whole folders to mirror (walked recursively).
_PACK_DIRS = [
    "notes",
    "plugins",
]


def default_export_path() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    docs = Path.home() / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
    return str(docs / f"aeris_sync_{ts}.zip")


def snapshot_files() -> list[str]:
    """List every path that WOULD be packed (relative to data/)."""
    out: list[str] = []
    for fn in _PACK_FILES:
        p = _DATA / fn
        if p.is_file():
            out.append(fn)
    for sub in _PACK_DIRS:
        d = _DATA / sub
        if not d.is_dir():
            continue
        for root, _dirs, files in os.walk(d):
            for fn in files:
                rel = Path(root).joinpath(fn).relative_to(_DATA)
                out.append(str(rel).replace(os.sep, "/"))
    return sorted(out)


def export_snapshot(path: Optional[str] = None) -> dict:
    """Write the user's customisations to a ZIP. Returns metadata."""
    target = Path(path) if path else Path(default_export_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    files = snapshot_files()
    if not files:
        return {"ok": False, "path": str(target), "files": 0,
                "msg": "Koi customisation file nahi mili to export."}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            src = _DATA / rel
            try:
                zf.write(src, arcname=rel)
            except Exception as e:
                log.warning("[sync] could not pack %s: %s", rel, e)
    size = target.stat().st_size if target.exists() else 0
    return {
        "ok": True,
        "path": str(target),
        "files": len(files),
        "size_bytes": size,
        "msg": f"Exported {len(files)} file(s) → {target} ({size} bytes).",
    }


def import_snapshot(path: str, overwrite: bool = True) -> dict:
    """Restore from a ZIP previously created by ``export_snapshot``.

    Files INSIDE the ZIP are written under ``data/`` preserving paths.
    Backs up any clashing file to ``<name>.bak-<ts>`` before overwrite
    so the user can roll back if needed.
    """
    src = Path(path)
    if not src.is_file():
        return {"ok": False, "msg": f"File nahi mila: {src}"}
    restored = 0
    backed_up = 0
    skipped = 0
    ts = time.strftime("%Y%m%d_%H%M%S")
    with zipfile.ZipFile(src, "r") as zf:
        for info in zf.infolist():
            # Reject absolute / traversal-style paths.
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                skipped += 1
                continue
            dest = _DATA / name
            if dest.exists():
                if not overwrite:
                    skipped += 1
                    continue
                try:
                    bak = dest.with_suffix(dest.suffix + f".bak-{ts}")
                    shutil.copy2(dest, bak)
                    backed_up += 1
                except Exception as e:
                    log.warning("[sync] backup of %s failed: %s", dest, e)
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                with zf.open(info) as src_f, open(dest, "wb") as dst_f:
                    shutil.copyfileobj(src_f, dst_f)
                restored += 1
            except Exception as e:
                log.warning("[sync] restore of %s failed: %s", name, e)
                skipped += 1
    return {
        "ok": True,
        "restored": restored,
        "backed_up": backed_up,
        "skipped": skipped,
        "msg": (f"Imported {restored} file(s) from {src}. "
                f"{backed_up} clashing file(s) backed up; "
                f"{skipped} skipped."),
    }
