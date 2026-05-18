"""Canonical loader + hash for the merged intent set.

Single source of truth shared by ``core.train_intent`` (offline trainer) and
``core.intent_classifier`` / ``core.intent_model`` (runtime classifiers). Both
sides MUST agree byte-for-byte on the merged intents dict — otherwise the
intents_hash diverges and the trained transformer model is silently rejected
as "drifted" even when nothing actually changed.

Always calls ``discover_skills()`` before reading the registry so plugin
patterns are present whether or not the caller has booted them.
"""

from __future__ import annotations

import hashlib
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
INTENTS_PATH = os.path.join(_ROOT, "data", "intents.json")
USER_PATTERNS_PATH = os.path.join(_ROOT, "data", "user_patterns.json")


def load_all_intents(intents_path: str = INTENTS_PATH) -> dict:
    """Read intents.json and merge in every registered skill plugin's patterns
    PLUS any user-defined patterns from ``data/user_patterns.json``.

    User patterns let the assistant grow new utterances at runtime via the
    ``teach_command`` skill without retraining the neural model — the k-NN
    classifier picks them up on the next ``brain.classifier.rebuild()``.

    Idempotent. ``discover_skills`` only imports each skill module once, so
    repeated calls are cheap.
    """
    with open(intents_path, "r", encoding="utf-8") as f:
        intents = json.load(f)
    try:
        from core.skill_registry import discover_skills, patterns_as_intent_dict
        discover_skills("skills")
        for name, cfg in patterns_as_intent_dict().items():
            if name in intents:
                existing = intents[name].get("patterns", [])
                intents[name]["patterns"] = existing + cfg.get("patterns", [])
            else:
                intents[name] = cfg
    except Exception:
        pass

    # User-taught patterns last so they always win (highest precedence).
    user = _load_user_patterns()
    for intent_name, phrases in user.items():
        if intent_name in intents:
            existing = intents[intent_name].get("patterns", [])
            intents[intent_name]["patterns"] = existing + list(phrases)
        else:
            # Unknown intent name — keep the user's mapping; the executor
            # will surface "ye kaam karna seekh raha hoon" if there's no
            # handler for it. Better than silently dropping.
            intents[intent_name] = {"patterns": list(phrases),
                                    "required_entities": [], "prompts": {}}
    return intents


def _load_user_patterns() -> dict[str, list[str]]:
    if not os.path.exists(USER_PATTERNS_PATH):
        return {}
    try:
        with open(USER_PATTERNS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        out: dict[str, list[str]] = {}
        for k, v in (data or {}).items():
            if isinstance(v, list):
                out[str(k)] = [str(x) for x in v if isinstance(x, str)]
        return out
    except Exception:
        return {}


def intents_hash(intents: dict | None = None,
                 intents_path: str = INTENTS_PATH) -> str:
    """MD5 over the canonical-JSON encoding of the merged intent set.

    Pass an already-loaded ``intents`` dict to avoid a second disk read; omit
    it to load fresh.
    """
    if intents is None:
        intents = load_all_intents(intents_path)
    canonical = json.dumps(intents, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()
