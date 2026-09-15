"""One-line quick-info skills — time, date, battery, focus-friendly
diagnostics. Each is small enough that lazy-loading isn't worth the noise.

Intentionally separate from ``system_skills`` (which holds longer-running
power-/sleep-/shutdown-style actions) so a regression in one file doesn't
take the other down.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

from core.skill_registry import skill

log = logging.getLogger(__name__)


# ── current_time ───────────────────────────────────────────────────── #


@skill(
    name="current_time",
    description="Speak the wall-clock time (24h + AM/PM).",
    patterns=[
        "what's the time", "what is the time", "current time", "time kya hai",
        "kitna baja hai", "time batao", "samay batao", "abhi kya time hai",
        "tell me the time", "what time is it", "time check karo",
        "abhi kitna time hua hai", "what's the current time", "give me the time",
        "now time", "watch time",
    ],
    required_entities=[],
)
def current_time(_slots: dict) -> str:
    now = datetime.now()
    pretty = now.strftime("%I:%M %p").lstrip("0")
    h24 = now.strftime("%H:%M")
    return f"Abhi {pretty} ho rahe hain ({h24})."


# ── current_date ───────────────────────────────────────────────────── #


@skill(
    name="current_date",
    description="Speak today's date and weekday.",
    patterns=[
        "what's the date", "today's date", "current date", "date kya hai",
        "aaj ki tareekh", "aaj ki date", "tareekh batao", "date batao",
        "what date is it", "tell me the date", "aaj kaun sa din hai",
        "aaj kya date hai", "konsa din hai aaj", "kya tareekh hai aaj",
        "what day is it", "what day today",
    ],
    required_entities=[],
)
def current_date(_slots: dict) -> str:
    now = datetime.now()
    return now.strftime("Aaj %A, %d %B %Y hai.")


# ── battery_status ─────────────────────────────────────────────────── #


@skill(
    name="battery_status",
    description="Battery percentage, plugged-in state, estimated time left.",
    patterns=[
        "battery", "battery status", "battery kitni hai", "battery percent",
        "battery percentage", "kitni battery hai", "battery check karo",
        "how much battery", "battery level", "is charger plugged in",
        "charging status", "charger laga hai kya", "battery time",
        "kitna battery time bacha hai", "phone battery", "laptop battery",
        "remaining battery",
    ],
    required_entities=[],
)
def battery_status(_slots: dict) -> str:
    try:
        import psutil
    except ImportError:
        return "psutil install nahi hai — battery check ke liye `pip install psutil`."
    b = psutil.sensors_battery()
    if b is None:
        return "Battery sensor nahi mila — shayad desktop pe chala raha hai?"
    pct = int(b.percent)
    plugged = "plugged in" if b.power_plugged else "battery par"
    if b.power_plugged or b.secsleft in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN):
        return f"Battery {pct}%, {plugged}."
    mins = b.secsleft // 60
    hrs, rem = divmod(mins, 60)
    if hrs >= 1:
        eta = f"approx {hrs}h {rem}m"
    else:
        eta = f"approx {rem}m"
    return f"Battery {pct}%, {plugged}. {eta} bacha hai."


# ── greeting ───────────────────────────────────────────────────────── #


@skill(
    name="greeting",
    description="Acknowledge a wake/hello with a time-of-day greeting.",
    patterns=[
        "hello", "hi", "hey jarvis", "hey aeris", "namaste", "hello sir",
        "hi jarvis", "kya haal hai", "how are you", "kaisa hai",
        "good morning", "good afternoon", "good evening", "good night",
        "shubh prabhat",
    ],
    required_entities=[],
)
def greeting(_slots: dict) -> str:
    hr = datetime.now().hour
    if 5 <= hr < 12:
        salute = "Good morning"
    elif 12 <= hr < 17:
        salute = "Good afternoon"
    elif 17 <= hr < 22:
        salute = "Good evening"
    else:
        salute = "Good night"
    base = f"{salute}, sir. Kya seva kar sakta hoon?"
    try:
        from core.response_enricher import enriched_reply
        return enriched_reply("greeting", base, hint=salute.lower())
    except Exception:
        return base


# ── clear_screen / chat ────────────────────────────────────────────── #


@skill(
    name="clear_chat",
    description="Acknowledge a clear-chat request. The UI listens for this "
                "and wipes the chat history pane.",
    patterns=[
        "clear chat", "chat clear karo", "wipe chat", "reset chat",
        "purani baatein hatao", "screen clear karo",
        "clear conversation", "naya chat shuru karo",
    ],
    required_entities=[],
)
def clear_chat(_slots: dict) -> str:
    return "[clear_chat]"
