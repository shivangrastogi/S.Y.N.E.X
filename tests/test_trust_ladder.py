"""Tests for core.trust_ladder — the autonomy safety spine (Sentient-Partner Phase 3)."""
from __future__ import annotations

import pytest

from core.trust_ladder import (
    classify, may_auto, AUTO, OFFER, CONFIRM, FORBID,
)


# ── base risk tiers (default autonomy L2) ────────────────────────────────
@pytest.mark.parametrize("intent,expected", [
    # forbid — irreversible / high-impact
    ("shutdown_pc", FORBID),
    ("restart_pc", FORBID),
    ("factory_reset", FORBID),
    ("empty_recycle_bin", FORBID),
    ("pay_bill", FORBID),
    # confirm — outward (reaches other people)
    ("send_whatsapp", CONFIRM),
    ("compose_email", CONFIRM),
    ("post_tweet", CONFIRM),
    # offer — reversible state change
    ("create_note", OFFER),
    ("set_reminder", OFFER),
    ("add_task", OFFER),
    ("quick_timer", OFFER),
    # auto — local, reversible, silent
    ("get_time", AUTO),
    ("system_stats", AUTO),
    ("open_app", AUTO),
    ("search_web", AUTO),
    ("volume_up", AUTO),
])
def test_base_tiers(intent, expected):
    assert classify(intent, level=2).level == expected


def test_destructive_from_confirm_gate():
    # kill_process is in confirm_gate.DESTRUCTIVE_SKILLS → at least CONFIRM.
    d = classify("kill_process", level=2)
    assert d.level in (CONFIRM, FORBID)


def test_unknown_defaults_to_confirm():
    assert classify("", level=2).level == CONFIRM


# ── autonomy clamp — lower level = more conservative, never laxer ────────
def test_manual_level_blocks_auto_and_offer():
    # L0: nothing silent, nothing on a simple yes → min CONFIRM
    assert classify("open_app", level=0).level == CONFIRM      # was AUTO
    assert classify("create_note", level=0).level == CONFIRM   # was OFFER


def test_careful_level_downgrades_auto_to_offer():
    # L1: may offer, never silent
    assert classify("open_app", level=1).level == OFFER        # was AUTO
    assert classify("create_note", level=1).level == OFFER     # stays OFFER


def test_default_level_allows_safe_auto():
    assert classify("open_app", level=2).level == AUTO


def test_clamp_never_relaxes_confirm_or_forbid():
    # High autonomy must NOT turn a destructive/outward/forbidden action safe.
    assert classify("send_whatsapp", level=3).level == CONFIRM
    assert classify("shutdown_pc", level=3).level == FORBID


# ── convenience + decision object ────────────────────────────────────────
def test_may_auto_helper():
    assert may_auto("get_time", level=2) is True
    assert may_auto("shutdown_pc", level=2) is False
    assert may_auto("send_whatsapp", level=2) is False
    assert may_auto("create_note", level=2) is False   # offer, not auto


def test_decision_reason_and_flags():
    d = classify("shutdown_pc", level=2)
    assert d.blocked is True and d.may_auto is False and d.reason
