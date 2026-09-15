"""Confirm gate — irreversible skills must ask before executing."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.confirm_gate import (
    DESTRUCTIVE_SKILLS, confirm_prompt, is_confirmation, needs_confirmation,
)


def test_destructive_set_membership():
    assert needs_confirmation("kill_process")
    assert needs_confirmation("vault_delete")
    assert needs_confirmation("kg_forget")
    # Frequent harmless skills must NEVER nag.
    assert not needs_confirmation("open_app")
    assert not needs_confirmation("battery_status")
    assert not needs_confirmation("screenshot_full")
    assert not needs_confirmation("volume_up")


def test_confirmation_phrases():
    for yes in ("haan", "Haan", "yes", "pakka", "kar do", "theek hai",
                "ok", "bilkul", "yeah", "sure"):
        assert is_confirmation(yes), yes


def test_non_confirmations():
    for no in ("cancel", "nahi", "ruko", "wait", "kya?", "no",
               "haan nahi karna",       # mixed signal — NOT a clean yes
               "open chrome"):
        assert not is_confirmation(no), no


def test_prompt_mentions_target_and_finality():
    p = confirm_prompt("kill_process", {"app_name": "chrome"})
    assert "chrome" in p
    assert "wapas nahi" in p         # communicates irreversibility
    assert "haan" in p and "cancel" in p


def test_prompt_without_target_still_sane():
    p = confirm_prompt("clipboard_clear", {})
    assert "clipboard" in p.lower()
    assert "haan" in p


def test_every_destructive_entry_has_description():
    for intent, desc in DESTRUCTIVE_SKILLS.items():
        assert desc and len(desc) > 3, intent
