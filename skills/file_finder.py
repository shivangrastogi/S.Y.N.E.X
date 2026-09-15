"""Advanced file finder + recent-files browser.

Distinct from ``skills/file_ops.open_file`` (which opens the first
substring hit). These skills:

* ``find_file``     — fuzzy + substring + extension-aware ranking,
                     returns top N candidates *and* opens the best one.
* ``recent_files``  — list the N most-recently-modified files across the
                     user's common doc/dl/desktop folders.

Both walk Documents, Downloads, Desktop, Pictures and stop at a small
depth (3 levels) to keep big folders cheap.
"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Iterable

from core.skill_registry import skill

log = logging.getLogger(__name__)

_HOME = Path.home()
_SEARCH_DIRS = [
    _HOME / "Documents",
    _HOME / "Downloads",
    _HOME / "Desktop",
    _HOME / "Pictures",
]
_MAX_DEPTH = 4               # don't descend deeper than this from the root
_MAX_FILES_SCANNED = 25_000  # belt-and-braces against pathological folders
_TOP_N = 5                   # default top-N hits to report


def _walk_capped(roots: Iterable[Path]) -> Iterable[Path]:
    """yield every file under ``roots``, bounded by depth + count."""
    seen = 0
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        root_depth = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden dirs and common cache/junk.
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and d.lower() not in {
                    "node_modules", "__pycache__", "venv", ".venv",
                    "target", "dist", "build", "out", ".git",
                }
            ]
            d = len(Path(dirpath).parts) - root_depth
            if d > _MAX_DEPTH:
                dirnames[:] = []
                continue
            for fn in filenames:
                yield Path(dirpath) / fn
                seen += 1
                if seen >= _MAX_FILES_SCANNED:
                    return


def _score(name: str, query: str) -> float:
    """Cheap fuzzy score in [0,1]. Higher = better match."""
    name_lo = name.lower()
    q = query.lower().strip()
    if not q:
        return 0.0
    if name_lo == q or name_lo.startswith(q):
        return 1.0
    if q in name_lo:
        # Bonus when the match is a whole-word boundary.
        if re.search(rf"\b{re.escape(q)}\b", name_lo):
            return 0.85
        return 0.7
    # Token-by-token: every query token must appear somewhere.
    tokens = [t for t in re.split(r"[\s_\-]+", q) if t]
    if not tokens:
        return 0.0
    hits = sum(1 for t in tokens if t in name_lo)
    return 0.4 * (hits / len(tokens)) if hits == len(tokens) else 0.0


def _strip_open_verb(text: str) -> str:
    """Strip leading 'find/open/locate' verbs (+ trailing filler) so what
    remains is the actual query. Greedy on filler words ("file", "my")
    because users say "find file resume" and mean "resume"."""
    if not text:
        return ""
    s = text.strip()
    # 1. Lead-strip verbs
    s = re.sub(
        r"^(?:please\s+)?"
        r"(?:find|locate|search|search\s+for|where\s+is|where's|"
        r"open|launch|show|show\s+me|"
        r"dhundo|dhoondo|find\s+karo|search\s+karo|kholo|"
        r"file\s+find\s+karo|file\s+kholo)\s+",
        "",
        s,
        flags=re.IGNORECASE,
    )
    # 2. Drop common filler nouns/possessives that follow the verb.
    s = re.sub(r"^(?:my|mera|meri|mere|the)\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:file|files|document|documents|doc|ppt|slides?|"
               r"spreadsheet|excel|pdf)\s+", "", s, flags=re.IGNORECASE)
    # 3. Trailing filler/question markers.
    s = re.sub(r"(?:^|\s+)(?:please|now|kahan\s+hai)\??$", "",
               s, flags=re.IGNORECASE)
    # Trailing "file"/"files" only when there's something else BEFORE it,
    # so "search slides please" → "" not "" — wait we need it gone here too.
    s = re.sub(r"\s+(?:file|files)$", "", s, flags=re.IGNORECASE)
    return s.strip(" ?:\"',")


# ── find_file ──────────────────────────────────────────────────────


@skill(
    name="find_file",
    description="Fuzzy-search the user's common folders for a filename, "
                "show top matches and open the best one.",
    patterns=[
        "find file", "find my file", "search file", "where is my file",
        "find resume", "find my resume", "search for resume", "where is my resume",
        "find file X", "search for file X", "locate X",
        "X file dhundo", "X file dhoondo", "find karo X",
        "find document", "find my document", "search document",
        "file find karo",
        "find slides", "find ppt", "find spreadsheet",
        "X dhoondo", "X file kahan hai", "X kahan hai",
    ],
    required_entities=[],
)
def find_file(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or slots.get("query") or ""
    query = _strip_open_verb(text) or text.strip()
    # Strip common trailing tokens too.
    query = re.sub(r"\s+(?:file|files|please|now)$", "", query, flags=re.IGNORECASE)
    if not query:
        return "Kaunsi file dhundhoon? Naam batao — e.g. 'find file resume'."

    candidates: list[tuple[float, float, Path]] = []  # (score, mtime, path)
    for p in _walk_capped(_SEARCH_DIRS):
        s = _score(p.name, query)
        if s <= 0:
            continue
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0.0
        candidates.append((s, mtime, p))

    if not candidates:
        return (f"'{query}' jaisi koi file Documents/Downloads/Desktop/Pictures "
                f"mein nahi mili.")

    # Sort: best score first, then newest mtime, deterministic by path.
    candidates.sort(key=lambda t: (-t[0], -t[1], str(t[2])))
    top = candidates[:_TOP_N]

    best = top[0][2]
    lines = [f"'{query}' ke liye {len(candidates)} files mile. Best: {best.name}"]
    for score, mtime, path in top:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)) if mtime else "?"
        lines.append(f"  • {path}  ({score:.2f} · {when})")
    # Open the best match.
    try:
        os.startfile(str(best))
    except OSError as e:
        lines.append(f"(open failed: {e})")
    return "\n".join(lines)


# ── recent_files ───────────────────────────────────────────────────


@skill(
    name="recent_files",
    description="List the 10 most recently modified files across Documents, "
                "Downloads, Desktop, Pictures.",
    patterns=[
        "recent files", "show recent files", "recently modified files",
        "what have i been working on", "kya kya kaam kiya recently",
        "haal ki files dikhao", "naye files dikhao", "latest files",
        "show my recent files", "what did i edit recently",
        "abhi tak ki files",
    ],
    required_entities=[],
)
def recent_files(_slots: dict) -> str:
    entries: list[tuple[float, Path]] = []
    for p in _walk_capped(_SEARCH_DIRS):
        try:
            mt = p.stat().st_mtime
        except OSError:
            continue
        entries.append((mt, p))
    if not entries:
        return "Kuch bhi files nahi mile."
    entries.sort(key=lambda t: -t[0])
    top = entries[:10]
    lines = [f"Top {len(top)} most recently modified files:"]
    for mt, path in top:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(mt))
        lines.append(f"  • {when}  {path}")
    return "\n".join(lines)
