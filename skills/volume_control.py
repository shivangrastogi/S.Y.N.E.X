"""System volume control.

Uses ``pycaw`` (Python wrapper for the Windows Core Audio API) if
installed — it can read and set the master volume scalar (0.0..1.0)
without spawning subprocesses. Falls back to simulating media-key
presses via ``ctypes.keybd_event`` so the skill still works on a fresh
install with no extras.

Supports four utterances:
  * ``volume 50`` / ``volume 50 percent`` — set absolute
  * ``volume up`` / ``louder``            — bump by 10 %
  * ``volume down`` / ``softer``          — drop by 10 %
  * ``mute`` / ``unmute``                 — toggle
"""
from __future__ import annotations

import ctypes
import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)


# ── Backend detection ──────────────────────────────────────────────── #

_PYCAW = None
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL  # type: ignore
    _PYCAW = "available"
except Exception:
    _PYCAW = None


def _endpoint():
    """Return an IAudioEndpointVolume interface, or None if pycaw absent."""
    if _PYCAW is None:
        return None
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception as e:
        log.warning("[volume] pycaw endpoint failed: %s", e)
        return None


# ── Fallback: media-key simulation ─────────────────────────────────── #

_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF


def _press_key(vk: int, times: int = 1) -> None:
    user32 = ctypes.WinDLL("user32")
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)   # KEYEVENTF_KEYUP


# ── Public surface ─────────────────────────────────────────────────── #

def _parse_percent(text: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*%?", text or "")
    if not m:
        return None
    val = int(m.group(1))
    return max(0, min(100, val))


# ── Mockable volume seam ───────────────────────────────────────────── #
#
# Reading/writing the master volume goes through these two functions so the
# skill is testable headlessly (monkeypatch get_volume/set_volume with a fake
# in-memory level) and so the undo path has one place to capture/restore from.


def get_volume():
    """Current master volume as a 0.0–1.0 scalar, or None if unavailable."""
    ep = _endpoint()
    if ep is None:
        return None
    try:
        return float(ep.GetMasterVolumeLevelScalar())
    except Exception as e:
        log.warning("[volume] GetMasterVolumeLevelScalar failed: %s", e)
        return None


def set_volume(scalar: float) -> bool:
    """Set master volume from a 0.0–1.0 scalar. True on success."""
    ep = _endpoint()
    if ep is None:
        return False
    try:
        ep.SetMasterVolumeLevelScalar(max(0.0, min(1.0, scalar)), None)
        return True
    except Exception as e:
        log.warning("[volume] SetMasterVolumeLevelScalar failed: %s", e)
        return False


def _record_volume_undo(prev_scalar) -> None:
    """Register an undo that restores ``prev_scalar`` (no-op if unknown)."""
    if prev_scalar is None:
        return
    try:
        from core.action_history import record

        def _undo(prev=prev_scalar):
            if set_volume(prev):
                return f"Volume wapas {int(round(prev * 100))}% kar diya."
            return "Volume undo nahi kar paya."

        record(f"volume → {int(round(prev_scalar * 100))}%", _undo, skill="volume")
    except Exception:
        pass


@skill(
    name="volume_set",
    description="Set system volume to an absolute percentage",
    patterns=[
        "volume 50", "volume 50 percent", "volume set to 30",
        "volume 60 kar do", "awaaz 40", "set volume to 75",
        "audio 80 percent", "loud 90", "loudness 25",
    ],
    # No hard gate: the level is a number in the phrase and _parse_percent scans
    # the whole string, so gating on a `content` slot the extractor doesn't fill
    # dead-ends at "kitna volume?" even when "volume 60" was given.
    required_entities=[],
    prompts={},
)
def volume_set(slots: dict) -> str:
    pct = _parse_percent(slots.get("content") or slots.get("raw_text")
                         or slots.get("text") or "")
    if pct is None:
        return "Volume percent batao — jaise 'volume 60'."
    prev = get_volume()                       # capture for undo before changing
    if set_volume(pct / 100.0):
        _record_volume_undo(prev)             # "undo" restores the old level
        return f"Volume {pct}% kar diya."
    # Fallback: nudge volume via media keys.
    # We can't query current absolute volume without pycaw, so we just
    # press VK_VOLUME_DOWN 50 times then VK_VOLUME_UP pct/2 times.
    _press_key(_VK_VOLUME_DOWN, 50)
    _press_key(_VK_VOLUME_UP, max(1, pct // 2))
    return f"Volume approximately {pct}% set kiya (fallback mode)."


@skill(
    name="volume_up",
    description="Increase system volume by ~10%",
    patterns=["volume up", "volume badhao", "louder", "awaaz badhao",
              "audio up", "thoda zor se", "bump volume"],
)
def volume_up(_slots: dict) -> str:
    cur = get_volume()
    if cur is not None:
        new = min(1.0, cur + 0.10)
        if set_volume(new):
            _record_volume_undo(cur)
            return f"Volume {int(new * 100)}% kar diya."
    _press_key(_VK_VOLUME_UP, 4)
    return "Volume badha diya."


@skill(
    name="volume_down",
    description="Decrease system volume by ~10%",
    patterns=["volume down", "volume kam karo", "softer", "awaaz kam",
              "audio down", "dheere", "lower volume"],
)
def volume_down(_slots: dict) -> str:
    cur = get_volume()
    if cur is not None:
        new = max(0.0, cur - 0.10)
        if set_volume(new):
            _record_volume_undo(cur)
            return f"Volume {int(new * 100)}% kar diya."
    _press_key(_VK_VOLUME_DOWN, 4)
    return "Volume kam kar diya."


@skill(
    name="volume_mute",
    description="Mute or unmute system audio",
    patterns=["mute", "mute karo", "unmute", "awaaz band karo",
              "audio off", "audio on", "silence", "mute toggle"],
)
def volume_mute(_slots: dict) -> str:
    ep = _endpoint()
    if ep is not None:
        try:
            muted = bool(ep.GetMute())
            ep.SetMute(not muted, None)
            return "Unmute kar diya." if muted else "Mute kar diya."
        except Exception:
            pass
    _press_key(_VK_VOLUME_MUTE, 1)
    return "Mute toggle kar diya."
