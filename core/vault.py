"""AES-256 encrypted vault for the user memory file.

Uses cryptography.Fernet (AES-128-CBC + HMAC-SHA256) with the key derived
from a passphrase via PBKDF2-SHA256 (480 000 iterations). The salt is stored
in the file header so the same passphrase can decrypt across restarts.

File layout (UTF-8 JSON wrapper):
    {
      "vault_version": 1,
      "salt": "<base64-encoded random 16 bytes>",
      "ciphertext": "<base64-encoded Fernet token>"
    }
"""

from __future__ import annotations

import base64
import json
import os
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _AVAILABLE = True
except ImportError:
    Fernet = None
    InvalidToken = Exception
    _AVAILABLE = False


_PBKDF2_ITERATIONS = 480_000
_VAULT_VERSION = 1


class VaultError(Exception):
    pass


def is_available() -> bool:
    return _AVAILABLE


def is_vault_file(path: str) -> bool:
    """True iff the file exists and looks like an encrypted vault wrapper."""
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            blob = json.load(f)
        return isinstance(blob, dict) and "vault_version" in blob and "ciphertext" in blob
    except Exception:
        return False


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if not _AVAILABLE:
        raise VaultError("cryptography package not installed")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_to_file(path: str, payload: dict, passphrase: str) -> None:
    if not _AVAILABLE:
        raise VaultError("cryptography package not installed; run: pip install cryptography")
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    fernet = Fernet(key)
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    token = fernet.encrypt(plaintext)
    wrapper = {
        "vault_version": _VAULT_VERSION,
        "salt": base64.b64encode(salt).decode("ascii"),
        "ciphertext": token.decode("ascii"),
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(wrapper, f, indent=2)
    os.replace(tmp, path)


def decrypt_from_file(path: str, passphrase: str) -> dict:
    if not _AVAILABLE:
        raise VaultError("cryptography package not installed")
    with open(path, "r", encoding="utf-8") as f:
        wrapper = json.load(f)
    if "ciphertext" not in wrapper or "salt" not in wrapper:
        raise VaultError("file is not a vault wrapper")
    salt = base64.b64decode(wrapper["salt"])
    key = _derive_key(passphrase, salt)
    try:
        plaintext = Fernet(key).decrypt(wrapper["ciphertext"].encode("ascii"))
    except InvalidToken as e:
        raise VaultError("wrong passphrase or corrupted vault") from e
    return json.loads(plaintext.decode("utf-8"))


def migrate_plaintext_to_vault(path: str, passphrase: str) -> Optional[dict]:
    """Read a plaintext JSON memory file, re-write it as an encrypted vault."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    encrypt_to_file(path, data, passphrase)
    return data
