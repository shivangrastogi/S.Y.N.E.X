"""Tests for voice-capture gating + processing-watchdog policy."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core import voice_gate as vg


# ── meaningful-capture filter ───────────────────────────────────────────


@pytest.mark.parametrize("text", [
    "open chrome",
    "weather batao",
    "um open notepad",          # filler + real word → passes
    "screenshot lo",
    "25 times 4",
])
def test_meaningful_passes_real_speech(text):
    assert vg.is_meaningful_capture(text) is True


@pytest.mark.parametrize("text", [
    "", "   ", None,
    "uh", "um", "hmm", "mm",
    "uh um", "hmm hm", "aa", "haan",
    "a",                         # single filler letter
])
def test_meaningful_rejects_noise(text):
    assert vg.is_meaningful_capture(text) is False


def test_min_chars_threshold():
    assert vg.is_meaningful_capture("x") is False
    assert vg.is_meaningful_capture("go") is True


# ── watchdog budget ─────────────────────────────────────────────────────


def test_timeout_base_default():
    t = vg.processing_timeout_s("open chrome")
    assert t == vg.DEFAULT_PROCESSING_TIMEOUT_S


def test_timeout_longer_for_long_text():
    short = vg.processing_timeout_s("hi")
    long = vg.processing_timeout_s("x" * 80)
    assert long > short


def test_timeout_capped_when_no_llm():
    t = vg.processing_timeout_s("x" * 80, llm_possible=False)
    assert t <= 6.0


def test_timeout_always_bounded():
    assert 3.0 <= vg.processing_timeout_s("x" * 5000) <= 30.0
    assert vg.processing_timeout_s("") >= 3.0
