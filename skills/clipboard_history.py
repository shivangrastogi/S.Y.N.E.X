"""Persistent clipboard history.

A background watcher polls the OS clipboard ~2x/sec and persists distinct
strings to ``data/clipboard_history.json`` (last 50). Skill voice triggers:

  "clipboard history dikhao"  → list last 10 with indexes
  "copy item 3"               → push item #3 back to the clipboard
  "clipboard clear"           → wipe history
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.skill_registry import skill  # noqa: E402

log = logging.getLogger(__name__)

_STORE = Path(_ROOT) / "data" / "clipboard_history.json"
_MAX = 50
_LOCK = threading.RLock()
_WATCHER_STARTED = False


def _load() -> list[dict]:
    if not _STORE.exists():
        return []
    try:
        return json.loads(_STORE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(items[-_MAX:], indent=2, ensure_ascii=False),
                      encoding="utf-8")


def _add(text: str) -> None:
    if not text or not text.strip():
        return
    text = text.strip()
    if len(text) > 4000:
        text = text[:4000] + "..."
    with _LOCK:
        items = _load()
        if items and items[-1].get("text") == text:
            return
        items.append({"text": text,
                      "ts": datetime.now().isoformat(timespec="seconds")})
        _save(items)


def _try_pyperclip():
    try:
        import pyperclip
        return pyperclip
    except Exception:
        return None


def _watcher_loop():
    pp = _try_pyperclip()
    if pp is None:
        return
    last = None
    while True:
        try:
            cur = pp.paste()
        except Exception:
            time.sleep(2.0)
            continue
        if cur and cur != last:
            _add(cur)
            last = cur
        time.sleep(0.5)


def _ensure_watcher() -> None:
    global _WATCHER_STARTED
    if _WATCHER_STARTED:
        return
    if _try_pyperclip() is None:
        return
    _WATCHER_STARTED = True
    t = threading.Thread(target=_watcher_loop, daemon=True, name="ClipboardWatcher")
    t.start()


# Auto-start when this module is imported.
_ensure_watcher()


@skill(
    name="clipboard_history",
    description="Show the most recent clipboard items captured by the background watcher.",
    patterns=[
        "clipboard history", "clipboard history dikhao",
        "show my clipboard", "kya kya copy kiya",
        "recent clipboard items", "clipboard list",
        "clipboard ka history batao",
    ],
    required_entities=[],
)
def clipboard_history(slots: dict) -> str:
    items = _load()
    if not items:
        return "Clipboard history khali hai. Kuch copy karo aur phir try karo."
    items = items[-10:][::-1]
    lines = ["Recent clipboard items (newest first):"]
    for i, it in enumerate(items, start=1):
        snippet = it["text"].replace("\n", " ⏎ ")
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        lines.append(f"  {i}. {snippet}")
    return "\n".join(lines)


@skill(
    name="copy_history_item",
    description="Push a previous clipboard entry back to the clipboard by index.",
    patterns=[
        "copy item 1", "copy item 2", "copy item 3",
        "history item 1 copy karo", "history se 2 copy karo",
        "clipboard 1 wapas copy karo",
    ],
    required_entities=["spec"],
    prompts={"spec": "Kaunsa item copy karna hai? Number batao."},
)
def copy_history_item(slots: dict) -> str:
    import re
    pp = _try_pyperclip()
    if pp is None:
        return "pyperclip install nahi hai. 'pip install pyperclip' chalao."
    raw = " ".join(str(v) for v in slots.values()) if slots else ""
    m = re.search(r"\d+", raw)
    if not m:
        return "Item number nahi mila."
    idx = int(m.group(0))
    items = _load()[-10:][::-1]
    if idx < 1 or idx > len(items):
        return f"Sirf {len(items)} items hain."
    text = items[idx - 1]["text"]
    try:
        pp.copy(text)
    except Exception as e:
        return f"Clipboard pe copy nahi hua: {e}"
    snippet = text[:60].replace("\n", " ⏎ ") + ("..." if len(text) > 60 else "")
    return f"Item #{idx} clipboard pe daal diya: {snippet}"


@skill(
    name="clipboard_clear",
    description="Wipe stored clipboard history.",
    patterns=[
        "clipboard clear", "clipboard history clear karo",
        "clipboard wipe karo", "clipboard hatao",
    ],
    required_entities=[],
)
def clipboard_clear(slots: dict) -> str:
    _save([])
    return "Clipboard history wipe kar di, sir."
