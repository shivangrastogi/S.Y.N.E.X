"""Live STT transcript voice surface.

Skills:
  * ``transcript_on``  — open the live transcript pane
  * ``transcript_off`` — close it
  * ``transcript_status``
  * ``transcript_log`` — print the last N events from the bus
"""
from __future__ import annotations

import logging
import threading
import time

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="transcript_on",
    description="Open the live STT transcript pane — see your speech "
                "and AERIS replies stream in real-time.",
    patterns=[
        "transcript on", "show transcript", "open transcript",
        "live transcript", "transcript kholo",
        "stt transcript on", "captions on",
        "show live captions",
    ],
    required_entities=[],
)
def transcript_on(_slots: dict) -> str:
    def _run():
        try:
            from ui.transcript_pane import open_transcript_pane
            open_transcript_pane()
        except Exception as e:
            log.warning("[transcript_skill] open failed: %s", e)
    threading.Thread(target=_run, daemon=True, name="TranscriptOpen").start()
    return "Transcript pane khol raha hoon."


@skill(
    name="transcript_off",
    description="Close the live transcript pane.",
    patterns=[
        "transcript off", "hide transcript", "close transcript",
        "transcript band karo", "captions off",
        "hide live captions", "transcript hide karo",
    ],
    required_entities=[],
)
def transcript_off(_slots: dict) -> str:
    def _run():
        try:
            from ui.transcript_pane import hide_transcript_pane
            hide_transcript_pane()
        except Exception as e:
            log.warning("[transcript_skill] hide failed: %s", e)
    threading.Thread(target=_run, daemon=True, name="TranscriptHide").start()
    return "Transcript pane OFF."


@skill(
    name="transcript_status",
    description="Report whether the transcript pane is visible.",
    patterns=[
        "transcript status", "is transcript on",
        "transcript visible kya hai", "captions status",
    ],
    required_entities=[],
)
def transcript_status(_slots: dict) -> str:
    try:
        from ui.transcript_pane import is_transcript_visible
        return f"Transcript: {'visible' if is_transcript_visible() else 'hidden'}."
    except Exception as e:
        return f"transcript_pane load fail: {e}"


@skill(
    name="transcript_log",
    description="Print the last 10 STT events from the transcript bus.",
    patterns=[
        "transcript log", "recent transcript", "show transcript history",
        "transcript history", "stt log",
        "transcript ke recent events",
    ],
    required_entities=[],
)
def transcript_log(_slots: dict) -> str:
    try:
        from core.transcript_bus import get_bus
    except Exception as e:
        return f"transcript_bus load fail: {e}"
    events = get_bus().recent(10)
    if not events:
        return "Transcript bus khaali hai."
    lines = [f"Last {len(events)} transcript event(s):"]
    for e in events:
        when = time.strftime("%H:%M:%S", time.localtime(e.get("ts") or time.time()))
        role = (e.get("role") or "final")[:7]
        text = (e.get("text") or "").strip()
        lines.append(f"  {when}  {role:7s}  {text[:80]}")
    return "\n".join(lines)
