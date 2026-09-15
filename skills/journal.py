"""Rolling journal — append timestamped lines to a single Markdown file.

Distinct from ``create_note`` (executor / one-note-per-call) — this skill
keeps a single rolling document so weekly review / search is one grep.

  * ``note_append``  — "log X" / "add to journal X" / "journal me likho X"
  * ``journal_show`` — read back the last N entries (default 10)
  * ``journal_path`` — print the file path so the user can open it directly
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from core.skill_registry import skill


_ROOT = Path(__file__).resolve().parents[1]
_JOURNAL_DIR = _ROOT / "data" / "notes"
_JOURNAL_PATH = _JOURNAL_DIR / "journal.md"


def _ensure_dir() -> None:
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)


def _strip_verb(text: str) -> str:
    """Strip leading 'log / add to journal / note that' so what's left is
    the actual entry."""
    if not text:
        return ""
    s = re.sub(
        r"^(?:please\s+)?"
        r"(?:log|note|note\s+that|note\s+down|add\s+to\s+journal|append\s+to\s+journal|"
        r"journal\s+me\s+likho|journal\s+me\s+add\s+karo|likh\s+do|likho|"
        r"journal\s+entry|log\s+karo)\s*[:\-]?\s*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )
    # Drop a single trailing-clause filler word ("that", "ki", "kya") so
    # the entry reads cleanly: "note that prod is down" → "prod is down".
    s = re.sub(r"^(?:that|ki|kya)\s+", "", s, flags=re.IGNORECASE)
    return s.strip(" :-,.\"'")


# ── note_append ────────────────────────────────────────────────────


@skill(
    name="note_append",
    description="Append a timestamped line to the rolling journal "
                "(data/notes/journal.md).",
    patterns=[
        "log", "log this", "add to journal", "append to journal",
        "note this", "note down",
        "journal me likho", "journal me add karo",
        "log karo", "diary me likho", "likh do",
        "today I", "today i",
    ],
    required_entities=[],
)
def note_append(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    entry = _strip_verb(text)
    if not entry:
        return ("Kya log karna hai? Try 'log finished the gesture engine refactor' "
                "or 'journal me likho meeting cancel ho gayi'.")
    _ensure_dir()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- **{ts}** — {entry}\n"
    with open(_JOURNAL_PATH, "a", encoding="utf-8") as f:
        f.write(line)
    return f"Logged: {entry[:80]}{'...' if len(entry) > 80 else ''}"


# ── journal_show ───────────────────────────────────────────────────


@skill(
    name="journal_show",
    description="Read back the last 10 journal entries.",
    patterns=[
        "show journal", "journal dikhao", "read journal",
        "recent journal entries", "last few notes", "what did I log",
        "journal ke entries", "journal me kya hai",
        "journal recent", "show last journal entries",
    ],
    required_entities=[],
)
def journal_show(_slots: dict) -> str:
    if not _JOURNAL_PATH.exists():
        return "Journal khaali hai. 'log <something>' bolo to shuru karo."
    with open(_JOURNAL_PATH, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    if not lines:
        return "Journal khaali hai."
    tail = lines[-10:]
    return f"Last {len(tail)} journal entries:\n" + "\n".join(tail)


# ── journal_path ───────────────────────────────────────────────────


@skill(
    name="journal_path",
    description="Print the journal file path so it can be opened in an editor.",
    patterns=[
        "journal path", "journal file", "where is my journal",
        "journal kahan hai", "open journal file",
    ],
    required_entities=[],
)
def journal_path(_slots: dict) -> str:
    _ensure_dir()
    if not _JOURNAL_PATH.exists():
        _JOURNAL_PATH.touch()
    return f"Journal: {_JOURNAL_PATH}"
