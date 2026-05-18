"""Voice-command trainer — let the user teach AERIS new utterances.

The merged intent loader (``core/intent_loader.load_all_intents``) reads
``data/user_patterns.json`` as the LAST contributor, so anything written
there wins over both ``intents.json`` and plugin-decorator patterns.

After teaching, the user must trigger an index rebuild for the change
to take effect. We do that automatically by calling
``classifier.rebuild()`` on the active brain — no app restart required.
The neural transformer model is NOT retrained (would take ~2 hours);
the brain's k-NN classifier picks up the new pattern instead, and the
``_neural_active`` flag keeps the neural path off for the new intent
until the user explicitly retrains.

Skills:
  * ``teach_command``   — "from now on 'open ide' means open_app vscode"
  * ``forget_command``  — remove a taught phrase
  * ``list_taught``     — show the current user-pattern table
"""
from __future__ import annotations

import json
import logging
import os
import re

from core.atomic_io import write_atomic_json
from core.skill_registry import skill, REGISTRY

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PATH = os.path.join(_ROOT, "data", "user_patterns.json")


def _load() -> dict[str, list[str]]:
    if not os.path.exists(_PATH):
        return {}
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        log.warning("[teach] load failed: %s", e)
        return {}


def _save(d: dict) -> None:
    write_atomic_json(_PATH, d, indent=2)


def _intent_in_file(intent: str) -> bool:
    """Cheap check: does ``intents.json`` define this intent name?"""
    try:
        from core.intent_loader import INTENTS_PATH
        with open(INTENTS_PATH, "r", encoding="utf-8") as f:
            return intent in (json.load(f) or {})
    except Exception:
        return False


def _rebuild_brain() -> bool:
    """Best-effort: poke the running brain so the next predict() picks
    up the new pattern. Falls back to a "manual rebuild required" hint
    if no brain is attached (e.g. headless test run).
    """
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return False
        for w in app.topLevelWidgets():
            brain_worker = getattr(w, "_brain", None)
            engine = getattr(brain_worker, "_engine", None)
            if engine is not None and getattr(engine, "brain", None) is not None:
                engine.brain.classifier.rebuild()
                return True
    except Exception as e:
        log.debug("[teach] brain rebuild failed: %s", e)
    return False


# Match  "from now on 'X' means Y"  OR  "X = Y"  OR  "teach Y X"
_TEACH_RE = re.compile(
    r"""
    ^\s*
    (?:
      from\s+now\s+on\s+['\"](?P<phrase1>[^'\"]+)['\"]\s+
        (?:means|=|->|→)\s+(?P<intent1>[\w_\-]+)\b
      |
      teach\s+(?P<intent2>[\w_\-]+)\s+['\"](?P<phrase2>[^'\"]+)['\"]
      |
      (?P<intent3>[\w_\-]+)\s*[:=]\s*['\"](?P<phrase3>[^'\"]+)['\"]
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


@skill(
    name="teach_command",
    description="Teach AERIS a new utterance for an existing intent or skill",
    patterns=[
        "from now on 'open ide' means open_app",
        "teach open_app 'fire up vscode'",
        "open_app = 'launch editor'",
        "teach command", "new command", "remember this command",
        "command sikhao", "command teach karo",
    ],
    required_entities=["content"],
    prompts={"content": "Format: from now on 'phrase' means intent_name"},
)
def teach_command(slots: dict) -> str:
    raw = (slots.get("content") or "").strip()
    m = _TEACH_RE.match(raw)
    if not m:
        return ("Format: \"from now on 'phrase' means intent_name\" "
                "or \"teach intent_name 'phrase'\".")
    phrase = (m.group("phrase1") or m.group("phrase2") or m.group("phrase3") or "").strip()
    intent = (m.group("intent1") or m.group("intent2") or m.group("intent3") or "").strip()
    if not phrase or not intent:
        return "Phrase aur intent dono chahiye."

    # Warn only if the target intent is unknown to BOTH the plugin
    # registry AND the canonical intents.json (built-in intents like
    # ``open_app`` are dispatched by the executor, not registered as
    # plugins, so we have to check both surfaces).
    intent_known = intent in REGISTRY or _intent_in_file(intent)
    suffix = "" if intent_known else (
        f" (warning: '{intent}' is not in intents.json or the skill "
        "registry; phrase will route to a generic 'I'm learning that' "
        "until you add a handler)"
    )

    d = _load()
    phrases = list(d.get(intent, []))
    if phrase.lower() in (p.lower() for p in phrases):
        return f"Phrase already taught: '{phrase}' → {intent}."
    phrases.append(phrase)
    d[intent] = phrases
    try:
        _save(d)
    except Exception as e:
        return f"Save fail: {e}"
    rebuilt = _rebuild_brain()
    rebuild_msg = (" Brain re-indexed live." if rebuilt
                   else " Restart AERIS for the new phrase to take effect.")
    return f"Taught: '{phrase}' → {intent}.{rebuild_msg}{suffix}"


@skill(
    name="forget_command",
    description="Remove a user-taught phrase (or all phrases for an intent)",
    patterns=[
        "forget command", "remove command", "untrain",
        "forget 'phrase'", "command bhul jao",
        "remove taught command",
    ],
    required_entities=["content"],
    prompts={"content": "Format: 'phrase' OR intent_name (all phrases for that intent)"},
)
def forget_command(slots: dict) -> str:
    raw = (slots.get("content") or "").strip().strip("'\"")
    if not raw:
        return "Phrase ya intent_name batao."
    d = _load()
    # 1. Try exact intent-name match → wipe all its taught phrases.
    if raw in d:
        n = len(d[raw])
        del d[raw]
        _save(d)
        _rebuild_brain()
        return f"Removed {n} taught phrases for intent '{raw}'."
    # 2. Try phrase match across all intents.
    removed_from: list[str] = []
    for intent, phrases in list(d.items()):
        keep = [p for p in phrases if p.lower() != raw.lower()]
        if len(keep) != len(phrases):
            if keep:
                d[intent] = keep
            else:
                del d[intent]
            removed_from.append(intent)
    if not removed_from:
        return f"'{raw}' kuch bhi nahi mila taught list me."
    _save(d)
    _rebuild_brain()
    return f"Removed phrase '{raw}' from: {', '.join(removed_from)}."


@skill(
    name="list_taught",
    description="Show every user-taught phrase",
    patterns=[
        "list taught", "list commands", "show taught", "what commands",
        "taught commands", "commands list",
    ],
)
def list_taught(_slots: dict) -> str:
    d = _load()
    if not d:
        return "Koi user-taught command nahi hai. Try 'teach_command' first."
    out = []
    for intent in sorted(d):
        phrases = d[intent]
        out.append(f"  {intent} ({len(phrases)} phrase{'s' if len(phrases) > 1 else ''}):")
        for p in phrases:
            out.append(f"    · {p}")
    return f"{len(d)} intents have user-taught phrases:\n" + "\n".join(out)
