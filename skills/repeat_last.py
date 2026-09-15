"""Re-run the previous user command — "do that again", "phir se karo".

Implementation note: skill handlers return a string, but to re-execute
a previous command we need to go through the brain again. This skill
returns a ``[repeat:<command>]`` sentinel which the UI intercepts and
feeds back through the normal user-send path. CLI / headless callers
that don't recognise the sentinel still get a readable message about
what's being re-run.

Reads the live conversation history via ``core.conversation.get_active()``
which the main engine publishes during boot.
"""
from __future__ import annotations

import logging

from core.conversation import get_active
from core.skill_registry import skill

log = logging.getLogger(__name__)

# These phrases are recognised triggers for the skill itself — when the
# previous user text matches one of them we skip OVER it (skip=N) so we
# don't get stuck repeating "repeat" forever.
_REPEAT_TRIGGERS = {
    "repeat", "phir se", "phir se karo", "do it again", "do that again",
    "wahi karo", "wohi karo", "again", "redo", "rerun", "repeat last",
    "repeat last command", "pichla wala karo", "pichla command",
}


def _is_trigger(text: str) -> bool:
    return (text or "").strip().lower() in _REPEAT_TRIGGERS


@skill(
    name="repeat_last",
    description="Re-execute the previous user command (skips this 'repeat' trigger itself).",
    patterns=[
        "repeat", "repeat last", "repeat last command",
        "do it again", "do that again", "again", "redo", "rerun",
        "phir se karo", "phir se", "wahi karo", "wohi karo",
        "pichla wala karo", "pichla command chalao",
        "vahi chalao", "fir se",
    ],
    required_entities=[],
)
def repeat_last(_slots: dict) -> str:
    hist = get_active()
    if hist is None:
        return "History uplabdh nahi hai — repeat ke liye engine chahiye."
    # Walk backward, skipping any user message that's itself a 'repeat' trigger.
    skip = 0
    while True:
        last = hist.last_user_text(skip=skip)
        if last is None:
            return "Pichla koi command nahi mila."
        if not _is_trigger(last):
            return f"[repeat:{last}]"
        skip += 1
        if skip > 5:
            return "Sirf repeat hi repeat hai — pehle koi asli command bolo."
