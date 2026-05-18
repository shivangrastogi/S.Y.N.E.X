"""Dev-tooling shortcuts for the engineer using AERIS as a daily driver.

* ``git_status``         — short, human-readable status of the project repo
* ``git_branch``         — current branch + ahead/behind summary
* ``open_explorer_here`` — File Explorer at the project root
* ``restart_explorer``   — taskkill /im explorer.exe + relaunch
* ``path_to_clipboard``  — full path of the project root to clipboard
* ``todo_today``         — parses ``data/scratch.md`` for today's `- [ ]` items
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import time
from datetime import date

from core.skill_registry import skill

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(cmd: list[str], *, cwd: str = _ROOT, timeout: float = 4.0) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, p.stdout or "", p.stderr or ""
    except Exception as e:
        return -1, "", str(e)


# ── git ────────────────────────────────────────────────────────────── #

@skill(
    name="git_status",
    description="Short git status of the AERIS project root",
    patterns=[
        "git status", "git st", "what's uncommitted", "uncommitted changes",
        "git changes", "show diff status", "git kya status hai",
    ],
)
def git_status(_slots: dict) -> str:
    rc, out, err = _run(["git", "status", "--short", "--branch"])
    if rc != 0:
        return f"git status failed: {err.strip() or out.strip() or 'unknown'}"
    lines = out.splitlines()
    if not lines:
        return "Working tree clean."
    branch_line = lines[0] if lines and lines[0].startswith("##") else ""
    file_lines = [l for l in lines if not l.startswith("##")]
    branch = branch_line.lstrip("# ").strip() if branch_line else ""
    if not file_lines:
        return f"Clean on {branch}." if branch else "Working tree clean."
    summary = {"M": 0, "A": 0, "D": 0, "R": 0, "??": 0}
    for l in file_lines:
        code = l[:2].strip() or "??"
        key = "??" if code.startswith("?") else code[0]
        if key in summary:
            summary[key] += 1
    parts = []
    if summary["M"]:  parts.append(f"{summary['M']} modified")
    if summary["A"]:  parts.append(f"{summary['A']} added")
    if summary["D"]:  parts.append(f"{summary['D']} deleted")
    if summary["R"]:  parts.append(f"{summary['R']} renamed")
    if summary["??"]: parts.append(f"{summary['??']} untracked")
    out_lines = [f"{branch}: {', '.join(parts)} ({len(file_lines)} total)"]
    for l in file_lines[:8]:
        out_lines.append(f"  {l.rstrip()}")
    if len(file_lines) > 8:
        out_lines.append(f"  ... +{len(file_lines) - 8} more")
    return "\n".join(out_lines)


@skill(
    name="git_branch",
    description="Current git branch + commit-ahead/behind summary",
    patterns=[
        "git branch", "what branch", "current branch", "branch kaunsa hai",
        "git current branch",
    ],
)
def git_branch(_slots: dict) -> str:
    rc, out, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0:
        return "Not a git repo here."
    branch = out.strip()
    # Try upstream comparison; gracefully degrade if no upstream is set.
    rc2, ab_out, _ = _run(["git", "rev-list", "--count", "--left-right",
                           f"{branch}...@{{upstream}}"])
    ahead_behind = ""
    if rc2 == 0:
        parts = ab_out.strip().split()
        if len(parts) == 2:
            ahead, behind = parts
            ahead_behind = f" · ahead {ahead}, behind {behind}"
    rc3, last_out, _ = _run(["git", "log", "-1", "--format=%h %s"])
    last = f" · last: {last_out.strip()}" if rc3 == 0 else ""
    return f"On '{branch}'{ahead_behind}{last}"


# ── File Explorer ──────────────────────────────────────────────────── #

@skill(
    name="open_explorer_here",
    description="Open File Explorer at the project root",
    patterns=[
        "open explorer", "open folder", "open file explorer",
        "show project folder", "open project", "explorer kholo",
        "open in finder", "reveal project",
    ],
)
def open_explorer_here(_slots: dict) -> str:
    if sys.platform != "win32":
        return "File Explorer skill sirf Windows pe."
    try:
        os.startfile(_ROOT)
        return f"Opened: {_ROOT}"
    except Exception as e:
        return f"Open fail: {e}"


@skill(
    name="restart_explorer",
    description="Restart explorer.exe (taskbar / desktop refresh)",
    patterns=[
        "restart explorer", "explorer restart karo",
        "refresh desktop", "taskbar refresh",
        "kill explorer",
    ],
)
def restart_explorer(_slots: dict) -> str:
    if sys.platform != "win32":
        return "Sirf Windows pe."
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"],
                       capture_output=True, timeout=4)
        time.sleep(0.5)
        subprocess.Popen("explorer.exe", shell=True, close_fds=True)
        return "Explorer restart kiya."
    except Exception as e:
        return f"Restart fail: {e}"


# ── Clipboard ──────────────────────────────────────────────────────── #

@skill(
    name="path_to_clipboard",
    description="Copy the project root path to the clipboard",
    patterns=[
        "copy path", "path copy karo", "project path",
        "copy project root", "current path",
    ],
)
def path_to_clipboard(_slots: dict) -> str:
    try:
        import pyperclip
        pyperclip.copy(_ROOT)
        return f"Path copied: {_ROOT}"
    except Exception:
        return f"pyperclip nahi hai. Path: {_ROOT}"


# ── Scratch todo extraction ───────────────────────────────────────── #

_TODO_RE = re.compile(r"^\s*-\s*\[\s*[\sx]\s*\]\s+", re.IGNORECASE)
_DONE_RE = re.compile(r"^\s*-\s*\[\s*x\s*\]\s+", re.IGNORECASE)


@skill(
    name="todo_today",
    description="Show unticked TODO lines from data/scratch.md (last 7 days)",
    patterns=[
        "todo today", "what todos", "my todos", "todos dikhao",
        "today's todos", "scratch todos", "todo list",
    ],
)
def todo_today(_slots: dict) -> str:
    path = os.path.join(_ROOT, "data", "scratch.md")
    if not os.path.exists(path):
        return "scratch.md nahi mila. 'note this: ...' se kuch likh do."
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Read fail: {e}"
    # We're treating EVERY line that looks like a markdown bullet or
    # `- [ ]` checkbox as a todo candidate; show those not checked.
    open_items: list[str] = []
    for line in lines:
        s = line.rstrip()
        if not s:
            continue
        if _DONE_RE.match(s):
            continue
        # `- [ ] X` is the explicit form; also accept plain `- X` from
        # append_note (which we treat as implicit todos).
        if _TODO_RE.match(s) or s.lstrip().startswith("- "):
            open_items.append(s.lstrip())
    if not open_items:
        return "Koi open todos nahi hain — clean!"
    show = open_items[-12:]   # most recent dozen
    return f"{len(open_items)} open items in scratch.md (showing last {len(show)}):\n" + \
           "\n".join(f"  {x}" for x in show)
