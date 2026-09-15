"""`ContinuousVoiceEngine`'s surface, backed by the voice child process (§6.31).

The vision cutover (§6.30) converted a *listener list* to bus polling. Voice is
the same idea with a different shape: `VoiceWorker` — which exists identically
in `ui/jarvis_v31/main_window.py` and `ui/aeris_v6/workers.py` — consumes six
**Qt signals** plus three methods:

    listening_started  captured(str)  sleep_detected  wake_detected
    state_changed(str)  error(str)
    initialize()  start_listening()  stop_listening()

So the adapter has to be a `QObject` that emits those same signals, sourced
from `RemoteVoice.poll()` instead of from an in-process capture thread. Qt
belongs on this side of the boundary anyway — the whole point of §6.25 is that
the *audio* moves out and the GUI keeps its event loop.

Polling runs on a `QTimer`, not a thread, which is a deliberate difference from
the gesture adapter. `VoiceWorker` already lives on a `QThread` with an event
loop, so a timer there fires **on that thread** and the signals are emitted
from the same place `ContinuousVoiceEngine` emitted them. Using a plain thread
would have meant emitting from a non-Qt thread — legal, but a different
threading contract than the one the GUI was written against.

Wake/sleep are *derived from state transitions* rather than from the service's
own `voice_woke`/`voice_slept` events, because `RemoteVoice.poll()`
deliberately collapses state to the last edge in a batch (a GUI that polled
slowly should render "sleeping", not flash through both). Deriving keeps the
signal consistent with the state the GUI is about to be told about.

Off unless ``AERIS_SPLIT_VOICE=1``.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from core.voice_modes import ACTIVE, SLEEPING, STOPPED

log = logging.getLogger(__name__)

ENV_SPLIT_VOICE = "AERIS_SPLIT_VOICE"

# Drain interval. Voice turns are seconds apart and endpointing already adds
# its own latency, so this is comfortably below anything perceptible.
POLL_MS = 120


def split_voice_enabled(environ: Optional[dict] = None) -> bool:
    raw = (environ if environ is not None else os.environ).get(ENV_SPLIT_VOICE, "")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


class RemoteVoiceEngine(QObject):
    """Drop-in for `ContinuousVoiceEngine`, backed by the voice service."""

    listening_started = pyqtSignal()
    captured = pyqtSignal(str)
    sleep_detected = pyqtSignal()
    wake_detected = pyqtSignal()
    state_changed = pyqtSignal(str)
    error = pyqtSignal(str)
    # Additive: live partials when AERIS_VOICE_STREAMING is on (§6.29). The
    # existing GUIs never connect it, which is why it can be added safely.
    partial = pyqtSignal(str)

    def __init__(self, parent=None, voice: Any = None, poll_ms: int = POLL_MS):
        super().__init__(parent)
        self._voice = voice
        self._poll_ms = poll_ms
        self._timer: Optional[QTimer] = None
        self._state = STOPPED

    # ── the ContinuousVoiceEngine surface ────────────────────────────
    @pyqtSlot()
    def initialize(self) -> None:
        """Prepare, but do not open the microphone.

        Mirrors `ContinuousVoiceEngine.initialize`, which readies the
        recogniser without starting to listen — and matches §6.25's rule that
        nothing opens the mic until someone actually asks to listen.
        """
        try:
            if self._voice is None:
                from core.remote_voice import RemoteVoice
                self._voice = RemoteVoice()
        except Exception as e:
            self.error.emit(f"Voice init failed: {e}")

    @pyqtSlot()
    def start_listening(self) -> None:
        if self._voice is None:
            self.initialize()
        if self._voice is None:
            return
        try:
            ok = bool(self._voice.listen())
        except Exception as e:
            self.error.emit(f"Capture error: {e}")
            return
        if not ok:
            self.error.emit(getattr(self._voice, "last_error", "")
                            or "could not start listening")
            return
        self._set_state(ACTIVE)
        self.listening_started.emit()
        self._start_timer()

    @pyqtSlot()
    def stop_listening(self) -> None:
        self._stop_timer()
        if self._voice is not None:
            try:
                self._voice.mute()
            except Exception as e:
                log.debug("[remote_voice_engine] mute raised: %s", e)
        self._set_state(STOPPED)

    # ── draining ─────────────────────────────────────────────────────
    @pyqtSlot()
    def drain_once(self) -> int:
        """One poll → signals. Returns how many transcripts were surfaced.

        Callable directly, so the whole signal mapping is testable without
        running a Qt event loop.
        """
        if self._voice is None:
            return 0
        try:
            got = self._voice.poll()
        except Exception as e:
            log.debug("[remote_voice_engine] poll failed: %s", e)
            return 0
        for text in getattr(got, "partials", None) or []:
            self.partial.emit(text)
        state = getattr(got, "state", None)
        if state:
            self._set_state(state)
        n = 0
        for text in getattr(got, "transcripts", None) or []:
            self.captured.emit(text)
            n += 1
        return n

    def _set_state(self, state: str) -> None:
        if state == self._state:
            return
        prev, self._state = self._state, state
        # Derived, not read from the service's own woke/slept events — see the
        # module docstring on last-edge collapsing.
        if prev == SLEEPING and state == ACTIVE:
            self.wake_detected.emit()
        elif prev == ACTIVE and state == SLEEPING:
            self.sleep_detected.emit()
        self.state_changed.emit(state)

    # ── timer plumbing ───────────────────────────────────────────────
    def _start_timer(self) -> None:
        if self._timer is not None:
            return
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.drain_once)
        self._timer.start(self._poll_ms)

    def _stop_timer(self) -> None:
        t, self._timer = self._timer, None
        if t is not None:
            t.stop()
            t.deleteLater()

    # ── teardown ─────────────────────────────────────────────────────
    def shutdown(self) -> None:
        """Kill the child entirely — no audio stack resident."""
        self._stop_timer()
        if self._voice is not None:
            try:
                self._voice.shutdown()
            except Exception as e:
                log.debug("[remote_voice_engine] shutdown raised: %s", e)
        self._set_state(STOPPED)
