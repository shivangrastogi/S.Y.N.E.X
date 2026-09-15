"""Per-application audio control via pycaw audio sessions.

Skills:
  * ``app_mute``      — "mute chrome" / "spotify mute karo"
  * ``app_unmute``    — "unmute chrome"
  * ``app_volume_set``— "set spotify to 30%" / "spotify volume 50"
  * ``app_volume_list`` — list every app currently playing audio + its level

Graceful degrade: when pycaw is missing, every handler returns a single
install hint instead of crashing.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


try:
    from pycaw.pycaw import AudioUtilities  # type: ignore
    _PYCAW_OK = True
except Exception:
    AudioUtilities = None  # type: ignore
    _PYCAW_OK = False


def _strip_audio_verb(text: str, *triggers: str) -> str:
    """Strip a leading verb (mute, unmute, set X to N%) so what remains is
    the target app token."""
    if not text:
        return ""
    s = text.strip()
    for trig in sorted(triggers, key=len, reverse=True):
        if s.lower().startswith(trig):
            s = s[len(trig):].lstrip()
            break
    # Drop trailing Hinglish suffix forms like "mute karo" / "unmute karo".
    s = re.sub(r"\s+(?:mute|unmute|volume\s+set)\s+karo$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+(?:mute|unmute)$", "", s, flags=re.IGNORECASE)
    return s.strip(" \"'.,?")


def _parse_pct(text: str) -> Optional[int]:
    """Pull "30%", "to 75", "at 100", or "volume 50" out of text."""
    if not text:
        return None
    m = re.search(r"(\d{1,3})\s*%", text)
    if m:
        return max(0, min(100, int(m.group(1))))
    m2 = re.search(r"\b(?:to|=|at|volume)\s+(\d{1,3})\b", text, re.IGNORECASE)
    if m2:
        return max(0, min(100, int(m2.group(1))))
    # Bare integer in the 0..100 range — last-ditch.
    m3 = re.search(r"\b(\d{1,3})\b", text)
    if m3:
        v = int(m3.group(1))
        if 0 <= v <= 100:
            return v
    return None


def _iter_sessions():
    """Yield (session, name_lower, volume_iface). Empty when pycaw missing."""
    if not _PYCAW_OK:
        return
    try:
        sessions = AudioUtilities.GetAllSessions()
    except Exception as e:
        log.warning("[app_audio] GetAllSessions failed: %s", e)
        return
    for s in sessions:
        try:
            p = s.Process
            name = (p.name() if p else "").lower()
        except Exception:
            name = ""
        try:
            vol = s.SimpleAudioVolume
        except Exception:
            vol = None
        if vol is None:
            continue
        yield s, name, vol


def _match_app(query: str) -> list[tuple[str, object]]:
    """Return (name, volume) for every session matching the query token."""
    q = query.lower().strip()
    if not q:
        return []
    hits = []
    for _, name, vol in _iter_sessions():
        if q in name:
            hits.append((name, vol))
    return hits


# ── app_mute ───────────────────────────────────────────────────────


@skill(
    name="app_mute",
    description="Mute a specific application's audio (e.g. 'mute chrome').",
    patterns=[
        "mute chrome", "mute spotify", "mute discord",
        "mute app", "mute application",
        "chrome mute karo", "spotify mute karo", "discord mute karo",
        "mute the app", "silence chrome",
    ],
    required_entities=[],
)
def app_mute(slots: dict) -> str:
    if not _PYCAW_OK:
        return "pycaw nahi mila — pip install pycaw comtypes."
    text = slots.get("raw_text") or slots.get("text") or ""
    target = _strip_audio_verb(text, "mute", "silence")
    if not target:
        return "Kaunsa app mute karna hai? e.g. 'mute spotify'."
    hits = _match_app(target)
    if not hits:
        return f"'{target}' jaisa koi running audio session nahi mila."
    for name, vol in hits:
        try:
            vol.SetMute(1, None)
        except Exception as e:
            log.debug("[app_mute] %s SetMute failed: %s", name, e)
    return f"Muted: {', '.join(n for n, _ in hits)}"


# ── app_unmute ─────────────────────────────────────────────────────


@skill(
    name="app_unmute",
    description="Unmute a specific application's audio.",
    patterns=[
        "unmute chrome", "unmute spotify", "unmute discord",
        "unmute app", "unmute the app",
        "chrome unmute karo", "spotify unmute karo",
        "audio wapas karo", "voice wapas",
    ],
    required_entities=[],
)
def app_unmute(slots: dict) -> str:
    if not _PYCAW_OK:
        return "pycaw nahi mila — pip install pycaw comtypes."
    text = slots.get("raw_text") or slots.get("text") or ""
    target = _strip_audio_verb(text, "unmute")
    if not target:
        return "Kaunsa app unmute karna hai? e.g. 'unmute spotify'."
    hits = _match_app(target)
    if not hits:
        return f"'{target}' jaisa koi running audio session nahi mila."
    for name, vol in hits:
        try:
            vol.SetMute(0, None)
        except Exception as e:
            log.debug("[app_unmute] %s SetMute failed: %s", name, e)
    return f"Unmuted: {', '.join(n for n, _ in hits)}"


# ── app_volume_set ─────────────────────────────────────────────────


@skill(
    name="app_volume_set",
    description="Set the per-app volume percentage (e.g. 'set spotify to 30%').",
    patterns=[
        "set spotify to", "set chrome to", "set discord to",
        "set spotify volume", "spotify volume",
        "set app volume", "chrome volume 50",
        "spotify ka volume", "chrome ka volume",
        "spotify volume set karo", "chrome volume set karo",
    ],
    required_entities=[],
)
def app_volume_set(slots: dict) -> str:
    if not _PYCAW_OK:
        return "pycaw nahi mila — pip install pycaw comtypes."
    text = slots.get("raw_text") or slots.get("text") or ""
    pct = _parse_pct(text)
    if pct is None:
        return "Volume % nahi mila. Try 'set spotify to 30%'."
    # Strip both the verb and the percentage from the text to recover the app name.
    cleaned = re.sub(r"\d+\s*%?", "", text)
    cleaned = re.sub(r"\b(set|to|at|volume|ka|set\s+karo)\b", "", cleaned, flags=re.IGNORECASE)
    target = cleaned.strip(" .,?\"'")
    if not target:
        return "Kis app ka volume? Try 'set spotify to 30%'."
    hits = _match_app(target)
    if not hits:
        return f"'{target}' jaisa koi running audio session nahi mila."
    level = pct / 100.0
    for name, vol in hits:
        try:
            vol.SetMasterVolume(level, None)
        except Exception as e:
            log.debug("[app_volume_set] %s SetMasterVolume failed: %s", name, e)
    return f"{', '.join(n for n, _ in hits)} → {pct}%"


# ── app_volume_list ────────────────────────────────────────────────


@skill(
    name="app_volume_list",
    description="List every app currently producing audio with its volume %.",
    patterns=[
        "list app volumes", "app volumes", "show app audio",
        "kaunse apps audio bana rahe hain", "running audio apps",
        "audio sessions", "what's playing",
        "what apps are playing audio", "which apps play sound",
    ],
    required_entities=[],
)
def app_volume_list(_slots: dict) -> str:
    if not _PYCAW_OK:
        return "pycaw nahi mila — pip install pycaw comtypes."
    rows = []
    for _, name, vol in _iter_sessions():
        if not name:
            continue
        try:
            lvl = int(round(vol.GetMasterVolume() * 100))
            mute = " (muted)" if vol.GetMute() else ""
        except Exception:
            lvl, mute = "?", ""
        rows.append(f"  • {name:25s} {lvl}%{mute}")
    if not rows:
        return "Koi audio session active nahi hai."
    return "Active audio sessions:\n" + "\n".join(rows)
