"""Privacy view — "kya store hota hai, kahan, kitna" ek nazar mein (S5).

Trust ka doosra aadha privacy hai: §9 registry ka LIVE roop. ``snapshot()``
har jaane-maane store ki asli file-state batata hai (exists/size/age/
encrypted-class), aur ``apply_action`` sirf ALLOWLISTED purge deta hai —
koi generic delete nahi (galat store udane ka koi rasta hi na ho).

Pure + injectable (root pass hota hai) → tmp-dir pe unit-tests.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# name → (relpath, encrypted?, privacy class, purge-allowed?)
REGISTRY: Dict[str, tuple] = {
    "goals":        ("data/goals.json",              False, "personal", False),
    "ledger":       ("data/ledger.jsonl",            False, "audit",    False),
    "trust_grants": ("data/trust_grants.json",       False, "config",   False),
    "openness":     ("data/openness.json",           False, "learned",  True),
    "graduation":   ("data/routine_graduation.json", False, "learned",  True),
    "routines":     ("data/routines.json",           False, "config",   False),
    "presence":     ("data/presence",                False, "local-only", True),
    "report_cards": ("data/report_card",             False, "derived",  True),
    "secrets":      ("data/secrets",                 True,  "secret",   False),
    "doc_index":    ("data/doc_index",               False, "derived",  True),

    # ── added 2026-09-01 (§6.39) ─────────────────────────────────────
    # The registry listed eight stores and none of the six that hold the most
    # about the user. A privacy view that omits the clipboard log and every
    # recorded utterance is not a privacy view — so these are the ones a
    # "kya store hota hai" question most needs answered.
    #
    # `encrypted` is reported as False for user_memory ON PURPOSE: the
    # capability exists (core/vault.py, AES-256 + PBKDF2-480k) but is only
    # engaged when a passphrase is supplied, and the file on this machine is
    # plaintext. Reporting the *capability* rather than the *state* is how a
    # privacy surface starts lying.
    "user_memory":  ("data/user_memory.json",        False, "personal", False),
    "clipboard":    ("data/clipboard_history.json",  False, "personal", True),
    "faces":        ("data/face_registry.json",      False, "biometric", True),
    "utterances":   ("data/feedback_log.sqlite",     False, "personal", False),
    "repair_memory": ("data/repair_memory.json",     False, "learned",  True),
    "conversation": ("data/semantic_memory.npz",     False, "personal", True),
}

# Stores whose contents are about the user rather than about the machine.
# Used by the tests to assert the high-sensitivity ones stay registered.
SENSITIVE_CLASSES = ("personal", "biometric", "secret")


def _entry(name: str, rel: str, enc: bool, cls: str, purgeable: bool,
           root: str, now: float) -> Dict[str, Any]:
    path = os.path.join(root, rel)
    exists = os.path.exists(path)
    size = 0
    mtime = None
    try:
        if os.path.isdir(path):
            for dp, _, fns in os.walk(path):
                for fn in fns:
                    size += os.path.getsize(os.path.join(dp, fn))
            mtime = os.path.getmtime(path) if exists else None
        elif exists:
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
    except Exception:
        pass
    return {
        "name": name, "path": rel, "exists": exists,
        "size_kb": round(size / 1024, 1),
        "age_days": (round((now - mtime) / 86400, 1) if mtime else None),
        "encrypted": enc, "class": cls, "purgeable": purgeable,
    }


def snapshot(*, root: str = _ROOT,
             now: Optional[float] = None) -> List[Dict[str, Any]]:
    t = time.time() if now is None else now
    return [_entry(n, *spec, root=root, now=t)
            for n, spec in REGISTRY.items()]


def apply_action(action: str, params: Dict[str, Any], *,
                 root: str = _ROOT) -> Dict[str, Any]:
    """Sirf 'purge' — aur sirf allowlisted stores. ValueError → 400."""
    if (action or "").strip().lower() != "purge":
        raise ValueError(f"unknown privacy action {action!r}")
    name = params.get("store")
    spec = REGISTRY.get(name or "")
    if spec is None:
        raise ValueError(f"unknown store {name!r}")
    rel, _enc, _cls, purgeable = spec
    if not purgeable:
        raise ValueError(f"store {name!r} is not purgeable")
    path = os.path.join(root, rel)
    removed = 0
    older_days = params.get("older_than_days")
    cutoff = (time.time() - float(older_days) * 86400) if older_days else None
    try:
        if os.path.isdir(path):
            for dp, _, fns in os.walk(path):
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    if cutoff is None or os.path.getmtime(fp) < cutoff:
                        os.remove(fp)
                        removed += 1
        elif os.path.exists(path):
            if cutoff is None or os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed = 1
    except Exception as e:
        log.warning("[privacy] purge %s failed: %s", name, e)
        return {"ok": False, "store": name, "error": str(e)}
    log.info("[privacy] purged %s: %d file(s)", name, removed)
    return {"ok": True, "store": name, "removed": removed}
