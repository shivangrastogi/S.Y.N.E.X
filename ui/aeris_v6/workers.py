"""Background workers — the engine-driving QThread objects.

These mirror the proven worker pattern from ``ui/jarvis_v31/main_window.py``
(BrainWorker / VoiceWorker / SpeakWorker) but live here so the v6 GUI is
self-contained and doesn't import the entire old widget tree. The threading
contract is identical, so the real :class:`core.main_engine.JarvisMainEngine`
is driven exactly as before.
"""
from __future__ import annotations

import time

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class BrainWorker(QObject):
    """Owns JarvisMainEngine on its own QThread. Heavy load happens here."""

    ready = pyqtSignal()
    responded = pyqtSignal(str, dict)         # (reply_text, meta)
    load_progress = pyqtSignal(str, str, int)  # (log_type, msg, pct)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._engine = None

    @pyqtSlot()
    def initialize(self):
        try:
            self.load_progress.emit("SYS", "Booting JarvisMainEngine…", 4)
            from core.main_engine import JarvisMainEngine
            self._engine = JarvisMainEngine(
                stt="SKIP", tts="SKIP", verbose=False, lazy=True,
            )
            for log_type, msg, pct in self._engine.setup_iter():
                self.load_progress.emit(log_type, msg, pct)
            self.ready.emit()
        except Exception as e:
            msg = f"Brain init failed: {e}"
            es = str(e)
            if "WinError 1114" in es or "DLL" in es or "torch" in es.lower():
                msg += (" — try: pip install --upgrade --force-reinstall torch"
                        " (or run from the .venv with a working PyTorch).")
            elif "pyttsx3" in es:
                msg += " — install with: pip install pyttsx3"
            self.error.emit(msg)

    @pyqtSlot(str)
    def process(self, text: str):
        if self._engine is None:
            self.error.emit("Brain not ready yet."); return
        t0 = time.monotonic()
        try:
            reply = self._engine.process_text(text)
        except Exception as e:
            self.error.emit(f"process_text crashed: {e}"); return
        latency_ms = int((time.monotonic() - t0) * 1000)
        meta = {"intent": "general", "confidence": 0.0,
                "latency_ms": latency_ms, "action": "executed"}
        try:
            cur = self._engine.feedback._conn.execute(
                "SELECT predicted_intent, confidence, action_taken "
                "FROM utterances ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if cur:
                meta["intent"] = cur["predicted_intent"] or "general"
                meta["confidence"] = float(cur["confidence"] or 0.0) * 100
                meta["action"] = cur["action_taken"] or "executed"
        except Exception:
            pass
        self.responded.emit(reply or "", meta)

    def engine(self):
        return self._engine


class VoiceWorker(QObject):
    """Wraps ContinuousVoiceEngine as a QObject for QThread use."""

    listening_started = pyqtSignal()
    captured = pyqtSignal(str)
    sleep_detected = pyqtSignal()
    wake_detected = pyqtSignal()
    state_changed = pyqtSignal(str)   # STOPPED / ACTIVE / SLEEPING
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._engine = None

    @pyqtSlot()
    def initialize(self):
        try:
            # Split-mode aware: returns ContinuousVoiceEngine unless
            # AERIS_SPLIT_VOICE=1, in which case the mic and speaker live in a
            # child process behind the same signals (§6.31).
            from core.voice_engine import make_voice_engine
            eng = make_voice_engine(self)
            eng.listening_started.connect(self.listening_started)
            eng.captured.connect(self.captured)
            eng.sleep_detected.connect(self.sleep_detected)
            eng.wake_detected.connect(self.wake_detected)
            eng.state_changed.connect(self.state_changed)
            eng.error.connect(self.error)
            self._engine = eng
            eng.initialize()
        except Exception as e:
            self.error.emit(f"Voice init failed: {e}")

    @pyqtSlot()
    def start_listening(self):
        if self._engine:
            self._engine.start_listening()

    @pyqtSlot()
    def stop_listening(self):
        if self._engine:
            self._engine.stop_listening()


class SpeakWorker(QObject):
    """Owns TTS. `speak(text)` slot — non-blocking from the UI's POV."""

    spoken = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._tts = None

    @pyqtSlot()
    def initialize(self):
        try:
            from core.tts import TTS
            self._tts = TTS()
        except Exception as e:
            self.error.emit(f"TTS init failed: {e}")

    @pyqtSlot(str)
    def speak(self, text: str):
        if not text or self._tts is None:
            return
        try:
            self._tts.speak(text)
            self.spoken.emit(text)
        except Exception as e:
            self.error.emit(f"TTS speak failed: {e}")
