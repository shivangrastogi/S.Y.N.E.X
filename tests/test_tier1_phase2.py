"""Tier 1 phase 2 — voice fingerprint, settings panel, calibration wizard.

Side-effect-safe:
  * voice_id tests synthesize PCM (no mic) and use a temp registry path.
  * UI tests use module-level imports only — actual dialogs are NOT shown
    (would block in headless CI). The launch helpers run in a daemon
    thread which we never join.
"""
from __future__ import annotations

import os
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "speaker_enroll", "speaker_identify", "speaker_list", "speaker_forget",
    "open_settings_panel", "start_calibration_wizard",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ─────────────────────────────────────────────────────

ROUTING_CASES = [
    ("enroll my voice",            "speaker_enroll"),
    ("speaker enroll",             "speaker_enroll"),
    ("identify speaker",           "speaker_identify"),
    ("speaker list",               "speaker_list"),
    ("list speakers",              "speaker_list"),
    ("forget speaker",             "speaker_forget"),
    ("open settings panel",        "open_settings_panel"),
    ("settings panel kholo",       "open_settings_panel"),
    ("preferences panel",          "open_settings_panel"),
    ("start calibration",          "start_calibration_wizard"),
    ("gesture tutorial",           "start_calibration_wizard"),
    ("teach me gestures",          "start_calibration_wizard"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier1_phase2(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── voice_id engine ────────────────────────────────────────────


def _make_pcm(freq_hz: float, duration_s: float = 1.0, rate: int = 16000) -> bytes:
    """Synthesize a sine wave PCM stream — distinct frequencies will
    produce distinct spectral signatures."""
    import math
    n = int(duration_s * rate)
    samples = [int(10000 * math.sin(2 * math.pi * freq_hz * i / rate)) for i in range(n)]
    return struct.pack("<" + "h" * n, *samples)


def test_voice_id_signature_shape():
    from core.voice_id import _pcm_to_signature, _FFT_N
    pcm = _make_pcm(440.0)
    sig = _pcm_to_signature(pcm)
    assert sig is not None
    assert len(sig) == _FFT_N // 2 + 1


def test_voice_id_signature_invariant_to_amplitude():
    """A 2× louder signal should produce a near-identical signature
    (L2-normalised spectral envelope)."""
    import math
    from core.voice_id import _pcm_to_signature
    import numpy as np
    n = 16000
    soft = [int(2000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(n)]
    loud = [s * 4 for s in soft]
    sig_a = _pcm_to_signature(struct.pack("<" + "h" * n, *soft))
    sig_b = _pcm_to_signature(struct.pack("<" + "h" * n, *loud))
    a = np.asarray(sig_a); b = np.asarray(sig_b)
    cos = float(a @ b)
    assert cos > 0.99, f"loud/soft cosine = {cos}"


def test_voice_id_distinguishes_frequencies(monkeypatch, tmp_path):
    """Enroll two distinctly-pitched signals; identify_pcm should match."""
    import core.voice_id as vi
    monkeypatch.setattr(vi, "_REG_PATH", tmp_path / "voice_registry.json")
    vi._DEFAULT = None
    eng = vi.get_voice_id_engine()
    # Enroll directly via the internal API (bypass mic).
    sig_alice = vi._pcm_to_signature(_make_pcm(200.0))
    sig_bob   = vi._pcm_to_signature(_make_pcm(800.0))
    eng._data["alice"] = [sig_alice]
    eng._data["bob"]   = [sig_bob]
    # Identify a fresh 200 Hz clip → alice.
    name, sim = eng.identify_pcm(_make_pcm(200.0))
    assert name == "alice", f"got {name!r} (sim {sim:.2f})"
    # 800 Hz → bob.
    name, sim = eng.identify_pcm(_make_pcm(800.0))
    assert name == "bob"


def test_voice_id_list_and_forget(monkeypatch, tmp_path):
    import core.voice_id as vi
    monkeypatch.setattr(vi, "_REG_PATH", tmp_path / "voice_registry.json")
    vi._DEFAULT = None
    eng = vi.get_voice_id_engine()
    eng._data["alice"] = [[0.0] * 257]
    assert "alice" in eng.list_speakers()
    assert eng.forget("alice") is True
    assert eng.list_speakers() == []
    assert eng.forget("alice") is False


def test_voice_id_engine_handles_short_pcm():
    """Sub-FFT-window PCM should produce None, not raise."""
    from core.voice_id import _pcm_to_signature, _FFT_N
    short = b"\x00\x00" * (_FFT_N // 4)
    assert _pcm_to_signature(short) is None


# ── speaker skill handlers (no mic) ────────────────────────────


def test_speaker_enroll_no_name():
    from skills.voice_id_skill import speaker_enroll
    out = speaker_enroll({"raw_text": "enroll my voice"})
    assert "naam" in out.lower() or "name" in out.lower()


def test_speaker_identify_when_empty(monkeypatch, tmp_path):
    import core.voice_id as vi
    monkeypatch.setattr(vi, "_REG_PATH", tmp_path / "voice_registry.json")
    vi._DEFAULT = None
    from skills.voice_id_skill import speaker_identify
    out = speaker_identify({})
    # Either "Koi speaker enrolled nahi" or backend-unavailable message.
    assert "speaker" in out.lower() or "enroll" in out.lower()


# ── settings panel (UI imports without running) ────────────────


def test_settings_panel_module_imports():
    """The module must import cleanly even on a headless host."""
    import ui.settings_panel as sp
    assert callable(sp.open_settings_panel)


def test_settings_panel_skill_returns_immediately():
    """The skill launches in a daemon thread, so the call returns fast."""
    from skills.settings_panel_skill import open_settings_panel
    t0 = time.monotonic()
    out = open_settings_panel({})
    assert time.monotonic() - t0 < 0.5
    assert "settings" in out.lower()


# ── calibration wizard ────────────────────────────────────────


def test_calibration_module_imports():
    import ui.calibration_wizard as cw
    assert callable(cw.open_calibration_wizard)
    # The step list should be non-empty.
    assert len(cw._CALIBRATION_STEPS) >= 6


def test_calibration_skill_returns_immediately():
    from skills.calibration_skill import start_calibration_wizard
    t0 = time.monotonic()
    out = start_calibration_wizard({})
    assert time.monotonic() - t0 < 0.5
    assert "calibration" in out.lower() or "wizard" in out.lower()
