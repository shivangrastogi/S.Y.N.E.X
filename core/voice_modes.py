"""Wake / sleep policy for the voice loop — Qt-free, so it can run in a child
process as well as in the GUI (§6.25).

`core/voice_engine.py` is a `QObject` with `pyqtSignal`s, which means the
active/sleeping decision — pure string logic — could only ever run inside a
process that had imported PyQt5. Moving voice into its own service needs that
decision without Qt, so it lives here and *both* surfaces use it. The Qt engine
keeps its module-level `SLEEP_TRIGGERS` / `WAKE_TRIGGERS` names as re-exports,
so nothing that imported them has to change.

Semantics are copied from `ContinuousVoiceEngine._loop` **exactly**, including
the substring matching, because the voice stack is hand-tuned and this is an
integration refactor, not a behaviour change:

* case-insensitive, whitespace-stripped;
* **substring**, not word-boundary — "ok jarvis kya haal hai" wakes it, and so
  would a sentence that merely contains "wake up". That false-positive is
  pre-existing and deliberately preserved here; changing it is a UX decision
  about a tuned voice flow, not a refactor;
* while SLEEPING only a wake trigger is acted on and everything else is
  silently dropped — that silence is the feature;
* a sleep trigger while ACTIVE is consumed, never delivered as a command.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

STOPPED = "STOPPED"
ACTIVE = "ACTIVE"
SLEEPING = "SLEEPING"

SLEEP_TRIGGERS: list[str] = [
    "jarvis sleep",
    "go to sleep",
    "sleep mode",
    "sleep now",
    "jarvis go to sleep",
    "stand by",
    "standby",
]

WAKE_TRIGGERS: list[str] = [
    "jarvis wake up",
    "wake up jarvis",
    "wake up",
    "wakeup",
    "aeris wake up",
    "wake up aeris",
    "ok jarvis",
    "ok aeris",
    "hey jarvis",
    "hey aeris",
    "jarvis wake",
    "aeris wake",
    "activate",
    "jarvis activate",
    "aeris activate",
    "are you there",
    "jaag jao",
    "uth jao",
    "uthho",
]


def _norm(text: str) -> str:
    return (text or "").lower().strip()


def is_sleep_trigger(text: str) -> bool:
    tl = _norm(text)
    return any(kw in tl for kw in SLEEP_TRIGGERS)


def is_wake_trigger(text: str) -> bool:
    tl = _norm(text)
    return any(kw in tl for kw in WAKE_TRIGGERS)


@dataclass
class Decision:
    """What one transcript means, given the current state."""
    state: str                      # the state AFTER this transcript
    deliver: bool = False           # hand it to the brain as a command?
    event: Optional[str] = None     # "woke" | "slept" | None


def decide(state: str, text: str) -> Decision:
    """Pure state transition — the whole voice-mode policy in one function.

    Deliberately total: an unknown state is treated as ACTIVE rather than
    raising, because this runs on a capture thread where an exception costs
    the user their microphone.
    """
    if not (text or "").strip():
        return Decision(state=state)

    if state == SLEEPING:
        if is_wake_trigger(text):
            return Decision(state=ACTIVE, event="woke")
        return Decision(state=SLEEPING)          # silence is the feature

    if state == STOPPED:
        return Decision(state=STOPPED)           # not listening at all

    # ACTIVE (and any unexpected state, treated as ACTIVE).
    if is_sleep_trigger(text):
        return Decision(state=SLEEPING, event="slept")
    return Decision(state=ACTIVE, deliver=True)


def prefer_offline(state: str) -> bool:
    """While asleep, transcribe locally.

    Not an optimisation — a privacy rule. A sleeping AERIS is still hearing
    the room, so that audio must not leave the machine just to check whether
    someone said "wake up". Mirrors `_transcribe(prefer_offline=…)`.
    """
    return state == SLEEPING
