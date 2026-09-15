"""Tests for the TTS phrase cache (core/tts_cache.py).

Pure filesystem + hashing — no pygame, no edge_tts, no audio device, so this
runs in the normal headless suite (unlike test_tts.py which conftest skips).
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core import tts_cache as tc


# ── key + normalisation ────────────────────────────────────────────────


def test_key_stable_and_input_sensitive():
    k1 = tc.cache_key("Done.", "en-IN-NeerjaNeural")
    k2 = tc.cache_key("Done.", "en-IN-NeerjaNeural")
    assert k1 == k2
    assert tc.cache_key("Done.", "en-US-AriaNeural") != k1     # voice matters
    assert tc.cache_key("Done.", "en-IN-NeerjaNeural", rate="+10%") != k1


def test_key_normalises_whitespace_and_case():
    assert tc.cache_key("Yes  sir.", "v") == tc.cache_key("yes sir.", "v")
    assert tc.cache_key("  Done. ", "v") == tc.cache_key("done.", "v")


# ── cacheability gate ───────────────────────────────────────────────────


def test_is_cacheable_gate():
    assert tc.is_cacheable("Done.")
    assert not tc.is_cacheable("")
    assert not tc.is_cacheable("   ")
    assert not tc.is_cacheable("x" * (tc.MAX_LEN + 1))
    assert tc.is_cacheable("x" * tc.MAX_LEN)


# ── store + lookup roundtrip ────────────────────────────────────────────


def _make_src(tmp_path, data=b"ID3fake-mp3-bytes"):
    src = tmp_path / "speech.mp3"
    src.write_bytes(data)
    return str(src)


def test_store_then_lookup_hits(tmp_path):
    audio_dir = str(tmp_path)
    src = _make_src(tmp_path)
    dst = tc.store(audio_dir, src, "Done.", "v")
    assert os.path.exists(dst)
    assert dst.endswith(".mp3") and dst != src

    hit = tc.lookup(audio_dir, "Done.", "v")
    assert hit == dst

    # Normalised variants hit the same clip.
    assert tc.lookup(audio_dir, "  done. ", "v") == dst


def test_lookup_miss_cases(tmp_path):
    audio_dir = str(tmp_path)
    assert tc.lookup(audio_dir, "never-stored", "v") is None
    # Non-cacheable phrase never reports a hit even if a file somehow exists.
    assert tc.lookup(audio_dir, "x" * 500, "v") is None
    # Empty (zero-byte) cached file is treated as a miss.
    p = tc.cache_path(audio_dir, "empty", "v")
    open(p, "wb").close()
    assert tc.lookup(audio_dir, "empty", "v") is None


def test_store_returns_src_on_bad_source(tmp_path):
    audio_dir = str(tmp_path)
    missing = str(tmp_path / "nope.mp3")
    # Source doesn't exist → best-effort returns the src path, no crash.
    out = tc.store(audio_dir, missing, "Done.", "v")
    assert out == missing


# ── prune (LRU) ─────────────────────────────────────────────────────────


def test_prune_keeps_newest_and_spares_non_cache_files(tmp_path):
    audio_dir = str(tmp_path)
    # A live temp file that must never be pruned.
    speech = tmp_path / "speech.mp3"
    speech.write_bytes(b"live")

    src = _make_src(tmp_path)
    paths = []
    for i in range(5):
        p = tc.store(audio_dir, src, f"phrase number {i}", "v")
        # Stagger mtimes so LRU ordering is deterministic.
        os.utime(p, (time.time() + i, time.time() + i))
        paths.append(p)

    removed = tc.prune(audio_dir, max_files=2)
    assert removed == 3
    # The two newest survive; speech.mp3 is untouched.
    assert os.path.exists(paths[-1]) and os.path.exists(paths[-2])
    assert not os.path.exists(paths[0])
    assert speech.exists()


def test_prune_noop_under_cap(tmp_path):
    audio_dir = str(tmp_path)
    src = _make_src(tmp_path)
    tc.store(audio_dir, src, "only one", "v")
    assert tc.prune(audio_dir, max_files=250) == 0
