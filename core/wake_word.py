"""Always-on wake word detector using Vosk grammar-restricted recognition.

Reuses the Vosk dependency that is already in the stack — no extra package,
no API key, no licensing. By passing a small JSON grammar of just the wake-
word vocabulary, Vosk becomes a fast, accurate, fully-offline wake detector
at ~3-5% CPU.

Usage:
    detector = WakeWordDetector("data/models/vosk-model-small-en-in-0.4")
    detector.listen(on_wake=engine.handle_one_turn)

The detector pauses cleanly while ``on_wake`` runs (so the main pipeline can
own the mic) and resumes after the callback returns.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Callable, Iterable, Optional

log = logging.getLogger(__name__)


_DEFAULT_WAKES = ("jarvis", "aeris", "hey jarvis", "hey aeris")


class WakeWordDetector:
    def __init__(
        self,
        model_path: str,
        wake_words: Iterable[str] = _DEFAULT_WAKES,
        sample_rate: int = 16000,
        chunk_frames: int = 4000,
    ):
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Vosk model not found at {model_path}. Download from "
                f"https://alphacephei.com/vosk/models (e.g. vosk-model-small-en-in-0.4) "
                f"and unzip into data/models/."
            )

        # Imports kept inside __init__ so that import-time errors don't block
        # the whole assistant when wake mode is unused.
        import vosk
        import pyaudio

        self._vosk = vosk
        self._pyaudio = pyaudio
        self._wakes = tuple(w.lower() for w in wake_words)
        self._sample_rate = sample_rate
        self._chunk_frames = chunk_frames

        self._model = vosk.Model(model_path)
        grammar = json.dumps(list(self._wakes) + ["[unk]"])
        self._recognizer = vosk.KaldiRecognizer(self._model, sample_rate, grammar)

        self._listening = threading.Event()
        self._listening.set()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                          #
    # ------------------------------------------------------------------ #

    def listen(self, on_wake: Callable[[], None]) -> None:
        """Block forever, calling ``on_wake()`` once per detected wake event."""
        p = self._pyaudio.PyAudio()
        stream = p.open(
            format=self._pyaudio.paInt16,
            channels=1,
            rate=self._sample_rate,
            input=True,
            frames_per_buffer=self._chunk_frames,
        )
        stream.start_stream()
        log.info("[WakeWord] Listening for: %s", ", ".join(self._wakes))

        try:
            while not self._stop.is_set():
                if not self._listening.is_set():
                    self._listening.wait()
                    if self._stop.is_set():
                        break

                data = stream.read(self._chunk_frames, exception_on_overflow=False)
                text = self._extract_text(data)
                if text and self._matches(text):
                    self.pause()
                    self._recognizer.Reset()
                    try:
                        on_wake()
                    except Exception as e:
                        log.exception("[WakeWord] on_wake handler raised: %s", e)
                    finally:
                        self.resume()
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def listen_async(self, on_wake: Callable[[], None]) -> threading.Thread:
        """Non-blocking variant. Returns the daemon thread running the loop."""
        if self._thread and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(
            target=self.listen, args=(on_wake,), daemon=True, name="wake-word"
        )
        self._thread.start()
        return self._thread

    def pause(self) -> None:
        """Pause listening (used while the main pipeline owns the mic)."""
        self._listening.clear()

    def resume(self) -> None:
        self._listening.set()

    def stop(self) -> None:
        self._stop.set()
        self._listening.set()

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _extract_text(self, data: bytes) -> str:
        """Pull final + partial text out of Vosk for fast wake response."""
        if self._recognizer.AcceptWaveform(data):
            return json.loads(self._recognizer.Result()).get("text", "").lower().strip()
        return json.loads(self._recognizer.PartialResult()).get("partial", "").lower().strip()

    def _matches(self, text: str) -> bool:
        return any(w in text for w in self._wakes)
