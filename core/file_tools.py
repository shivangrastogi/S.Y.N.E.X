"""Local file intelligence — folder stats, large-file finder, read-aloud.

Pure os/pathlib, zero network. Walks are capped (file count + skip heavy
system dirs) so a stray "C:\\" never hangs the assistant.
"""
from __future__ import annotations

import heapq
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_MAX_WALK_FILES = 20000
_SKIP_DIRS = {"node_modules", "__pycache__", ".git", "$recycle.bin",
              "windows", "program files", "program files (x86)",
              "appdata", "system volume information"}

_KEYWORD_FOLDERS = {
    "downloads": "~/Downloads", "download": "~/Downloads",
    "documents": "~/Documents", "document": "~/Documents",
    "desktop": "~/Desktop", "pictures": "~/Pictures", "photo": "~/Pictures",
    "music": "~/Music", "videos": "~/Videos", "video": "~/Videos",
}

_TEXT_EXT = {".txt", ".md", ".log", ".rst", ".csv", ".py", ".json",
             ".ini", ".cfg", ".bat", ".sh", ".yaml", ".yml"}


def resolve_folder(text: str) -> Optional[str]:
    """Pull a folder from an utterance: explicit path or a keyword folder."""
    import re
    m = re.search(r"[A-Za-z]:[\\/][^\"'\n]*|~[\\/][^\"'\n]*", text or "")
    if m:
        p = os.path.expanduser(m.group(0).strip().rstrip(".,"))
        return p
    lo = (text or "").lower()
    for kw, folder in _KEYWORD_FOLDERS.items():
        if kw in lo:
            return os.path.expanduser(folder)
    return None


def _fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _walk(folder: Path):
    """Yield (path, size) for files, capped + skipping system dirs."""
    count = 0
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs
                   if d.lower() not in _SKIP_DIRS and not d.startswith(".")]
        for name in names:
            p = Path(root) / name
            try:
                size = p.stat().st_size
            except OSError:
                continue
            yield p, size
            count += 1
            if count >= _MAX_WALK_FILES:
                return


def folder_stats(path: str) -> str:
    """Count, total size, and top file-types in a folder (recursive, capped)."""
    p = Path(os.path.expanduser(path))
    if not p.is_dir():
        return f"Folder nahi mila: {path}"
    n_files = 0
    total = 0
    by_ext: dict[str, int] = {}
    for fp, size in _walk(p):
        n_files += 1
        total += size
        ext = fp.suffix.lower() or "(no ext)"
        by_ext[ext] = by_ext.get(ext, 0) + 1
    if n_files == 0:
        return f"{p.name or path} khaali hai (koi file nahi)."
    top = sorted(by_ext.items(), key=lambda kv: -kv[1])[:4]
    types = ", ".join(f"{ext} ×{c}" for ext, c in top)
    capped = " (pehle 20k tak gina)" if n_files >= _MAX_WALK_FILES else ""
    return (f"{p.name or path}: {n_files} files, {_fmt_size(total)} total{capped}. "
            f"Zyada: {types}.")


def find_large_files(path: str, n: int = 5) -> str:
    """Top-N largest files under a folder — the local disk-hog finder."""
    p = Path(os.path.expanduser(path))
    if not p.is_dir():
        return f"Folder nahi mila: {path}"
    largest = heapq.nlargest(
        max(1, min(20, n)), _walk(p), key=lambda ps: ps[1])
    if not largest:
        return f"{p.name or path} mein koi file nahi mili."
    rows = [f"{_fmt_size(size)}  {fp.name}" for fp, size in largest]
    return f"Sabse bade files ({p.name or path}):\n" + "\n".join(rows)


def read_file_text(path: str, cap: int = 600) -> Optional[tuple[str, bool]]:
    """(text, truncated) for a readable text file, else None."""
    p = Path(os.path.expanduser(path.strip().strip('"')))
    if not p.is_file():
        return None
    if p.suffix.lower() not in _TEXT_EXT:
        return None
    try:
        if p.stat().st_size > 2 * 1024 * 1024:      # 2 MB text cap
            return None
        text = p.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None
    if not text:
        return None
    if len(text) > cap:
        return text[:cap].rstrip() + "…", True
    return text, False
