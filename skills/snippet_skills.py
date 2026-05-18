"""Text-expansion skills — trigger-key → expansion via clipboard.

Snippets live in ``data/snippets.json``. ``{{date}}`` / ``{{time}}``
inside an expansion expand to today's date / now's clock at trigger
time, so a snippet like ``"datetime": "{{date}} {{time}}"`` always
produces a fresh stamp.

Skills exposed:
  * ``text_expand``        — "expand sig"  →  copies expansion to clipboard
  * ``text_expand_list``   — show all snippet triggers
  * ``text_expand_add``    — "add snippet trig=value" → persists to JSON
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime

from core.atomic_io import write_atomic_json
from core.skill_registry import skill

log = logging.getLogger(__name__)


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "data", "snippets.json")


def _load() -> dict:
    if not os.path.exists(_PATH):
        return {}
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("snippets", {})
    except Exception as e:
        log.warning("[snippets] load failed: %s", e)
        return {}


def _save(snips: dict) -> None:
    write_atomic_json(_PATH, {"snippets": snips}, indent=2)


def _expand_placeholders(text: str) -> str:
    """Replace ``{{date}}`` and ``{{time}}`` with current values."""
    now = datetime.now()
    return (text
            .replace("{{date}}", now.strftime("%Y-%m-%d"))
            .replace("{{time}}", now.strftime("%H:%M")))


def _normalise_trigger(raw: str) -> str:
    """Strip 'expand ' / 'snippet ' prefixes, lowercase, strip ws."""
    t = (raw or "").strip().lower()
    for prefix in ("expand ", "snippet ", "snip ", "type "):
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
            break
    return t


@skill(
    name="text_expand",
    description="Expand a snippet trigger to its full text on the clipboard",
    patterns=[
        "expand sig", "expand email", "expand date", "expand time",
        "snippet sig", "snippet email", "type sig", "type email",
        "expand", "paste sig", "sig copy karo", "snippet expand karo",
    ],
    required_entities=["content"],
    prompts={"content": "Kaunsa snippet expand karna hai? (e.g. sig, email, date)"},
)
def text_expand(slots: dict) -> str:
    trig = _normalise_trigger(slots.get("content") or "")
    if not trig:
        return "Snippet trigger batao. 'text expand list' se sab dekho."
    snips = _load()
    if trig not in snips:
        # Try a fuzzy fallback — first key that startswith.
        cand = [k for k in snips if k.startswith(trig)]
        if len(cand) == 1:
            trig = cand[0]
        elif cand:
            return f"Multiple matches: {', '.join(cand)}. Be more specific."
        else:
            return f"Snippet '{trig}' nahi mila. Available: {', '.join(sorted(snips))}."
    text = _expand_placeholders(str(snips[trig]))
    try:
        import pyperclip
        pyperclip.copy(text)
    except Exception:
        return f"Expanded '{trig}' but pyperclip nahi hai:\n{text}"
    # Echo a short preview so the user sees it worked.
    preview = text.replace("\n", " ↵ ")[:80]
    return f"'{trig}' → clipboard ({len(text)} chars): {preview}"


@skill(
    name="text_expand_list",
    description="List every available snippet trigger",
    patterns=[
        "list snippets", "show snippets", "snippets list",
        "what snippets", "snippets dikhao", "expand list",
    ],
)
def text_expand_list(_slots: dict) -> str:
    snips = _load()
    if not snips:
        return "Koi snippets nahi hain. 'add snippet trig=value' se add karo."
    lines = [f"  {k:14s} → {(_expand_placeholders(str(v))[:60]).strip()}"
             for k, v in sorted(snips.items())]
    return f"{len(snips)} snippets:\n" + "\n".join(lines)


_ADD_RE = re.compile(r"^\s*([\w\-]+)\s*[=:]\s*(.+)$", re.DOTALL)


@skill(
    name="text_expand_add",
    description="Add or update a snippet: 'add snippet trig=value text'",
    patterns=[
        "add snippet", "new snippet", "snippet add karo",
        "save snippet", "store snippet",
    ],
    required_entities=["content"],
    prompts={"content": "Format: 'trigger=value' (e.g. 'addr=123 Main St')"},
)
def text_expand_add(slots: dict) -> str:
    raw = (slots.get("content") or "").strip()
    m = _ADD_RE.match(raw)
    if not m:
        return "Format: 'trigger=expansion' (e.g. 'addr=123 Main St')."
    trig = m.group(1).lower().strip()
    value = m.group(2).strip()
    if not trig or not value:
        return "Trigger aur value dono chahiye."
    snips = _load()
    existed = trig in snips
    snips[trig] = value
    try:
        _save(snips)
    except Exception as e:
        return f"Save fail: {e}"
    return f"{'Updated' if existed else 'Added'} snippet '{trig}' ({len(value)} chars)."
