"""Tests for streaming endpointing + VAD energy gate (core/vad_stream.py)."""
from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.vad_stream import Endpointer, is_speech


# ── energy gate ─────────────────────────────────────────────────────────


def _pcm16(amplitude, n=400):
    return struct.pack("<%dh" % n, *([amplitude] * n))


def test_is_speech_silence_vs_voice():
    assert is_speech(_pcm16(0)) is False              # pure silence
    assert is_speech(_pcm16(50)) is False             # quiet room tone
    assert is_speech(_pcm16(5000)) is True            # loud → speech
    assert is_speech(b"") is False
    assert is_speech(b"\x01") is False                # malformed/short


def test_is_speech_threshold_tunable():
    chunk = _pcm16(300)
    assert is_speech(chunk, threshold=1000) is False
    assert is_speech(chunk, threshold=100) is True


# ── endpointer ──────────────────────────────────────────────────────────


def test_growing_partial_resets_silence():
    ep = Endpointer(max_silence_chunks=3)
    d = ep.update("open")
    assert d.changed and not d.finalize and d.text == "open"
    d = ep.update("open chrome")
    assert d.changed and not d.finalize
    assert ep.partial == "open chrome"


def test_endpoints_after_trailing_silence():
    ep = Endpointer(max_silence_chunks=3)
    ep.update("open chrome")
    # Same partial repeated = trailing silence; endpoints on the 3rd.
    assert ep.update("open chrome").finalize is False
    assert ep.update("open chrome").finalize is False
    d = ep.update("open chrome")
    assert d.finalize is True
    assert d.text == "open chrome"
    assert ep.final_text == "open chrome"


def test_hard_final_endpoints_immediately():
    ep = Endpointer()
    d = ep.update("weather batao", is_final=True)
    assert d.finalize is True and d.text == "weather batao"


def test_empty_hard_final_is_noop_preserves_partial():
    ep = Endpointer()
    ep.update("hello")
    d = ep.update("", is_final=True)
    assert d.finalize is False
    assert ep.partial == "hello"                       # running partial preserved


def test_no_endpoint_before_any_speech():
    ep = Endpointer(max_silence_chunks=2)
    # Silence-only updates (empty partials) never endpoint.
    for _ in range(10):
        assert ep.update("").finalize is False


def test_reset_clears_state():
    ep = Endpointer(max_silence_chunks=2)
    ep.update("hello")
    ep.reset()
    assert ep.partial == "" and ep.final_text == ""
    # After reset it needs fresh speech before it can endpoint again.
    assert ep.update("").finalize is False


def test_max_silence_chunks_configurable():
    fast = Endpointer(max_silence_chunks=1)
    fast.update("hi")
    assert fast.update("hi").finalize is True          # endpoints after 1 silent chunk
