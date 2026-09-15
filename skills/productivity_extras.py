"""Five productivity skills — useful enough to live alongside the system pack.

* ``file_search``      — recursive glob with size cap, returns top 8 hits
* ``clipboard_transform`` — uppercase / lowercase / slug / json-pretty / strip
* ``kill_process``     — terminate a process by name (psutil)
* ``quick_timer``      — start a one-shot toast timer (5 / 10 / 15 / 30 min)
* ``append_note``      — append a timestamped line to ``data/scratch.md``

None of these depend on external services. Every skill degrades
gracefully when a feature is missing (e.g. pyperclip absent → clipboard
transforms return a helpful install hint instead of crashing).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── file_search ────────────────────────────────────────────────────── #

def _default_search_dirs() -> list[str]:
    """Common user folders only — full-profile walk is too slow for a 5 s
    breaker budget and most useful hits live in these few places anyway.
    Includes the project root so the user can search current-work files.
    """
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Pictures"),
        os.path.join(home, "Videos"),
        _ROOT,
    ]
    return [d for d in candidates if d and os.path.isdir(d)]


_SEARCH_DIRS = _default_search_dirs()
_SEARCH_EXCLUDE = {
    "node_modules", ".git", ".venv", "venv", "__pycache__",
    "AppData", ".cache", "Library", "site-packages",
    "dist", "build", ".next", ".nuxt",
}
_SEARCH_MAX_HITS = 8
_SEARCH_TIME_BUDGET_S = 3.5    # stay well under the 5 s breaker timeout

# Command/filler words peeled off the raw phrase to recover the actual query
# when the entity extractor didn't fill `content`. Position-independent (unlike
# web_jumps' front-only peel) because file phrasings put the name at either end
# ("file dhundo report" vs "report file kahaan hai").
_FS_STOP = {
    "file", "files", "folder", "dhundo", "dhoondo", "dhundho", "khojo",
    "find", "search", "locate", "named", "name", "for", "called",
    "kahaan", "kahan", "hai", "ka", "ki", "ko", "mera", "meri", "mere",
    "my", "wali", "wala", "the", "a", "an", "please", "zara", "koi", "naam",
}


def _fs_query(slots: dict) -> str:
    """Recover the search query: prefer an extracted `content` slot, else strip
    known command/filler words out of the raw phrase (any position)."""
    q = (slots.get("content") or "").strip()
    if q:
        return q
    raw = (slots.get("raw_text") or slots.get("text") or "").lower()
    toks = [t for t in re.findall(r"[a-z0-9._\-]+", raw) if t not in _FS_STOP]
    return " ".join(toks).strip()


@skill(
    name="file_search",
    description="Search recent user files by substring (case-insensitive)",
    patterns=[
        "file dhundo", "find files named",
        "search for file", "kahaan hai file", "locate file",
    ],
    # No hard gate: if `content` isn't extracted we recover the query from the
    # raw phrase (_fs_query) instead of dead-ending at a "kaunsa file?" prompt
    # even when the user already named the file ("file dhundo report").
    required_entities=[],
    prompts={},
)
def file_search(slots: dict) -> str:
    query = _fs_query(slots)
    if not query:
        return "Kya naam ke file dhundne hain? Jaise: 'file dhundo report'."
    if len(query) < 2:
        return "At least 2 characters chahiye search ke liye."
    query = query.lower()
    hits: list[tuple[float, str]] = []
    scanned = 0
    deadline = time.monotonic() + _SEARCH_TIME_BUDGET_S
    timed_out = False
    for root in _SEARCH_DIRS:
        if timed_out:
            break
        for dirpath, dirnames, filenames in os.walk(root):
            if time.monotonic() > deadline:
                timed_out = True
                break
            dirnames[:] = [d for d in dirnames if d not in _SEARCH_EXCLUDE
                           and not d.startswith(".")]
            scanned += len(filenames)
            for name in filenames:
                if query in name.lower():
                    full = os.path.join(dirpath, name)
                    try:
                        mtime = os.path.getmtime(full)
                    except OSError:
                        mtime = 0
                    hits.append((mtime, full))
            if len(hits) >= 200:
                break
    suffix = " (search timed out)" if timed_out else ""
    if not hits:
        return f"'{query}' naam ka koi file nahi mila ({scanned:,} scanned){suffix}."
    hits.sort(reverse=True)
    top = hits[:_SEARCH_MAX_HITS]
    out = [f"{len(hits)} matches (showing latest {len(top)}, {scanned:,} scanned){suffix}:"]
    for mtime, path in top:
        date = datetime.fromtimestamp(mtime).strftime("%b %d")
        out.append(f"  · [{date}] {path}")
    return "\n".join(out)


# ── clipboard_transform ────────────────────────────────────────────── #

_TRANSFORMS = ("upper", "lower", "slug", "json", "strip", "reverse")


def _slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "untitled"


@skill(
    name="clipboard_transform",
    description="Transform clipboard contents (upper/lower/slug/json/strip/reverse)",
    patterns=[
        "uppercase clipboard", "lowercase clipboard", "slugify clipboard",
        "format json clipboard", "json pretty", "strip clipboard",
        "reverse clipboard",
        "clipboard ko uppercase karo", "clipboard ko lowercase karo",
        "clipboard slug karo", "json pretty karo",
    ],
    # No hard required-entity gate: the transform word ("uppercase") lives in
    # the raw phrase, not in a `content` slot the extractor can fill, so gating
    # on `content` would ask "kaunsa transform?" and never reach this handler
    # (the actual text to transform comes from the clipboard, not the command).
    required_entities=[],
    prompts={},
)
def clipboard_transform(slots: dict) -> str:
    # Check content AND raw_text — the entity extractor often strips the
    # transform word out of `content` ("clipboard uppercase karo" → content
    # "clipboard"), so we'd otherwise ask "kaunsa transform?" needlessly.
    mode_raw = (str(slots.get("content") or "") + " " +
                str(slots.get("raw_text") or slots.get("text") or "")).strip().lower()
    mode = next((t for t in _TRANSFORMS if t in mode_raw), None)
    if mode is None:
        return f"Transform batao: {', '.join(_TRANSFORMS)}."
    try:
        import pyperclip
    except ImportError:
        return "'pip install pyperclip' karo."
    text = pyperclip.paste() or ""
    if not text:
        return "Clipboard khaali hai."
    try:
        if mode == "upper":
            new = text.upper()
        elif mode == "lower":
            new = text.lower()
        elif mode == "slug":
            new = _slugify(text)
        elif mode == "strip":
            new = text.strip()
        elif mode == "reverse":
            new = text[::-1]
        elif mode == "json":
            new = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        else:
            return f"Transform {mode!r} unknown."
    except json.JSONDecodeError:
        return "Clipboard contents valid JSON nahi hain."
    pyperclip.copy(new)
    return f"Clipboard {mode} ho gaya. {len(new)} chars."


# ── kill_process ───────────────────────────────────────────────────── #

# Verb/filler words peeled off the raw phrase to recover the process name when
# the extractor didn't fill `content` ("kill firefox" → name "firefox"). Same
# pattern as _fs_query: needed because relaxing the required-entity gate (so the
# anchored "kill X" reaches this handler) means we must recover the name here.
_KILL_STOP = {
    "kill", "terminate", "close", "quit", "stop", "end", "band", "karo",
    "kar", "kro", "do", "process", "app", "application", "force", "task",
    "ko", "the", "exe", "please", "zara", "abhi", "wala", "wali",
}


def _proc_name(slots: dict) -> str:
    """Recover the target process name: prefer `content`, else strip kill/close
    verbs and filler out of the raw phrase."""
    n = (slots.get("content") or "").strip()
    if n:
        return n
    raw = (slots.get("raw_text") or slots.get("text") or "").lower()
    toks = [t for t in re.findall(r"[a-z0-9.\-]+", raw) if t not in _KILL_STOP]
    return " ".join(toks).strip()


@skill(
    name="kill_process",
    description="Terminate a process by name (e.g. 'firefox', 'discord')",
    patterns=[
        "kill process", "kill firefox", "close process",
        "kill chrome", "terminate", "process band karo",
        "kill app", "force quit",
    ],
    # No hard gate: the anchor routes "kill X" here, and the name lives in the
    # verb phrase (not a `content` slot the extractor fills), so gating on
    # `content` would dead-end at a "kaunsa process?" prompt. _proc_name recovers
    # it; a bare "kill" with no target still returns the prompt below.
    required_entities=[],
    prompts={},
)
def kill_process(slots: dict) -> str:
    name = _proc_name(slots).lower()
    if not name:
        return "Kaunsa process kill karna hai? Jaise: 'kill firefox'."
    if len(name) < 3:
        return "Process name kam se kam 3 letters ka ho — safety ke liye."
    # Hard block on common safety hazards.
    forbidden = {"system", "csrss", "winlogon", "services", "lsass",
                 "explorer", "wininit", "smss", "svchost"}
    if name in forbidden or name + ".exe" in forbidden:
        return f"'{name}' system-critical hai, nahi kar sakta."
    try:
        import psutil
    except ImportError:
        return "'pip install psutil' karo."
    killed = []
    failed = []
    target = name if name.endswith(".exe") else name + ".exe"
    for proc in psutil.process_iter(["name"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            if pname == name.lower() or pname == target.lower():
                proc.terminate()
                killed.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            failed.append(str(e))
    if not killed:
        return f"'{name}' naam ke koi running process nahi mila."
    if failed:
        return f"{len(killed)} terminate kiye ({len(failed)} fail). PIDs: {killed}"
    return f"{len(killed)} process(es) terminate kar diye. PIDs: {killed}"


# ── quick_timer ────────────────────────────────────────────────────── #

_active_timers: list[threading.Timer] = []
_timer_lock = threading.Lock()


def _fire_timer(label: str) -> None:
    """Show a tray toast when a timer expires. Best-effort — we look up
    the running main_window for its TrayController. Fall back to log if
    the GUI is not up."""
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            for w in app.topLevelWidgets():
                tray = getattr(w, "_tray", None)
                if tray is not None:
                    tray.notify("Timer", label)
                    return
    except Exception:
        pass
    log.info("[timer] EXPIRED — %s", label)


@skill(
    name="quick_timer",
    description="Set a timer — '5 minute timer', '10 min timer', '30 minute pomodoro'",
    patterns=[
        "5 minute timer", "10 minute timer", "15 minute timer",
        "30 minute timer", "set timer", "timer lagao",
        "pomodoro timer", "60 minute timer",
        "timer set karo", "5 minute baad batao",
    ],
    required_entities=["content"],
    prompts={"content": "Kitne minute ka timer? (1-180)"},
)
def quick_timer(slots: dict) -> str:
    raw = (slots.get("content") or "").strip().lower()
    m = re.search(r"(\d+)", raw)
    if not m:
        return "Number batao — jaise '5 minute timer'."
    minutes = max(1, min(180, int(m.group(1))))
    label = f"{minutes}-minute timer done"
    if "pomodoro" in raw or "focus" in raw:
        label = f"Pomodoro {minutes}m — take a break"
    t = threading.Timer(minutes * 60.0, _fire_timer, args=[label])
    t.daemon = True
    t.start()
    with _timer_lock:
        _active_timers.append(t)
        # Reap finished timers.
        _active_timers[:] = [x for x in _active_timers if x.is_alive()]
    return f"Timer set: {minutes} minute. Total active timers: {len(_active_timers)}."


# ── append_note ────────────────────────────────────────────────────── #

@skill(
    name="append_note",
    description="Append a quick note to data/scratch.md with a timestamp",
    patterns=[
        "add note", "save note", "note likho",
        "remember this", "scratch note", "quick note",
        "yaad rakhna", "likh lo",
    ],
    required_entities=["content"],
    prompts={"content": "Kya note karna hai?"},
)
def append_note(slots: dict) -> str:
    text = (slots.get("content") or "").strip()
    if not text:
        return "Note ka content batao."
    path = os.path.join(_ROOT, "data", "scratch.md")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Append with a timestamp; the file IS user-curated, so a
        # non-atomic append is fine and avoids rewriting the whole file
        # for every short note.
        with open(path, "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            f.write(f"- [{ts}] {text}\n")
    except OSError as e:
        return f"Note save fail ho gaya: {e}"
    return f"Note saved to scratch.md ({len(text)} chars)."
