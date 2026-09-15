"""Locks in the qr_code dead-end fix (2026-08-01): the QR payload lives after the
trigger word in the raw phrase, not in a `content` slot the extractor fills, so the
skill used to ask "Kya text/URL chahiye QR me?" even when the user already gave it.
`_qr_payload` peels leading trigger words and keeps the tail VERBATIM (URL case/path
preserved). Same 'ambient/embedded argument' class as _fs_query / _proc_name.
"""
from __future__ import annotations

import pytest

from skills.compute_skills import _qr_payload


@pytest.mark.parametrize("slots,expected", [
    # An extracted content slot always wins.
    ({"content": "already extracted"}, "already extracted"),
    ({"content": "x", "raw_text": "qr code banao something-else"}, "x"),
    # Payload recovered from the raw phrase (leading triggers peeled).
    ({"raw_text": "qr code banao hello world"}, "hello world"),
    ({"raw_text": "qr banao MyData"}, "MyData"),
    ({"raw_text": "generate qr for wifi-password-123"}, "wifi-password-123"),
    # URLs keep their case and path (verbatim tail, not lowercased/tokenised).
    ({"raw_text": "make qr https://Example.com/Path"}, "https://Example.com/Path"),
    # Bare trigger with no payload → empty (handler then prompts).
    ({"raw_text": "qr code"}, ""),
    ({"raw_text": "generate qr"}, ""),
])
def test_qr_payload(slots, expected):
    assert _qr_payload(slots) == expected


def test_qr_payload_empty_slots():
    assert _qr_payload({}) == ""
