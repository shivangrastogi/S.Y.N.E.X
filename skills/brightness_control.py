"""Screen brightness control.

Uses the ``screen_brightness_control`` package if installed (cross-
platform; uses WMI on Windows). Falls back to a WMI call via ``ctypes``
+ ``win32com.client`` when only ``pywin32`` is present.

Skills exposed:
  * ``brightness 50``      — set absolute
  * ``brighter``           — +10 %
  * ``dimmer``             — -10 %
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)


_SBC = None
try:
    import screen_brightness_control as _sbc  # type: ignore
    _SBC = _sbc
except Exception:
    _SBC = None


def _get_brightness() -> int | None:
    if _SBC is not None:
        try:
            vals = _SBC.get_brightness()
            return int(vals[0]) if isinstance(vals, list) and vals else int(vals)
        except Exception:
            pass
    return _wmi_get_brightness()


def _set_brightness(pct: int) -> bool:
    pct = max(0, min(100, int(pct)))
    if _SBC is not None:
        try:
            _SBC.set_brightness(pct)
            return True
        except Exception:
            pass
    return _wmi_set_brightness(pct)


def _wmi_get_brightness() -> int | None:
    try:
        import win32com.client  # type: ignore
        s = win32com.client.GetObject("winmgmts:\\\\.\\root\\WMI")
        for obj in s.InstancesOf("WmiMonitorBrightness"):
            return int(obj.CurrentBrightness)
    except Exception as e:
        log.debug("[brightness] WMI get failed: %s", e)
    return None


def _wmi_set_brightness(pct: int) -> bool:
    try:
        import win32com.client  # type: ignore
        s = win32com.client.GetObject("winmgmts:\\\\.\\root\\WMI")
        for obj in s.InstancesOf("WmiMonitorBrightnessMethods"):
            obj.WmiSetBrightness(pct, 0)
        return True
    except Exception as e:
        log.debug("[brightness] WMI set failed: %s", e)
        return False


def _parse_percent(text: str) -> int | None:
    m = re.search(r"(\d{1,3})\s*%?", text or "")
    if not m:
        return None
    return max(0, min(100, int(m.group(1))))


def _record_brightness_undo(prev) -> None:
    """Register an undo restoring the prior brightness % (no-op if unknown)."""
    if prev is None:
        return
    try:
        from core.action_history import record

        def _undo(prev=int(prev)):
            if _set_brightness(prev):
                return f"Brightness wapas {prev}% kar diya."
            return "Brightness undo nahi kar paya."

        record(f"brightness → {int(prev)}%", _undo, skill="brightness")
    except Exception:
        pass


@skill(
    name="brightness_set",
    description="Set screen brightness to an absolute percentage",
    patterns=[
        "brightness 50", "brightness set to 30", "brightness 60 percent",
        "screen brightness 75", "screen 25 percent", "display 80",
        "screen bright 90",
    ],
    # No hard gate: the level is a number in the phrase and _parse_percent scans
    # the whole string, so gating on a `content` slot the extractor doesn't fill
    # dead-ends at "kitni brightness?" even when "brightness 75" was given.
    required_entities=[],
    prompts={},
)
def brightness_set(slots: dict) -> str:
    pct = _parse_percent(slots.get("content") or slots.get("raw_text")
                         or slots.get("text") or "")
    if pct is None:
        return "Brightness percent batao — jaise 'brightness 60'."
    prev = _get_brightness()                  # capture for undo before changing
    if _set_brightness(pct):
        _record_brightness_undo(prev)         # "undo" restores the old level
        return f"Brightness {pct}% kar diya."
    return ("Brightness change nahi ho saka. "
            "'pip install screen-brightness-control' karo for full support.")


@skill(
    name="brightness_up",
    description="Increase screen brightness by ~10%",
    patterns=["brighter", "brightness up", "screen bright karo",
              "increase brightness", "thoda bright", "tej karo"],
)
def brightness_up(_slots: dict) -> str:
    cur = _get_brightness()
    if cur is None:
        return "Brightness read nahi hua. 'pip install screen-brightness-control' try karo."
    new = min(100, cur + 10)
    return brightness_set({"content": str(new)})


@skill(
    name="brightness_down",
    description="Decrease screen brightness by ~10%",
    patterns=["dimmer", "brightness down", "screen dim karo",
              "decrease brightness", "thoda dim", "kam brightness"],
)
def brightness_down(_slots: dict) -> str:
    cur = _get_brightness()
    if cur is None:
        return "Brightness read nahi hua. 'pip install screen-brightness-control' try karo."
    new = max(0, cur - 10)
    return brightness_set({"content": str(new)})
