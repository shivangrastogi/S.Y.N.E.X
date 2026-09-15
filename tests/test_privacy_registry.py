"""The privacy view must cover what AERIS actually stores (§6.39).

`core/privacy_view.py` already existed — a good surface answering "kya store
hota hai, kahan, kitna", with an `encrypted?` flag and an allowlisted purge.
It listed eight stores, and **none of the six holding the most about the
user**: the clipboard log, the face registry, every recorded utterance, the
conversation index, user memory, and the phrasings §6.24 learns.

A privacy view that omits the clipboard history is not a privacy view. These
tests keep the registry honest in the two ways it can rot: a sensitive store
quietly leaving it, and a registered path drifting from the code that writes it.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from core.privacy_view import REGISTRY, SENSITIVE_CLASSES, snapshot

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _rel(name: str) -> str:
    return REGISTRY[name][0].replace("\\", "/")


class TestCoverage:
    @pytest.mark.parametrize("name", [
        "user_memory", "clipboard", "faces", "utterances", "conversation",
        "repair_memory",
    ])
    def test_the_high_sensitivity_stores_are_registered(self, name):
        """Regression guard: these were all missing until §6.39."""
        assert name in REGISTRY, (
            f"{name!r} left the privacy registry — a store holding user data "
            f"that the privacy view cannot see is invisible to the user too.")

    def test_every_entry_is_well_formed(self):
        for name, spec in REGISTRY.items():
            assert len(spec) == 4, name
            rel, enc, cls, purgeable = spec
            assert rel and not os.path.isabs(rel), name
            assert isinstance(enc, bool) and isinstance(purgeable, bool), name
            assert cls, name

    def test_biometric_data_is_classified_as_such(self):
        """Face data is not 'personal' like a note is; the class should say so
        because it changes what a reasonable person wants done with it."""
        assert REGISTRY["faces"][2] == "biometric"

    def test_the_audit_trail_cannot_be_purged(self):
        """A ledger you can delete is not an audit trail."""
        assert REGISTRY["ledger"][3] is False

    def test_utterances_and_user_memory_are_not_casually_purgeable(self):
        for name in ("utterances", "user_memory"):
            assert REGISTRY[name][3] is False, name


class TestPathsMatchTheCodeThatWritesThem:
    """The strongest guard here. I registered the conversation store as
    `semantic_memory.json`; it is actually `.npz`. A registry pointing at a
    file nobody writes reports `exists: False` forever and quietly tells the
    user their conversation log does not exist.
    """

    def test_conversation_matches_semantic_memory(self):
        import core.semantic_memory as sm
        assert os.path.basename(sm._STORE_PATH) == \
            os.path.basename(_rel("conversation"))

    def test_repair_memory_matches_its_module_default(self):
        import core.repair_memory as rm
        assert os.path.basename(rm.DEFAULT_PATH) == \
            os.path.basename(_rel("repair_memory"))

    def test_ledger_matches_autonomy(self):
        import core.autonomy as au
        assert os.path.basename(au._DEFAULT_LEDGER) == \
            os.path.basename(_rel("ledger"))

    def test_goals_matches_goal_system(self):
        import core.goal_system as gs
        assert os.path.basename(gs._DEFAULT_PATH) == \
            os.path.basename(_rel("goals"))


class TestTheEncryptedFlagIsHonest:
    """`encrypted` must report the STATE on disk, not the CAPABILITY.

    `core/vault.py` can encrypt user memory (AES-256, PBKDF2-480k) — but only
    when a passphrase is supplied. Reporting `encrypted: True` because the
    feature exists would be the most damaging kind of lie a privacy surface
    can tell.
    """

    def test_user_memory_is_reported_unencrypted(self):
        assert REGISTRY["user_memory"][1] is False

    def test_and_the_file_on_disk_agrees(self):
        """If this ever fails because the file became a vault, the registry
        entry needs updating — the test is the reminder, not the obstacle."""
        path = ROOT / _rel("user_memory")
        if not path.exists():
            pytest.skip("no user memory on this machine")
        head = path.read_text(encoding="utf-8", errors="ignore")[:200]
        looks_vaulted = "vault_version" in head or "ciphertext" in head
        assert not looks_vaulted, (
            "user_memory.json is now encrypted — set encrypted=True in "
            "core/privacy_view.REGISTRY")

    def test_the_secrets_store_is_the_one_marked_encrypted(self):
        """DPAPI-backed, so this one genuinely is."""
        assert REGISTRY["secrets"][1] is True

    def test_no_other_store_claims_encryption_it_does_not_have(self):
        claimed = {n for n, spec in REGISTRY.items() if spec[1]}
        assert claimed == {"secrets"}, (
            f"{claimed - {'secrets'}} claim encryption; only the DPAPI secrets "
            f"store is actually encrypted at rest today.")


class TestSnapshot:
    def test_it_reports_every_registered_store(self):
        assert {e["name"] for e in snapshot()} == set(REGISTRY)

    def test_a_missing_file_is_reported_not_hidden(self, tmp_path):
        rows = snapshot(root=str(tmp_path))
        assert rows and all(e["exists"] is False for e in rows)
        assert all(e["size_kb"] == 0 for e in rows)

    def test_it_carries_the_class_and_encryption_through(self):
        by_name = {e["name"]: e for e in snapshot()}
        assert by_name["faces"]["class"] == "biometric"
        assert by_name["secrets"]["encrypted"] is True
        assert by_name["clipboard"]["encrypted"] is False

    def test_sensitive_classes_are_a_recognised_set(self):
        for name, spec in REGISTRY.items():
            if spec[2] in SENSITIVE_CLASSES:
                assert spec[2] in ("personal", "biometric", "secret"), name
