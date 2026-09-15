"""Locks in three more 'embedded-argument' dead-end fixes (2026-08-02): date_diff,
recall, text_expand all gated on a `content` slot the extractor doesn't fill, so
they asked a needless question even though the argument was in the phrase. Each now
recovers the argument from raw_text and the required-entity gate is relaxed.

Part of the broader dead-end sweep (see memory: aeris_routing_audit). Pure/near-pure
— recall is tested via its recovery helper to avoid loading the semantic encoder.
"""
from __future__ import annotations

import pytest

from skills.info_skills import date_diff, currency_convert
from skills.memory_skills import _recall_query
from skills.snippet_skills import text_expand
from skills.vault_skills import _vault_name, vault_get
from skills.expense_tracker import _task_text, add_task
from skills.brightness_control import _parse_percent as _brightness_pct
from skills.volume_control import _parse_percent as _volume_pct
from skills.automation_skill import _routine_name
from skills.clipboard_history import copy_history_item
from skills.file_ops import _open_query, _folder_name


# ── date_diff: dates in the phrase → computed, not a format prompt ───────
@pytest.mark.parametrize("phrase,needle", [
    ("days between 2026-01-01 and 2026-02-01", "+31 day"),
    ("date diff 2026-02-01 and 2026-01-01", "-31 day"),
])
def test_date_diff_reaches_handler(phrase, needle):
    out = date_diff({"raw_text": phrase})
    assert needle in out
    assert "format:" not in out.lower()  # not the old dead-end prompt


def test_date_diff_content_slot_wins():
    assert "+31 day" in date_diff({"content": "2026-01-01 and 2026-02-01"})


# ── recall: query recovered from the phrase (helper — no encoder load) ───
@pytest.mark.parametrize("slots,expected", [
    ({"content": "already"}, "already"),
    ({"raw_text": "recall mera favourite colour"}, "mera favourite colour"),
    ({"raw_text": "yaad karo maine kya kaha tha"}, "maine kya kaha tha"),
    ({"raw_text": "what did i say about the project"}, "the project"),
    ({"raw_text": "recall"}, ""),  # bare trigger → empty (handler asks)
])
def test_recall_query_recovery(slots, expected):
    assert _recall_query(slots) == expected


# ── text_expand: trigger key recovered → lookup, not "batao" prompt ──────
def test_text_expand_reaches_lookup():
    out = text_expand({"raw_text": "expand brb"})
    assert "trigger batao" not in out.lower()   # not the old dead-end
    # Reached the snippet lookup (either found it, or a clean "not found").


def test_text_expand_bare_still_prompts():
    # "expand" with no key → normalise strips to empty → prompt is correct here.
    out = text_expand({"raw_text": "expand"})
    assert "trigger batao" in out.lower()


# ── currency_convert: amount+currencies in the phrase → converted ────────
@pytest.mark.parametrize("phrase", ["100 usd to inr", "convert 50 eur to usd"])
def test_currency_convert_reaches_handler(phrase):
    out = currency_convert({"raw_text": phrase})
    assert "=" in out and "Format:" not in out  # converted, not the dead-end prompt


# ── vault_get: secret name recovered from the phrase ────────────────────
@pytest.mark.parametrize("slots,expected", [
    ({"content": "already"}, "already"),
    ({"raw_text": "vault se github_token nikalo"}, "github_token"),
    ({"raw_text": "secret get karo aws_key"}, "aws_key"),
    ({"raw_text": "retrieve secret my_password"}, "my_password"),  # 1-token name kept
    ({"raw_text": "vault get"}, ""),
])
def test_vault_name_recovery(slots, expected):
    assert _vault_name(slots) == expected


def test_vault_get_reaches_lookup_no_deadend():
    # Fake key → reaches lookup and reports not-found (never the old "kaunsa
    # secret?" prompt, and never echoes a secret value).
    out = vault_get({"raw_text": "vault se zzznonexistentkey nikalo"})
    assert "kaunsa secret" not in out.lower()
    assert "secret name batao" not in out.lower()


# ── add_task: task text recovered from the phrase (verbatim, keeps 'schedule') ──
@pytest.mark.parametrize("slots,expected", [
    ({"task_text": "already"}, "already"),
    ({"raw_text": "add task write the report"}, "write the report"),
    ({"raw_text": "task add karo project finish karna hai"}, "project finish karna hai"),
    ({"raw_text": "todo add karo gym jana"}, "gym jana"),
    ({"raw_text": "add task schedule the meeting"}, "schedule the meeting"),  # keeps 'schedule'
    ({"raw_text": "gym jana add karo"}, "gym jana"),                          # trailing trigger
    ({"raw_text": "remind me to call mom tomorrow"}, "call mom tomorrow"),
    ({"raw_text": "kaam add karo"}, ""),                                      # bare → empty
])
def test_add_task_text_recovery(slots, expected):
    assert _task_text(slots) == expected


def test_add_task_bare_prompts_without_workbook_touch():
    # A bare "add task" returns the content prompt BEFORE opening the workbook —
    # so this is side-effect-free (no jarvis_workbook.xlsx mutation) and proves
    # the handler is reached (not the old required-entity gate).
    out = add_task({"raw_text": "add task"})
    assert "kya task add karna" in out.lower()


# ── brightness_set / volume_set: level parsed from the raw phrase ────────
# (Only the pure parser is tested — calling the handlers would change the real
# screen brightness / system volume. Feeding it raw_text is the whole fix.)
@pytest.mark.parametrize("phrase,expected", [
    ("brightness 75", 75), ("screen 25 percent", 25),
    ("display 80", 80), ("brightness", None),
])
def test_brightness_percent_from_phrase(phrase, expected):
    assert _brightness_pct(phrase) == expected


@pytest.mark.parametrize("phrase,expected", [
    ("volume 60 kar do", 60), ("awaaz 40", 40),
    ("set volume to 75", 75), ("volume", None),
])
def test_volume_percent_from_phrase(phrase, expected):
    assert _volume_pct(phrase) == expected


# ── routine_enable/disable: routine name recovered from the phrase ──────
@pytest.mark.parametrize("slots,expected", [
    ({"content": "already"}, "already"),
    ({"raw_text": "enable morning routine"}, "morning"),
    ({"raw_text": "enable coding mode"}, "coding"),
    ({"raw_text": "disable battery saver"}, "battery saver"),
    ({"raw_text": "routine on karo"}, ""),  # generic → empty → handler prompts
])
def test_routine_name_recovery(slots, expected):
    assert _routine_name(slots) == expected


# ── copy_history_item: index parsed from the phrase (no gate) ───────────
def test_copy_history_item_reaches_parse():
    # Out-of-range index → reaches the range-check without writing the clipboard,
    # and never the old "kaunsa item?" required-entity prompt.
    out = copy_history_item({"raw_text": "copy item 999"})
    assert "kaunsa item" not in out.lower()


# ── open_file / create_folder: name recovered from the phrase ───────────
# (Recovery helpers only — calling the handlers would open a file / create a real
# folder. Feeding raw_text to the recoverer is the whole fix.)
@pytest.mark.parametrize("slots,expected", [
    ({"query": "already.pdf"}, "already.pdf"),
    ({"raw_text": "resume kholo"}, "resume"),
    ({"raw_text": "report.pdf file kholo"}, "report.pdf"),  # extension preserved
    ({"raw_text": "find and open budget"}, "budget"),
    ({"raw_text": "file kholo"}, ""),
])
def test_open_file_query_recovery(slots, expected):
    assert _open_query(slots) == expected


@pytest.mark.parametrize("slots,expected", [
    ({"query": "MyFolder"}, "MyFolder"),
    ({"raw_text": "create folder ProjectX"}, "ProjectX"),
    ({"raw_text": "naya folder banao Reports"}, "Reports"),
    ({"raw_text": "make a new directory Photos"}, "Photos"),
    ({"raw_text": "folder banao"}, ""),
])
def test_create_folder_name_recovery(slots, expected):
    assert _folder_name(slots) == expected
