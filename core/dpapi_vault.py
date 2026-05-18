"""Windows-native encrypted secrets store via the Data Protection API.

OS-concept demo
---------------
Windows ships ``CryptProtectData`` / ``CryptUnprotectData`` (crypt32.dll)
— a kernel-managed key derivation tied to either the current user account
or the local machine. We use the user-bound variant: only the SAME
Windows user on the SAME machine can decrypt. No key management on our
side; the OS handles it (the key is derived from the user's password
and the machine's TPM-protected secret).

This is what cloud SDKs (AWS CLI, Azure CLI) and apps like Chrome use
for the same purpose — we just expose it as a tiny `store/get/list`
surface that AERIS skills can call.

API
---
    store(name, secret)        → True/False
    get(name)                  → str | None
    delete(name)               → True/False
    list_names()               → list[str]   (never the values)
    clear()                    → wipe everything

Storage layout
--------------
``data/vault.bin`` is a single DPAPI-encrypted blob. Inside it: a JSON
mapping ``{name: secret_str}``. We re-encrypt the whole blob on every
write — keeps the layout simple and avoids per-key key rotation.

Threading
---------
A single module-level ``RLock`` serialises reads + writes. Safe to call
from skills running on the breaker thread pool.

Fail-safes
----------
* Non-Windows host → store/get/list return None / [] / False with a
  one-line log warning. Skills surface a friendly install message.
* Missing crypt32 (theoretically possible on a stripped Windows
  image) → same degradation.
* Corrupted vault blob → loaded as empty store; original is preserved
  with a ``.corrupt-<ts>`` suffix so the user can recover manually.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import logging
import os
import sys
import threading
import time
from typing import Optional

from core.atomic_io import write_atomic

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VAULT_PATH = os.path.join(_ROOT, "data", "vault.bin")

_lock = threading.RLock()


# ── DPAPI ctypes plumbing ──────────────────────────────────────────── #

class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _have_dpapi() -> bool:
    return sys.platform == "win32"


def _make_blob(data: bytes) -> _DATA_BLOB:
    n = len(data)
    buf = ctypes.create_string_buffer(data, n)
    return _DATA_BLOB(n, ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))


def _read_blob(blob: _DATA_BLOB) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def _dpapi_encrypt(plain: bytes) -> Optional[bytes]:
    if not _have_dpapi():
        return None
    try:
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        in_blob = _make_blob(plain)
        out_blob = _DATA_BLOB()
        # description=None, optional_entropy=None, reserved=None,
        # prompt_struct=None, flags=0x4 = CRYPTPROTECT_UI_FORBIDDEN
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob), None, None, None, None, 0x04,
            ctypes.byref(out_blob),
        )
        if not ok:
            log.warning("[vault] CryptProtectData failed (%d)",
                        ctypes.get_last_error())
            return None
        try:
            return _read_blob(out_blob)
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception as e:
        log.warning("[vault] encrypt raised: %s", e)
        return None


def _dpapi_decrypt(cipher: bytes) -> Optional[bytes]:
    if not _have_dpapi():
        return None
    try:
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        in_blob = _make_blob(cipher)
        out_blob = _DATA_BLOB()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), None, None, None, None, 0x04,
            ctypes.byref(out_blob),
        )
        if not ok:
            log.warning("[vault] CryptUnprotectData failed (%d)",
                        ctypes.get_last_error())
            return None
        try:
            return _read_blob(out_blob)
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception as e:
        log.warning("[vault] decrypt raised: %s", e)
        return None


# ── Store I/O ──────────────────────────────────────────────────────── #

def _load() -> dict:
    """Read + decrypt the vault. Empty dict if missing/corrupt."""
    if not os.path.exists(_VAULT_PATH):
        return {}
    try:
        with open(_VAULT_PATH, "rb") as f:
            cipher = f.read()
        if not cipher:
            return {}
        plain = _dpapi_decrypt(cipher)
        if plain is None:
            _quarantine_corrupt()
            return {}
        return json.loads(plain.decode("utf-8")) or {}
    except Exception as e:
        log.warning("[vault] load failed (%s) — quarantining", e)
        _quarantine_corrupt()
        return {}


def _quarantine_corrupt() -> None:
    """Rename a corrupt vault file so a fresh one can be written without
    losing the original for forensic recovery."""
    if not os.path.exists(_VAULT_PATH):
        return
    bak = _VAULT_PATH + f".corrupt-{int(time.time())}"
    try:
        os.replace(_VAULT_PATH, bak)
    except OSError as e:
        log.warning("[vault] quarantine rename failed: %s", e)


def _save(d: dict) -> bool:
    """Encrypt + atomically write the whole store."""
    plain = json.dumps(d, ensure_ascii=False).encode("utf-8")
    cipher = _dpapi_encrypt(plain)
    if cipher is None:
        return False
    try:
        write_atomic(_VAULT_PATH, cipher)
        return True
    except Exception as e:
        log.warning("[vault] write failed: %s", e)
        return False


# ── Public surface ─────────────────────────────────────────────────── #

def store(name: str, secret: str) -> bool:
    name = (name or "").strip()
    if not name or not secret:
        return False
    if not _have_dpapi():
        return False
    with _lock:
        d = _load()
        d[name] = secret
        return _save(d)


def get(name: str) -> Optional[str]:
    name = (name or "").strip()
    if not name or not _have_dpapi():
        return None
    with _lock:
        return _load().get(name)


def delete(name: str) -> bool:
    name = (name or "").strip()
    if not name or not _have_dpapi():
        return False
    with _lock:
        d = _load()
        if name not in d:
            return False
        del d[name]
        return _save(d)


def list_names() -> list[str]:
    if not _have_dpapi():
        return []
    with _lock:
        return sorted(_load().keys())


def clear() -> bool:
    if not _have_dpapi():
        return False
    with _lock:
        return _save({})


def available() -> bool:
    """True iff DPAPI is reachable and a tiny round-trip works."""
    if not _have_dpapi():
        return False
    test = _dpapi_encrypt(b"aeris-vault-probe")
    if test is None:
        return False
    rt = _dpapi_decrypt(test)
    return rt == b"aeris-vault-probe"


# ── Smoke test ─────────────────────────────────────────────────────── #

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not available():
        print("DPAPI unavailable on this host — skipping smoke test.")
        sys.exit(0)
    # Use a throwaway path so we don't touch the user's real vault.
    import tempfile
    bak = _VAULT_PATH
    tf = tempfile.NamedTemporaryFile(prefix="aeris_vault_", suffix=".bin",
                                     delete=False)
    tf.close()
    _VAULT_PATH = tf.name
    try:
        print("store github_token:", store("github_token", "ghp_smoketest"))
        print("list:               ", list_names())
        print("get github_token:   ", get("github_token"))
        print("get missing:        ", get("nonexistent"))
        print("delete github_token:", delete("github_token"))
        print("list after delete:  ", list_names())
    finally:
        try: os.unlink(tf.name)
        except OSError: pass
        _VAULT_PATH = bak
