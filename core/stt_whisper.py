"""Offline STT via faster-whisper — drop-in alternative to Google STT.

Better for Hinglish / mixed-language users and works fully offline.
Lazy-loads the model (~150 MB for ``base``) on first ``transcribe()``
call. Graceful degrade — if faster-whisper isn't installed the engine
reports "unavailable" and callers can fall back to the regular STT.

Public API:
    eng = get_whisper_engine()
    eng.is_available()        -> bool
    eng.transcribe(pcm_or_wav_path) -> str
    eng.transcribe_mic(duration_s=4) -> str
    eng.model_size            -> "tiny" | "base" | "small" | "medium" | "large-v3"
    eng.set_model_size(size)
"""
from __future__ import annotations

import io
import logging
import os
import tempfile
import threading
import time
import wave
from typing import Optional, Union

log = logging.getLogger(__name__)


_DEFAULT_MODEL = "base"        # ~150 MB, good speed/accuracy trade
_RATE = 16000
_CHANNELS = 1
_SAMPLE_WIDTH = 2
_CHUNK = 1024


def _whisper_available() -> bool:
    try:
        import faster_whisper  # type: ignore  # noqa: F401
        return True
    except Exception:
        return False


class WhisperEngine:
    def __init__(self):
        self._lock = threading.RLock()
        self._model = None
        self._model_size = _DEFAULT_MODEL
        self._init_failed = False

    @property
    def model_size(self) -> str:
        return self._model_size

    def is_available(self) -> bool:
        return _whisper_available()

    def set_model_size(self, size: str) -> tuple[bool, str]:
        valid = {"tiny", "base", "small", "medium", "large-v3"}
        size = (size or "").strip().lower()
        if size not in valid:
            return False, f"Invalid size '{size}'. Pick one of: {', '.join(sorted(valid))}."
        with self._lock:
            self._model_size = size
            self._model = None        # force reload on next transcribe()
            self._init_failed = False
        return True, f"Whisper model size → {size} (loads on next transcribe)."

    def _ensure_model(self):
        if self._model is not None or self._init_failed:
            return self._model
        with self._lock:
            if self._model is not None or self._init_failed:
                return self._model
            try:
                from faster_whisper import WhisperModel  # type: ignore
                # CPU + int8 keeps it on commodity machines; user can edit
                # this if they have CUDA.
                self._model = WhisperModel(self._model_size, device="cpu",
                                            compute_type="int8")
                log.info("[whisper] model '%s' loaded.", self._model_size)
            except Exception as e:
                log.warning("[whisper] model load failed: %s", e)
                self._init_failed = True
        return self._model

    # ── transcription ────────────────────────────────────────────

    def transcribe(self, source: Union[str, bytes]) -> Optional[str]:
        """Transcribe a wav file path OR raw 16kHz int16 mono PCM bytes."""
        if not self.is_available():
            return None
        model = self._ensure_model()
        if model is None:
            return None
        wav_path = None
        cleanup = False
        try:
            if isinstance(source, (bytes, bytearray)):
                # Spool to a temp wav so faster-whisper can read it.
                fd, wav_path = tempfile.mkstemp(prefix="aeris_whisper_", suffix=".wav")
                os.close(fd)
                cleanup = True
                with wave.open(wav_path, "wb") as wf:
                    wf.setnchannels(_CHANNELS)
                    wf.setsampwidth(_SAMPLE_WIDTH)
                    wf.setframerate(_RATE)
                    wf.writeframes(bytes(source))
            else:
                wav_path = str(source)
            segments, _info = model.transcribe(wav_path, beam_size=1)
            text = " ".join(seg.text for seg in segments).strip()
            return text or None
        except Exception as e:
            log.info("[whisper] transcribe failed: %s", e)
            return None
        finally:
            if cleanup and wav_path:
                try: os.remove(wav_path)
                except Exception: pass

    def transcribe_mic(self, duration_s: float = 4.0) -> Optional[str]:
        try:
            import pyaudio  # type: ignore
        except Exception as e:
            log.info("[whisper] pyaudio missing: %s", e)
            return None
        try:
            pa = pyaudio.PyAudio()
            stream = pa.open(format=pa.get_format_from_width(_SAMPLE_WIDTH),
                             channels=_CHANNELS, rate=_RATE,
                             input=True, frames_per_buffer=_CHUNK)
        except Exception as e:
            log.info("[whisper] mic open failed: %s", e)
            return None
        frames: list[bytes] = []
        deadline = time.monotonic() + max(0.5, duration_s)
        try:
            while time.monotonic() < deadline:
                try:
                    frames.append(stream.read(_CHUNK, exception_on_overflow=False))
                except Exception as e:
                    log.debug("[whisper] read err: %s", e)
                    break
        finally:
            try: stream.stop_stream()
            except Exception: pass
            try: stream.close()
            except Exception: pass
            try: pa.terminate()
            except Exception: pass
        pcm = b"".join(frames)
        if not pcm:
            return None
        return self.transcribe(pcm)


_DEFAULT: Optional[WhisperEngine] = None


def get_whisper_engine() -> WhisperEngine:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = WhisperEngine()
    return _DEFAULT
