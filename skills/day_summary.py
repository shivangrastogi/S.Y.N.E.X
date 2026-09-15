"""End-of-day wrap-up — one spoken summary of the whole day.

Roadmap v3 ("proactive AERIS") item 1: instead of the user interrogating
five different skills at night, one command (or the shipped
"Evening wrap-up" routine at 21:30) rolls the day up:

  * screen time by app          (workspace tracker, since midnight)
  * what AERIS did              (activity digest: commands, top skills)
  * money spent today           (Expenses sheet of the workbook)
  * battery + uptime            (psutil)

Every section is independently fault-isolated: a missing workbook or a
stopped tracker degrades to a one-line note, never an error reply.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import time

from core.skill_registry import skill

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKBOOK = os.path.join(_ROOT, "data", "jarvis_workbook.xlsx")


def _since_midnight_s() -> float:
    now = _dt.datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60.0, (now - midnight).total_seconds())


def _screen_time_lines() -> str:
    try:
        from core.workspace_tracker import get_tracker
        return get_tracker().summary(window_s=_since_midnight_s())
    except Exception as e:
        log.debug("[day_summary] workspace section failed: %s", e)
        return "Screen time: tracker data nahi mila."


def _aeris_activity_line() -> str:
    try:
        from core.activity_digest import digest
        d = digest(window_h=_since_midnight_s() / 3600.0)
        total = sum(d.get("by_intent", {}).values()) if isinstance(
            d.get("by_intent"), dict) else d.get("total", 0)
        top = ""
        by = d.get("by_intent") or {}
        if by:
            best = max(by.items(), key=lambda kv: kv[1])
            top = f" — sabse zyada '{best[0]}' ({best[1]}x)"
        if not total:
            return "AERIS commands: aaj koi nahi."
        return f"AERIS commands aaj: {total}{top}."
    except Exception as e:
        log.debug("[day_summary] activity section failed: %s", e)
        return "AERIS activity: data nahi mila."


def _expenses_line() -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(_WORKBOOK, read_only=True, data_only=True)
        if "Expenses" not in wb.sheetnames:
            return "Kharcha: sheet nahi mili."
        today = _dt.date.today()
        total = 0.0
        n = 0
        for row in wb["Expenses"].iter_rows(min_row=2, values_only=True):
            d, amount = row[0], row[1]
            if isinstance(d, _dt.datetime):
                d = d.date()
            if d == today and isinstance(amount, (int, float)):
                total += float(amount)
                n += 1
        if n == 0:
            return "Kharcha aaj: zero. Wallet khush hai."
        return f"Kharcha aaj: ₹{total:,.0f} ({n} entr{'y' if n == 1 else 'ies'})."
    except Exception as e:
        log.debug("[day_summary] expenses section failed: %s", e)
        return "Kharcha: workbook nahi khula."


def _system_line() -> str:
    try:
        import psutil
        parts = []
        batt = psutil.sensors_battery()
        if batt:
            parts.append(f"battery {batt.percent:.0f}%"
                         + (" (charging)" if batt.power_plugged else ""))
        up_h = (time.time() - psutil.boot_time()) / 3600.0
        parts.append(f"uptime {up_h:.1f}h")
        return "System: " + ", ".join(parts) + "."
    except Exception:
        return ""


@skill(
    name="day_summary",
    description="End-of-day wrap-up: screen time, AERIS activity, today's "
                "spend, battery/uptime — one spoken report.",
    patterns=[
        "day summary", "aaj ka summary", "aaj ka summary do",
        "end of day report", "end of day summary", "day wrap up",
        "wrap up my day", "din kaisa gaya", "aaj ka hisaab do",
        "daily wrap up", "aaj ka report do", "summarise my day",
    ],
    required_entities=[],
)
def day_summary(_slots: dict) -> str:
    now = _dt.datetime.now()
    lines = [f"Aaj ka wrap-up, {now.strftime('%A %d %b')}:"]
    lines.append(_screen_time_lines())
    lines.append(_aeris_activity_line())
    lines.append(_expenses_line())
    sysline = _system_line()
    if sysline:
        lines.append(sysline)
    return "\n".join(l for l in lines if l)
