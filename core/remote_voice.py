"""RemoteVoice — the GUI-side seam to the voice service (§6.25).

Third of the three seams, and the one whose lifecycle is least like the others:

* `RemoteBrain` is always-on; the interesting question was how to *retire* it.
* `RemoteVision` must not exist until gestures are switched on.
* Voice is **two capabilities in one process**, and they turn on separately.

That last point is the whole shape of this file. Speaking and listening share a
child — because mic and speaker must be co-located for barge-in to cost no IPC
(§6.25) — but they are not the same permission. AERIS reading a reply out loud
is routine; AERIS holding the microphone open is not. So:

    speak("...")   → spawns the child if needed, and does NOT open the mic
    listen()       → spawns the child if needed, and DOES open the mic
    mute()         → closes the mic, leaves speech working
    shutdown()     → kills the child; nothing audio-related is resident

`speak` deliberately does not imply `listen`. It would be one line shorter to
have both go through a single `enable()`, and that one line would quietly turn
the microphone on every time AERIS answered a typed question.
"""
from __future__ import annotations

import logging
from typing import Any, NamedTuple, Optional

from core.bus_events import payloads, texts
from core.voice_modes import ACTIVE, SLEEPING, STOPPED

log = logging.getLogger(__name__)


class VoicePoll(NamedTuple):
    """Everything one bus drain yielded.

    A named tuple because the queue can only be read once (see `poll`), so
    every signal has to come back from the same call — and because a caller
    that only wants transcripts should not have to remember argument order.
    """
    transcripts: list
    state: Optional[str]
    partials: list


def extract_transcripts(events) -> list:
    """Recognised user speech since the last poll, oldest first."""
    return texts(events, "transcript")


def extract_partials(events) -> list:
    """Mid-utterance partial transcripts (opt-in streaming mode).

    Display-only: a partial is an unfinished sentence, and the service never
    delivers one as a command.
    """
    return texts(events, "partial")


def extract_voice_state(events) -> Optional[str]:
    """The LAST voice state announced in this batch, or ``None``.

    Last rather than all: these are edges on a state machine, and a GUI that
    polled slowly enough to see WOKE then SLEPT wants to render *sleeping*,
    not flash through both.
    """
    seen = [p.get("state") for p in payloads(events, "voice_state")
            if p.get("state")]
    return seen[-1] if seen else None


class RemoteVoice:
    def __init__(self, proxy: Any = None, request_timeout: float = 10.0,
                 ready_timeout: float = 60.0):
        self._proxy = proxy
        self._timeout = request_timeout
        self._ready_timeout = ready_timeout
        self.last_error: str = ""

    # ── plumbing ─────────────────────────────────────────────────────
    def _ensure_proxy(self) -> None:
        if self._proxy is None:
            from core.service_bus import ServiceProxy
            from core.voice_service import voice_handler_factory
            self._proxy = ServiceProxy("voice", voice_handler_factory)

    def _ensure_child(self) -> bool:
        """Bring the voice process up. Does **not** touch the microphone."""
        self._ensure_proxy()
        if self._proxy.is_ready():
            return True
        try:
            ok = bool(self._proxy.start(ready_timeout=self._ready_timeout))
        except Exception as e:
            self.last_error = f"voice service failed to start: {e}"
            log.warning("[remote_voice] %s", self.last_error)
            return False
        if not ok:
            self.last_error = "voice service did not come up"
            log.warning("[remote_voice] %s", self.last_error)
        return ok

    def _request(self, kind: str, payload: dict,
                 timeout: Optional[float] = None) -> Optional[dict]:
        if self._proxy is None:
            return None
        try:
            r = self._proxy.request(kind, payload,
                                    timeout=timeout or self._timeout)
        except Exception as e:
            log.warning("[remote_voice] %s request failed: %s", kind, e)
            return None
        if not getattr(r, "ok", False):
            return {"error": getattr(r, "error", "") or "service error"}
        return dict(getattr(r, "payload", None) or {})

    def is_running(self) -> bool:
        return self._proxy is not None and self._proxy.is_ready()

    # ── speaking (no microphone) ─────────────────────────────────────
    def speak(self, text: str) -> bool:
        """Say something. Never opens the mic — see the module docstring.

        Returns when playback **starts**, not when it finishes: the service
        loop is single-threaded, so blocking here would park the child for the
        length of the utterance — and the request that arrives during an
        utterance is `stop_speaking`. Barge-in would have been queued behind
        the speech it was meant to interrupt. `status()["speaking"]` reports
        whether audio is still playing.
        """
        self.last_error = ""
        if not (text or "").strip():
            return False
        if not self._ensure_child():
            return False
        r = self._request("speak", {"text": text},
                          timeout=max(self._timeout, 60.0))
        if not r or not r.get("ok"):
            self.last_error = (r or {}).get("error") or (r or {}).get(
                "reason") or "speak failed"
            return False
        return True

    def stop_speaking(self) -> bool:
        """Barge-in. The child also detects this locally; this is the GUI's
        explicit interrupt (a stop button, or a new command arriving)."""
        if not self.is_running():
            return False
        r = self._request("stop_speaking", {})
        return bool(r and r.get("ok"))

    # ── listening (opens the microphone) ─────────────────────────────
    def listen(self, state: str = ACTIVE) -> bool:
        """Open the mic. Separate from `speak` on purpose."""
        self.last_error = ""
        if not self._ensure_child():
            return False
        r = self._request("listen_start", {"state": state})
        if not r or not r.get("ok"):
            self.last_error = (r or {}).get("error") or "could not start listening"
            return False
        return True

    def mute(self) -> bool:
        """Close the mic but keep the child, so speech still works instantly."""
        if not self.is_running():
            return True                  # nothing is listening — already muted
        r = self._request("listen_stop", {})
        return bool(r and r.get("ok"))

    def set_state(self, state: str) -> Optional[str]:
        """Force ACTIVE/SLEEPING without stopping capture."""
        if state not in (ACTIVE, SLEEPING):
            return None
        r = self._request("set_state", {"state": state})
        return (r or {}).get("state")

    # ── teardown ─────────────────────────────────────────────────────
    def shutdown(self) -> None:
        """Stop everything and kill the child, so no audio stack is resident."""
        if self._proxy is None:
            return
        ready = self._proxy.is_ready()
        if ready:
            self._request("listen_stop", {})
        alive = getattr(self._proxy, "is_alive", lambda: False)
        try:
            if not (ready or alive()):
                return
        except Exception:
            return
        try:
            self._proxy.stop()
        except Exception as e:
            log.debug("[remote_voice] stop raised: %s", e)

    # ── polling ──────────────────────────────────────────────────────
    def poll(self) -> "VoicePoll":
        """One drain, every signal: transcripts, state, and live partials.

        Drained together because the bus queue is consumed by reading it —
        separate poll methods would mean whichever ran second saw an empty
        queue and silently lost the others' events. That constraint is why
        this returns a named tuple rather than growing a method per signal.
        """
        if not self.is_running():
            return VoicePoll([], None, [])
        try:
            events = self._proxy.poll_events()
        except Exception:
            return VoicePoll([], None, [])
        return VoicePoll(extract_transcripts(events),
                         extract_voice_state(events),
                         extract_partials(events))

    def status(self) -> dict:
        if not self.is_running():
            return {"state": STOPPED, "listening": False, "running": False}
        r = self._request("status", {}) or {}
        r["running"] = True
        return r
