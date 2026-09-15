"""Continuous voice engine with active / sleep modes.

Runs as a QObject on a QThread. An inner daemon thread owns the PyAudio
capture loop so the Qt event loop stays free.

Thread-safety design
--------------------
Only ONE capture thread (_loop_thr) exists at a time. start_listening() will
join() any previous thread before spawning a new one, so the mic hardware is
never touched by two threads simultaneously — the root cause of the crash when
the mic button is tapped rapidly.

Each loop thread stamps its own identity at start and checks it before
emitting the final STOPPED signal, so a stale exiting thread never overwrites
state that a newer thread already set to ACTIVE.

States
------
STOPPED   mic off, loop not running
ACTIVE    listening, transcribing, emitting captured()
SLEEPING  listening for wake words only; all other speech ignored silently

Sleep triggers (case-insensitive substring match):
  "jarvis sleep", "go to sleep", "sleep mode", "sleep now", "stand by"

Wake triggers:
  "jarvis wake up", "wake up", "ok jarvis", "hey jarvis"
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

# ── Keyword tables + mode policy ──────────────────────────────────────
# Single source of truth is `core/voice_modes.py`, which is Qt-free so the
# same wake/sleep decision can run in the voice SERVICE child process
# (§6.25). Re-exported here under the original names so existing importers
# and this module's own `_loop` keep working unchanged.
log = logging.getLogger(__name__)

from core.voice_modes import (           # noqa: E402  (kept next to its users)
    ACTIVE, SLEEPING, STOPPED, SLEEP_TRIGGERS, WAKE_TRIGGERS,
)

_VOSK_REL = os.path.join("data", "models", "vosk-model")

# Max time (seconds) to wait for old capture thread to die before starting new
# one. listen() uses a 1-second timeout, so T1 exits within ~1s of _stop_evt
# being set. 3s gives 3× headroom.
_JOIN_TIMEOUT = 3.0


class ContinuousVoiceEngine(QObject):
    """Qt object — parent to VoiceWorker, which lives on the voice QThread.

    start_listening() / stop_listening() are called from VoiceWorker slots,
    which are serialized by Qt's event queue (no concurrent slot calls).
    The only concurrency is between a slot and the daemon capture thread —
    guarded by _stop_evt and the join() in start_listening().
    """

    listening_started = pyqtSignal()
    captured          = pyqtSignal(str)    # ACTIVE mode only
    sleep_detected    = pyqtSignal()
    wake_detected     = pyqtSignal()
    error             = pyqtSignal(str)
    state_changed     = pyqtSignal(str)    # STOPPED / ACTIVE / SLEEPING

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state    = STOPPED
        self._rec      = None
        self._mic      = None
        self._vosk     = None
        self._stop_evt = threading.Event()
        self._loop_thr: threading.Thread | None = None

    # ── Slots ─────────────────────────────────────────────────────────

    @pyqtSlot()
    def initialize(self) -> None:
        try:
            import speech_recognition as sr
            rec = sr.Recognizer()
            rec.dynamic_energy_threshold = True
            rec.pause_threshold          = 0.70
            rec.phrase_threshold         = 0.30
            rec.non_speaking_duration    = 0.50
            mic = sr.Microphone()
            with mic as source:
                rec.adjust_for_ambient_noise(source, duration=0.4)
            self._rec = rec
            self._mic = mic
        except Exception as e:
            self.error.emit(f"Mic init: {e}")
            return

        try:
            from vosk import Model as VoskModel
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.normpath(os.path.join(root, _VOSK_REL))
            if os.path.isdir(path):
                self._vosk = VoskModel(path)
        except Exception:
            pass

    @pyqtSlot()
    def start_listening(self) -> None:
        if self._state != STOPPED:
            return
        if self._rec is None:
            self.error.emit("Mic not ready — call initialize() first.")
            return

        # ── Drain previous thread before touching the mic again ──────
        # _stop_evt should already be set (set by stop_listening or the
        # previous loop exit). If the thread is still alive, give it up to
        # _JOIN_TIMEOUT to exit gracefully. Without this join, the old thread
        # may still hold the PyAudio stream while the new thread tries to open
        # it — crashing on rapid mic-button taps.
        if self._loop_thr is not None and self._loop_thr.is_alive():
            self._stop_evt.set()                    # ensure it knows to stop
            self._loop_thr.join(timeout=_JOIN_TIMEOUT)

        self._stop_evt.clear()
        self._state = ACTIVE
        self.state_changed.emit(ACTIVE)
        self.listening_started.emit()
        thr = threading.Thread(target=self._loop, daemon=True)
        self._loop_thr = thr
        thr.start()

    @pyqtSlot()
    def stop_listening(self) -> None:
        self._stop_evt.set()
        if self._state != STOPPED:
            self._state = STOPPED
            self.state_changed.emit(STOPPED)

    # ── Capture loop (daemon thread) ──────────────────────────────────

    def _loop(self) -> None:
        # Stamp identity so we can detect if a newer start_listening() has
        # already replaced us before we try to emit the final STOPPED.
        my_thread = threading.current_thread()

        import speech_recognition as sr
        rec = self._rec

        consec_errors = 0
        while not self._stop_evt.is_set():
            try:
                with self._mic as source:
                    try:
                        audio = rec.listen(source, timeout=1.0, phrase_time_limit=8)
                    except sr.WaitTimeoutError:
                        consec_errors = 0
                        continue
            except Exception as e:
                if self._stop_evt.is_set():
                    break
                # Transient PyAudio / device errors should NOT silently
                # kill the listener — that's what stranded the wake-word
                # detector in SLEEPING. Surface the error, back off, then
                # retry. Only give up after several consecutive failures.
                self.error.emit(f"Capture error: {e}")
                consec_errors += 1
                if consec_errors >= 5:
                    break
                time.sleep(0.5)
                continue

            consec_errors = 0
            if self._stop_evt.is_set():
                break

            text = self._transcribe(audio, prefer_offline=(self._state == SLEEPING))
            if not text:
                continue

            tl = text.lower().strip()

            if self._state == SLEEPING:
                if any(kw in tl for kw in WAKE_TRIGGERS):
                    self._state = ACTIVE
                    self.state_changed.emit(ACTIVE)
                    self.wake_detected.emit()

            elif self._state == ACTIVE:
                if any(kw in tl for kw in SLEEP_TRIGGERS):
                    self._state = SLEEPING
                    self.state_changed.emit(SLEEPING)
                    self.sleep_detected.emit()
                else:
                    self.captured.emit(text)

        # Only emit STOPPED if we're still the current loop thread.
        # If start_listening() already launched a successor, leave state alone.
        if self._loop_thr is my_thread and self._state != STOPPED:
            self._state = STOPPED
            self.state_changed.emit(STOPPED)

    # ── Transcription ─────────────────────────────────────────────────

    def _transcribe(self, audio, prefer_offline: bool = False) -> str:
        if prefer_offline and self._vosk is not None:
            out = self._transcribe_vosk(audio)
            if out:
                return out
            # Vosk gave nothing — fall through to Google so wake-words
            # aren't lost when the offline model under-recognises.
        import speech_recognition as sr
        try:
            return self._rec.recognize_google(audio, language="en-IN").lower()
        except sr.UnknownValueError:
            return ""
        except Exception:
            return self._transcribe_vosk(audio)

    def _transcribe_vosk(self, audio) -> str:
        if self._vosk is None:
            return ""
        try:
            from vosk import KaldiRecognizer
            raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
            rec = KaldiRecognizer(self._vosk, 16000)
            rec.AcceptWaveform(raw)
            res = json.loads(rec.FinalResult())
            return res.get("text", "").lower()
        except Exception:
            return ""


# ── split-mode factory (§6.31) ────────────────────────────────────────
def make_voice_engine(parent=None):
    """Build the voice engine this process should use.

    Returns `ContinuousVoiceEngine` normally, or a `RemoteVoiceEngine` — the
    same six signals and three slots, backed by the audio child process — when
    ``AERIS_SPLIT_VOICE=1``.

    Exists so the GUI's `VoiceWorker.initialize()` is a one-line change that is
    provably behaviour-preserving with the flag off: same class, same object.
    A broken split falls back rather than costing the user their microphone.
    """
    try:
        from core.remote_voice_engine import (
            RemoteVoiceEngine, split_voice_enabled,
        )
        if split_voice_enabled():
            log.info("[voice] split mode — mic and speaker in a child process")
            return RemoteVoiceEngine(parent)
    except Exception as e:
        log.warning("[voice] split mode unavailable (%s) — in-process", e)
    return ContinuousVoiceEngine(parent)
