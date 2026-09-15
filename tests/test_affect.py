"""Tests for core.affect — the Affective Core (Sentient-Partner Phase 1).

Pure logic: we inject `now`/`hour` and a temp state path so nothing depends on the
wall clock or touches the real data/affect_state.json.
"""
from __future__ import annotations

import core.affect as A
from core.affect import AffectiveCore, AffectiveState


def _core(tmp_path, enabled=True, state=None):
    return AffectiveCore(state=state or AffectiveState(), enabled=enabled,
                         persist_path=str(tmp_path / "affect.json"))


# ── mood mapping ─────────────────────────────────────────────────────────
def test_mood_quadrants():
    assert AffectiveState(valence=-0.6, arousal=0.7).mood() == "frustrated"
    assert AffectiveState(valence=-0.6, arousal=0.3).mood() == "low"
    assert AffectiveState(valence=0.6, arousal=0.7).mood() == "excited"
    assert AffectiveState(valence=0.6, arousal=0.3).mood() == "content"
    assert AffectiveState(valence=0.0, arousal=0.05).mood() == "tired"
    assert AffectiveState(valence=0.0, arousal=0.4).mood() == "neutral"


# ── observe: valence tracks sentiment, failure/success nudge ─────────────
def test_negative_stream_lowers_valence(tmp_path):
    c = _core(tmp_path)
    t = 1000.0
    for _ in range(3):
        c.observe(-0.8, now=t)
        t += 1
    assert c.state.valence < -0.35
    assert c.state.consecutive_low == 3
    assert c.mood() in ("low", "frustrated")


def test_positive_stream_raises_valence(tmp_path):
    c = _core(tmp_path)
    t = 1000.0
    for _ in range(3):
        c.observe(0.8, now=t)
        t += 1
    assert c.state.valence > 0.35
    assert c.state.consecutive_low == 0
    assert c.mood() in ("content", "excited")


def test_failure_and_success_nudge(tmp_path):
    c = _core(tmp_path)
    c.observe(0.0, failure=True, now=1000.0)
    assert c.state.valence < 0 and c.state.consecutive_fail == 1
    c2 = _core(tmp_path)
    c2.observe(0.0, success=True, now=1000.0)
    assert c2.state.valence > 0


# ── tone ──────────────────────────────────────────────────────────────────
def test_tone_maps_mood(tmp_path):
    c = _core(tmp_path, state=AffectiveState(valence=-0.6, arousal=0.3))
    assert c.tone() == "gentle"
    c = _core(tmp_path, state=AffectiveState(valence=0.6, arousal=0.7))
    assert c.tone() == "upbeat"
    c = _core(tmp_path, state=AffectiveState(valence=0.0, arousal=0.4))
    assert c.tone() == "neutral"


# ── proactive care: warranted, rate-limited, quiet-hours-suppressed ──────
def test_care_moment_fires_then_rate_limits(tmp_path):
    c = _core(tmp_path)
    t = 1000.0
    for _ in range(3):
        c.observe(-0.8, now=t)
        t += 1
    line = c.care_moment(now=t, hour=14)          # daytime, warranted
    assert line and isinstance(line, str)
    # immediate second call is rate-limited
    assert c.care_moment(now=t + 5, hour=14) is None


def test_care_suppressed_in_quiet_hours(tmp_path):
    c = _core(tmp_path)
    t = 1000.0
    for _ in range(3):
        c.observe(-0.8, now=t)
        t += 1
    assert c.care_moment(now=t, hour=2) is None    # 2 AM → quiet


def test_care_none_when_calm(tmp_path):
    c = _core(tmp_path)
    c.observe(0.5, now=1000.0)
    assert c.care_moment(now=1001.0, hour=14) is None


# ── decay toward neutral ─────────────────────────────────────────────────
def test_decay_relaxes_valence(tmp_path):
    c = _core(tmp_path, state=AffectiveState(valence=-0.8, arousal=0.9, updated_at=0.0))
    c._decay(now=2 * 3600.0)          # 2 hours later
    assert abs(c.state.valence) < 0.8
    assert c.state.arousal < 0.9


# ── kill switch ──────────────────────────────────────────────────────────
def test_disabled_is_inert(tmp_path):
    c = _core(tmp_path, enabled=False, state=AffectiveState(valence=-0.9, arousal=0.9))
    c.observe(-0.9, failure=True, now=1000.0)     # no-op
    assert c.state.valence == -0.9                # unchanged
    assert c.mood() == "neutral"
    assert c.tone() == "neutral"
    assert c.care_moment(now=1000.0, hour=14) is None
    assert c.modulate("hello") == "hello"


# ── env kill switch + persistence round-trip ─────────────────────────────
def test_env_kill_switch(monkeypatch, tmp_path):
    monkeypatch.setenv("AERIS_AFFECT_OFF", "1")
    c = AffectiveCore(persist_path=str(tmp_path / "a.json"))
    assert c.enabled is False


def test_persist_round_trip(tmp_path):
    p = str(tmp_path / "a.json")
    c = AffectiveCore(state=AffectiveState(valence=-0.5, arousal=0.6), persist_path=p)
    c.persist()
    c2 = AffectiveCore(persist_path=p)
    assert round(c2.state.valence, 2) == -0.5 and round(c2.state.arousal, 2) == 0.6
