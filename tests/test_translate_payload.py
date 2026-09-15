"""Locks in the translate dead-end fix (2026-08-01): translate_to_hindi/english
gated on a `query` slot the extractor never fills (payload sits at either end of
the phrase), so they asked "Kya translate karna hai?" instead of reaching the
handler — which gives the actionable "install argostranslate" hint. `_tr_payload`
peels command/filler words; the gate is relaxed so the handler always runs.
"""
from __future__ import annotations

import pytest

from skills.translate import (
    _tr_payload, translate_to_hindi, translate_to_english,
)


@pytest.mark.parametrize("slots,expected", [
    ({"query": "already"}, "already"),                       # extracted slot wins
    ({"raw_text": "hello ko hindi me translate karo"}, "hello"),   # payload before
    ({"raw_text": "translate to hindi hello"}, "hello"),          # payload after
    ({"raw_text": "namaste ka english kya hai"}, "namaste"),
    ({"raw_text": "good morning ko hindi mein bolo"}, "good morning"),  # multi-word
    ({"raw_text": "hindi mein translate karo"}, ""),             # bare → empty
])
def test_tr_payload(slots, expected):
    assert _tr_payload(slots) == expected


def test_translate_reaches_handler_not_deadend():
    """With a payload present the handler runs — it must NOT return the old
    required-entity prompt ('Kya translate karna hai?'). (When argostranslate is
    absent it returns an actionable install hint; when present, a translation.)"""
    for fn in (translate_to_hindi, translate_to_english):
        out = fn({"raw_text": "hello ko hindi me translate karo"})
        assert "kya translate karna hai" not in out.lower()
