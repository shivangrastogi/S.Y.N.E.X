"""Voice tuning skills — adjust TTS rate / volume on the fly.

Writes to ``data/settings.json`` via the settings store so the change
survives restarts. The TTS engine consults these keys on each utterance,
so the effect is immediate for the *next* spoken reply.

Tunable keys:
  * ``speech_rate``    (int, words-per-minute)  — pyttsx3 honors this.
  * ``voice_volume``   (float 0.0 .. 1.0)       — pyttsx3 honors this.
"""
from __future__ import annotations

import logging

from core import settings as _settings
from core.skill_registry import skill

log = logging.getLogger(__name__)

_MIN_RATE, _MAX_RATE = 80, 350
_RATE_STEP = 25
_MIN_VOL, _MAX_VOL = 0.10, 1.00
_VOL_STEP = 0.10


def _current_rate() -> int:
    v = _settings.get("speech_rate") or 175
    try:
        return int(v)
    except Exception:
        return 175


def _current_volume() -> float:
    v = _settings.get("voice_volume")
    if v is None:
        return 1.0
    try:
        return max(_MIN_VOL, min(_MAX_VOL, float(v)))
    except Exception:
        return 1.0


def _set_rate(new: int) -> int:
    new = max(_MIN_RATE, min(_MAX_RATE, int(new)))
    _settings.set_("speech_rate", new)
    return new


def _set_vol(new: float) -> float:
    new = max(_MIN_VOL, min(_MAX_VOL, float(new)))
    _settings.set_("voice_volume", round(new, 2))
    return _current_volume()


# ── speech rate ────────────────────────────────────────────────────


@skill(
    name="voice_slower",
    description="Slow down the TTS voice by one step (~25 wpm).",
    patterns=[
        "speak slower", "speak more slowly", "slow down voice",
        "voice slow karo", "dheere bolo", "thoda dheere bolo",
        "speak slowly", "talk slower", "slow voice",
        "kam speed se bolo", "less speed",
    ],
    required_entities=[],
)
def voice_slower(_slots: dict) -> str:
    cur = _current_rate()
    nxt = _set_rate(cur - _RATE_STEP)
    if nxt == cur:
        return f"Voice already minimum speed ({nxt} wpm) par hai."
    return f"Voice slower kar di — {cur} → {nxt} wpm."


@skill(
    name="voice_faster",
    description="Speed up the TTS voice by one step (~25 wpm).",
    patterns=[
        "speak faster", "speed up voice", "voice fast karo",
        "tez bolo", "jaldi bolo", "talk faster",
        "voice speed badhao", "increase speech rate",
        "fast bolo", "speed up",
    ],
    required_entities=[],
)
def voice_faster(_slots: dict) -> str:
    cur = _current_rate()
    nxt = _set_rate(cur + _RATE_STEP)
    if nxt == cur:
        return f"Voice already maximum speed ({nxt} wpm) par hai."
    return f"Voice faster kar di — {cur} → {nxt} wpm."


# ── volume ─────────────────────────────────────────────────────────


@skill(
    name="voice_louder",
    description="Increase TTS voice volume by one step.",
    patterns=[
        "speak louder", "louder voice", "voice loud karo",
        "voice volume badhao", "zor se bolo", "increase voice volume",
        "tts loud karo", "voice high karo",
    ],
    required_entities=[],
)
def voice_louder(_slots: dict) -> str:
    cur = _current_volume()
    nxt = _set_vol(cur + _VOL_STEP)
    if abs(nxt - cur) < 0.001:
        return f"Voice already maximum ({int(nxt*100)}%) volume par hai."
    return f"Voice volume {int(cur*100)}% → {int(nxt*100)}%."


@skill(
    name="voice_softer",
    description="Decrease TTS voice volume by one step.",
    patterns=[
        "speak softer", "softer voice", "voice low karo",
        "voice volume kam karo", "dheemi awaz", "speak quieter",
        "tts low karo", "voice kam karo", "lower voice volume",
        "quiet voice",
    ],
    required_entities=[],
)
def voice_softer(_slots: dict) -> str:
    cur = _current_volume()
    nxt = _set_vol(cur - _VOL_STEP)
    if abs(nxt - cur) < 0.001:
        return f"Voice already minimum ({int(nxt*100)}%) volume par hai."
    return f"Voice volume {int(cur*100)}% → {int(nxt*100)}%."


# ── status / reset ─────────────────────────────────────────────────


@skill(
    name="voice_status",
    description="Report current TTS voice rate + volume.",
    patterns=[
        "voice status", "current voice settings", "voice settings",
        "voice ka rate kya hai", "voice ka volume kya hai",
        "tts settings",
    ],
    required_entities=[],
)
def voice_status(_slots: dict) -> str:
    return (f"Voice rate: {_current_rate()} wpm · "
            f"volume: {int(_current_volume()*100)}%.")


@skill(
    name="voice_reset",
    description="Restore TTS voice rate and volume to defaults (175 wpm, 100%).",
    patterns=[
        "reset voice", "voice reset karo", "voice defaults",
        "restore voice settings", "default voice",
        "voice normal karo",
    ],
    required_entities=[],
)
def voice_reset(_slots: dict) -> str:
    _settings.set_("speech_rate", 175)
    _settings.set_("voice_volume", 1.0)
    return "Voice settings default pe reset — 175 wpm, 100% volume."
