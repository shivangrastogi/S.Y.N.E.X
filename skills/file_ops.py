"""Common-folder file operations."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from core.skill_registry import skill

_HOME = Path.home()
_SEARCH_DIRS = [
    _HOME / "Documents",
    _HOME / "Downloads",
    _HOME / "Desktop",
    _HOME / "Pictures",
]


def _find_file(query: str) -> str | None:
    """Case-insensitive substring match across common folders. Returns first hit."""
    q = query.lower().strip()
    if not q:
        return None
    for root in _SEARCH_DIRS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            try:
                if p.is_file() and q in p.name.lower():
                    return str(p)
            except (PermissionError, OSError):
                continue
    return None


@skill(
    name="open_file",
    description="Search Documents/Downloads/Desktop/Pictures for a file by name and open it",
    patterns=[
        "X file kholo",
        "resume kholo",
        "X document open karo",
        "find and open X",
        "file kholo X",
    ],
    required_entities=["query"],
    prompts={"query": "Kaunsi file kholni hai?"},
)
def open_file(slots: dict) -> str:
    query = (slots.get("query") or "").strip()
    if not query:
        return "Kaunsi file kholni hai? Naam batao."
    path = _find_file(query)
    if not path:
        return f"'{query}' naam ki file Documents, Downloads, Desktop, Pictures mein nahi mili."
    try:
        os.startfile(path)
    except OSError as e:
        return f"File mili lekin khol nahi paya: {e}"
    return f"Khola: {Path(path).name}"


@skill(
    name="create_folder",
    description="Create a new folder by path or simple name (under Documents by default)",
    patterns=[
        "naya folder banao X",
        "create folder X",
        "X folder banao Documents mein",
        "make a new directory X",
    ],
    required_entities=["query"],
    prompts={"query": "Folder ka naam kya rakhna hai?"},
)
def create_folder(slots: dict) -> str:
    name = (slots.get("query") or "").strip()
    if not name:
        return "Folder ka naam batao."
    target = Path(name) if Path(name).is_absolute() else _HOME / "Documents" / name
    target.mkdir(parents=True, exist_ok=True)
    return f"Folder ban gaya: {target}"


@skill(
    name="reveal_in_explorer",
    description="Open File Explorer at a common location",
    patterns=[
        "downloads kholo",
        "documents kholo",
        "desktop kholo file explorer mein",
        "open downloads folder",
        "open documents folder",
    ],
    required_entities=[],
)
def reveal_in_explorer(slots: dict) -> str:
    text = " ".join(str(v).lower() for v in slots.values()) if slots else ""
    target = _HOME / "Documents"
    if "download" in text:
        target = _HOME / "Downloads"
    elif "desktop" in text:
        target = _HOME / "Desktop"
    elif "picture" in text:
        target = _HOME / "Pictures"
    subprocess.Popen(f'explorer "{target}"', shell=True)
    return f"Khola: {target}"
