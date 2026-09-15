"""Local file intelligence by voice — folder stats, large files, read aloud.

100% local (core/file_tools, pure os/pathlib). Distinct from file_search
(finds a named file) and reveal_in_explorer (opens a folder).
"""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="folder_stats",
    description="How many files + total size + top types in a folder (local, recursive).",
    patterns=[
        "downloads me kitni files hain", "is folder me kya hai",
        "folder stats batao", "downloads folder ka size kya hai",
        "documents me kitni files hain", "is folder me kitni files hain",
        "folder me kitna data hai", "downloads kitna bhaari hai",
    ],
    required_entities=[],
)
def folder_stats(slots: dict) -> str:
    from core.file_tools import folder_stats as _stats, resolve_folder
    text = slots.get("raw_text") or slots.get("text") or ""
    folder = resolve_folder(text)
    if not folder:
        return ("Kis folder ki, sir? Naam ya path do — jaise 'downloads me "
                "kitni files hain' ya ek full path.")
    return _stats(folder)


@skill(
    name="find_large_files",
    description="Find the biggest files eating disk space in a folder (local).",
    patterns=[
        "bade files dhundo", "sabse bade files konse hain",
        "disk kaun kha raha hai files me", "downloads me bade files dikhao",
        "sabse bhaari files batao", "large files dhundo",
        "kaunsi files zyada jagah le rahi hain",
    ],
    required_entities=[],
)
def find_large_files(slots: dict) -> str:
    from core.file_tools import find_large_files as _large, resolve_folder
    text = slots.get("raw_text") or slots.get("text") or ""
    folder = resolve_folder(text)
    if not folder:
        # Default to Downloads — the usual disk-hog culprit.
        import os
        folder = os.path.expanduser("~/Downloads")
    return _large(folder, n=6)


@skill(
    name="read_file_aloud",
    description="Read a text file's content aloud (local TTS via the reply path).",
    patterns=[
        "is file ko padho", "file padh do", "file ka content padho",
        "ye text file padho", "file ko sunao", "is file ko bol ke sunao",
        "file read karo",
    ],
    required_entities=[],
)
def read_file_aloud(slots: dict) -> str:
    from core.file_tools import read_file_text, resolve_folder
    text = slots.get("raw_text") or slots.get("text") or ""
    path = resolve_folder(text)     # reuses the path extractor
    if not path:
        return ("Kaunsi file, sir? Path do — jaise 'is file ko padho "
                "C:\\Notes\\plan.txt' (txt/md/log/csv chalega).")
    res = read_file_text(path, cap=600)
    if res is None:
        return (f"'{path}' padhne layak text file nahi (txt/md/log/csv/… "
                "chahiye, ya file mili nahi).")
    content, truncated = res
    return content + ("  (… aur bhi hai — poora file me dekho.)"
                      if truncated else "")
