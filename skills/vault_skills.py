"""Vault skills — store/get/list/delete secrets via DPAPI.

Security notes
--------------
* ``vault_get`` NEVER returns the secret in its response text. It
  copies the secret to the clipboard and replies with a length-only
  acknowledgement. This keeps the secret out of the structured log
  (which is otherwise grep-friendly + persisted).
* ``vault_list`` exposes ONLY names. Values are never sent.
* ``vault_delete`` is unguarded — assume the user means it; if they
  didn't they can always re-store.
"""
from __future__ import annotations

import logging
import re

from core import dpapi_vault as _vault
from core.skill_registry import skill

log = logging.getLogger(__name__)


_STORE_RE = re.compile(r"^\s*([\w.\-]+)\s*[=:]\s*(.+)$", re.DOTALL)


@skill(
    name="vault_store",
    description="Encrypt + store a secret in the Windows DPAPI vault",
    patterns=[
        "vault store", "store secret", "save secret", "secret save karo",
        "vault add", "add to vault", "credential save",
    ],
    required_entities=["content"],
    prompts={"content": "Format: 'name=secret_value' (e.g. 'github_token=ghp_xxx')"},
)
def vault_store(slots: dict) -> str:
    if not _vault.available():
        return "Vault sirf Windows pe chalta hai (DPAPI required)."
    raw = (slots.get("content") or "").strip()
    m = _STORE_RE.match(raw)
    if not m:
        return "Format: 'name=secret_value'."
    name = m.group(1).strip()
    secret = m.group(2).strip()
    if not name or not secret:
        return "Name aur secret dono chahiye."
    if _vault.store(name, secret):
        # Intentionally do NOT log the secret length or echo any of it.
        return f"Stored secret '{name}'. Use 'vault get {name}' to retrieve."
    return "Store fail ho gaya."


# Command/filler words peeled from the raw phrase to recover the secret NAME when
# the extractor didn't fill `content` ("vault se github_token nikalo" → "github_token").
# NOT "token"/"key"/"password" — those are often part of the name itself.
_VAULT_STOP = {
    "vault", "get", "secret", "retrieve", "credential", "creds", "karo", "kar",
    "kardo", "do", "se", "me", "mein", "from", "nikalo", "nikaal", "batao",
    "dedo", "dikhao", "please", "zara", "ka", "ki", "ko", "the", "my", "mera",
}


def _vault_name(slots: dict) -> str:
    n = (slots.get("content") or "").strip()
    if n:
        return n
    raw = (slots.get("raw_text") or slots.get("text") or "").strip()
    kept = [w for w in raw.split() if w.lower().strip(":,-") not in _VAULT_STOP]
    return " ".join(kept).strip()


@skill(
    name="vault_get",
    description="Decrypt a vault secret and copy it to the clipboard (never to chat log)",
    patterns=[
        "vault get", "get secret", "retrieve secret",
        "vault retrieve", "credential get", "secret get karo",
    ],
    # No hard gate: the secret NAME follows the trigger ("vault se github_token
    # nikalo"), not a `content` slot the extractor fills — gating dead-ends at
    # "kaunsa secret?" even when named. _vault_name recovers it; a wrong guess is
    # safe (handler returns length only + "not found", never the secret value).
    required_entities=[],
    prompts={},
)
def vault_get(slots: dict) -> str:
    if not _vault.available():
        return "Vault sirf Windows pe."
    name = _vault_name(slots)
    if not name:
        return "Secret name batao."
    val = _vault.get(name)
    if val is None:
        return f"Secret '{name}' nahi mila."
    try:
        import pyperclip
        pyperclip.copy(val)
        copied = " (copied to clipboard)"
    except Exception:
        copied = " (pyperclip missing — secret not auto-copied; install pyperclip)"
    # Length-only acknowledgement — never echo the secret itself.
    return f"Retrieved '{name}' · {len(val)} chars{copied}"


@skill(
    name="vault_list",
    description="List all stored secret names (values never returned)",
    patterns=[
        "vault list", "list secrets", "list vault", "secrets dikhao",
        "what secrets", "vault dikhao",
    ],
)
def vault_list(_slots: dict) -> str:
    if not _vault.available():
        return "Vault sirf Windows pe."
    names = _vault.list_names()
    if not names:
        return "Vault khaali hai. 'vault store name=value' se add karo."
    return f"{len(names)} secrets stored:\n  " + "\n  ".join(names)


@skill(
    name="vault_delete",
    description="Remove a secret from the vault",
    patterns=[
        "vault delete", "delete secret", "remove secret",
        "vault remove", "secret delete karo",
    ],
    required_entities=["content"],
    prompts={"content": "Kaunsa secret delete karna hai?"},
)
def vault_delete(slots: dict) -> str:
    if not _vault.available():
        return "Vault sirf Windows pe."
    name = (slots.get("content") or "").strip()
    if not name:
        return "Secret name batao."
    if _vault.delete(name):
        return f"Deleted '{name}'."
    return f"Secret '{name}' nahi mila."
