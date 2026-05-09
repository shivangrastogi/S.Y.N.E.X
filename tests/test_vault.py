"""Tests for the encrypted memory vault."""

from __future__ import annotations

import os

import pytest

from core import vault

pytestmark = pytest.mark.skipif(
    not vault.is_available(),
    reason="cryptography package not installed",
)


def test_round_trip(tmp_path):
    path = str(tmp_path / "vault.json")
    payload = {"facts": {"name": {"value": "Shivang"}}, "notes": [], "preferences": {}}

    vault.encrypt_to_file(path, payload, "supersecret")
    assert vault.is_vault_file(path)

    loaded = vault.decrypt_from_file(path, "supersecret")
    assert loaded == payload


def test_wrong_passphrase_raises(tmp_path):
    path = str(tmp_path / "vault.json")
    vault.encrypt_to_file(path, {"facts": {}}, "right")
    with pytest.raises(vault.VaultError):
        vault.decrypt_from_file(path, "wrong")


def test_is_vault_file_returns_false_for_plain_json(tmp_path):
    path = str(tmp_path / "plain.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"facts": {}}')
    assert not vault.is_vault_file(path)


def test_is_vault_file_returns_false_for_missing(tmp_path):
    assert not vault.is_vault_file(str(tmp_path / "missing.json"))


def test_user_memory_with_passphrase_persists(tmp_path):
    from core.memory import UserMemory

    path = str(tmp_path / "mem.json")

    mem = UserMemory(path, passphrase="vault-pass")
    mem.set("name", "Shivang")
    mem.set("location", "Delhi")

    # Reload — same passphrase should decrypt cleanly
    mem2 = UserMemory(path, passphrase="vault-pass")
    assert mem2.get("name") == "Shivang"
    assert mem2.get("location") == "Delhi"

    # File on disk must NOT contain plaintext "Shivang"
    with open(path, "rb") as f:
        blob = f.read()
    assert b"Shivang" not in blob
    assert b"Delhi" not in blob


def test_enable_vault_migrates_plaintext(tmp_path):
    from core.memory import UserMemory

    path = str(tmp_path / "mem.json")
    mem = UserMemory(path)
    mem.set("name", "Shivang")
    assert not vault.is_vault_file(path)

    mem.enable_vault("new-pass")
    assert vault.is_vault_file(path)

    mem2 = UserMemory(path, passphrase="new-pass")
    assert mem2.get("name") == "Shivang"
