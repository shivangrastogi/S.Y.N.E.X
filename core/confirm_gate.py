"""Confirmation gate for IRREVERSIBLE skills.

``core.action_history`` gives reversible actions (clipboard, volume,
brightness) an undo. But the truly destructive skills — kill a process,
wipe clipboard history, forget a trained gesture, delete a vault secret —
cannot be undone after the fact. For those the protection must come
BEFORE execution:

    You:   "kill process chrome"
    AERIS: "kill_process chalane wala hoon (chrome) — pakka? Bolo
            'haan' ya 'cancel'."
    You:   "haan"        → executes
    You:   anything else → aborted, nothing ran

One-turn window, same shape as the feedback-correction window in
``main_engine``. STT misfires get a second chance instead of a dead app.

Opt-in by skill name — the list is curated for DATA-LOSS actions only.
Frequent harmless skills must never nag for confirmation.
"""
from __future__ import annotations

import re

# Skills whose effect cannot be recovered once run. Curated, not derived:
# nagging on harmless skills would train the user to say "haan" blindly.
DESTRUCTIVE_SKILLS: dict[str, str] = {
    # name → short Hinglish description used in the confirm prompt
    "kill_process":             "process force-kill",
    "forget_command":           "user-taught phrase delete",
    "gesture_unteach":          "trained gesture delete",
    "kg_forget":                "memory facts delete",
    "vault_delete":             "vault secret delete",
    "delete_last_memo":         "voice memo delete",
    "clipboard_clear":          "clipboard history wipe",
    "conversation_clear":       "conversation memory wipe",
    "workspace_clear":          "workspace history wipe",
    "gesture_trace_clear":      "gesture log wipe",
    "reset_preferences":        "saare preferences reset",
    "master_permissions_clear": "saari gesture permissions reset",
    "doc_clear":                "document index wipe",
    "speaker_forget":           "enrolled voice delete",
    "empty_recycle_bin":        "recycle bin permanently khali",
}

_YES_RE = re.compile(
    r"^\s*(?:haan+|haa+|ha|yes|yeah|yep|pakka|sure|confirm|kar\s*do|"
    r"do\s*it|karo|theek\s*hai|ok(?:ay)?|bilkul)\s*[.!]?\s*$",
    re.IGNORECASE)


def needs_confirmation(intent: str) -> bool:
    return intent in DESTRUCTIVE_SKILLS


def confirm_prompt(intent: str, slots: dict) -> str:
    """The question AERIS asks before running a destructive skill."""
    what = DESTRUCTIVE_SKILLS.get(intent, intent)
    target = ""
    for key in ("app_name", "content", "raw_text"):
        v = (slots or {}).get(key)
        if v and key != "raw_text":
            target = f" ({v})"
            break
    return (f"Ye {what}{target} hai — wapas nahi hoga. "
            f"Pakka karna hai? Bolo 'haan' ya 'cancel'.")


def is_confirmation(text: str) -> bool:
    return bool(_YES_RE.match(text or ""))
