"""Outlook calendar skills via win32com (MAPI namespace).

Reads the default Outlook calendar (folder 9 = olFolderCalendar) and
surfaces today's meetings + the next upcoming one. Requires:
  * Outlook desktop client installed and configured
  * ``pywin32`` (which brings ``win32com.client``)

Skills:
  * ``next_meeting``       — soonest upcoming appointment
  * ``todays_meetings``    — every appointment with today's date
  * ``this_week_meetings`` — every appointment in the next 7 days
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, date as _date
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


_OL_FOLDER_CALENDAR = 9


def _outlook_calendar():
    """Return the Outlook calendar folder, or None on any failure.
    Lazy-imports win32com so the module loads on machines without it."""
    try:
        import win32com.client  # type: ignore
    except Exception as e:
        log.info("[outlook_calendar] win32com unavailable: %s", e)
        return None
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        return ns.GetDefaultFolder(_OL_FOLDER_CALENDAR)
    except Exception as e:
        log.info("[outlook_calendar] dispatch failed: %s", e)
        return None


def _query_appointments(start: datetime, end: datetime):
    """Yield Outlook appointment items whose Start is within [start, end)."""
    cal = _outlook_calendar()
    if cal is None:
        return
    try:
        items = cal.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        # Restrict with Outlook's filter language — much faster than
        # iterating the whole calendar.
        fmt = "%m/%d/%Y %I:%M %p"
        restrict = (f"[Start] >= '{start.strftime(fmt)}' "
                    f"AND [Start] < '{end.strftime(fmt)}'")
        for appt in items.Restrict(restrict):
            yield appt
    except Exception as e:
        log.info("[outlook_calendar] query failed: %s", e)


def _fmt_appointment(appt) -> str:
    try:
        subject = (getattr(appt, "Subject", "") or "(no subject)").strip()
        start = getattr(appt, "Start", None)
        loc = (getattr(appt, "Location", "") or "").strip()
    except Exception:
        return "(unreadable appointment)"
    start_str = start.strftime("%a %d %b · %H:%M") if start else "?"
    return f"{start_str}  {subject}" + (f"  @ {loc}" if loc else "")


# ── next_meeting ───────────────────────────────────────────────────


@skill(
    name="next_meeting",
    description="Show the next upcoming Outlook appointment.",
    patterns=[
        "next meeting", "what's my next meeting",
        "agla meeting kya hai", "next appointment",
        "what's next on my calendar", "upcoming meeting",
        "next event", "agla event",
    ],
    required_entities=[],
)
def next_meeting(_slots: dict) -> str:
    cal = _outlook_calendar()
    if cal is None:
        return ("Outlook calendar reach nahi ho paya. "
                "Outlook desktop chal raha hai kya? (pywin32 also needed)")
    now = datetime.now()
    horizon = now + timedelta(days=14)
    for appt in _query_appointments(now, horizon):
        return f"Next: {_fmt_appointment(appt)}"
    return "Next 14 din mein koi meeting nahi hai."


# ── todays_meetings ────────────────────────────────────────────────


@skill(
    name="todays_meetings",
    description="List every appointment on today's calendar.",
    patterns=[
        "todays meetings", "today's meetings", "today's calendar",
        "aaj ki meetings", "aaj ke meeting batao",
        "what meetings today", "list todays meetings",
        "my schedule today", "aaj ka schedule",
    ],
    required_entities=[],
)
def todays_meetings(_slots: dict) -> str:
    cal = _outlook_calendar()
    if cal is None:
        return ("Outlook calendar reach nahi ho paya. "
                "Outlook desktop installed + open hona chahiye.")
    today = _date.today()
    start = datetime.combine(today, datetime.min.time())
    end   = start + timedelta(days=1)
    items = list(_query_appointments(start, end))
    if not items:
        return "Aaj koi meeting scheduled nahi hai."
    lines = [f"Today ({today.isoformat()}) — {len(items)} meeting(s):"]
    for appt in items[:10]:
        lines.append(f"  • {_fmt_appointment(appt)}")
    return "\n".join(lines)


# ── this_week_meetings ─────────────────────────────────────────────


@skill(
    name="this_week_meetings",
    description="List appointments in the next 7 days.",
    patterns=[
        "this week meetings", "week ka schedule",
        "is hafte ki meetings", "meetings this week",
        "next 7 days meetings", "schedule for the week",
    ],
    required_entities=[],
)
def this_week_meetings(_slots: dict) -> str:
    cal = _outlook_calendar()
    if cal is None:
        return "Outlook calendar reach nahi ho paya."
    now = datetime.now()
    end = now + timedelta(days=7)
    items = list(_query_appointments(now, end))
    if not items:
        return "Agle 7 din mein koi meeting nahi hai."
    lines = [f"Next 7 days — {len(items)} meeting(s):"]
    for appt in items[:15]:
        lines.append(f"  • {_fmt_appointment(appt)}")
    return "\n".join(lines)
