"""Voice-fingerprint speaker identification — best-effort, scipy-only.

Speakers are enrolled by recording a short PCM sample; the spectral
envelope (log-magnitude FFT, averaged over frames, L2-normalised) is
stored as the per-speaker signature. Identification computes the same
signature for a fresh recording and returns the best cosine match.

Accuracy: works well for 2–4 distinctly-voiced people; will misfire on
similar-sounding voices. For production use install ``resemblyzer``
(d-vector embeddings) — this module is the "always-available" fallback
that ships with no extra pip dependencies beyond pyaudio + scipy.

Public API:
    eng = get_voice_id_engine()
    eng.enroll(name, duration_s=4)           -> (ok, msg)
    eng.identify(duration_s=2)               -> (name_or_None, similarity)
    eng.list_speakers() -> [str]
    eng.forget(name) -> bool
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
import wave
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_REG_PATH = _ROOT / "data" / "voice_registry.json"


# Audio capture params (match voice_memo for consistency)
_RATE = 16000
_CHANNELS = 1
_SAMPLE_WIDTH = 2     # 16-bit PCM
_CHUNK = 1024

# Feature params
_FFT_N = 512             # FFT length (power-of-two for speed)
_MATCH_THRESH = 0.78     # cosine similarity above which we declare a match


_NP_OK = True
try:
    import numpy as _np  # type: ignore
except Exception:
    _np = None
    _NP_OK = False


def _record_pcm(duration_s: float) -> Optional[bytes]:
    """Block for ``duration_s`` and return raw PCM bytes. None on failure."""
    try:
        import pyaudio  # type: ignore
    except Exception as e:
        log.info("[voice_id] pyaudio missing: %s", e)
        return None
    try:
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pa.get_format_from_width(_SAMPLE_WIDTH),
                         channels=_CHANNELS, rate=_RATE,
                         input=True, frames_per_buffer=_CHUNK)
    except Exception as e:
        log.info("[voice_id] mic open failed: %s", e)
        return None
    frames: list[bytes] = []
    deadline = time.monotonic() + max(0.5, duration_s)
    try:
        while time.monotonic() < deadline:
            try:
                frames.append(stream.read(_CHUNK, exception_on_overflow=False))
            except Exception as e:
                log.debug("[voice_id] read err: %s", e)
                break
    finally:
        try: stream.stop_stream()
        except Exception: pass
        try: stream.close()
        except Exception: pass
        try: pa.terminate()
        except Exception: pass
    return b"".join(frames) or None


def _pcm_to_signature(pcm: bytes):
    """Compute the L2-normalised log-magnitude spectral envelope.
    Returns a 1-D numpy array of length _FFT_N//2 + 1, or None on failure.
    """
    if not _NP_OK or not pcm:
        return None
    try:
        samples = _np.frombuffer(pcm, dtype=_np.int16).astype(_np.float32) / 32768.0
    except Exception:
        return None
    if len(samples) < _FFT_N:
        return None
    # Frame the signal at 50% hop, take FFT of each, log-magnitude average.
    hop = _FFT_N // 2
    n_frames = max(1, (len(samples) - _FFT_N) // hop + 1)
    window = _np.hanning(_FFT_N).astype(_np.float32)
    total = _np.zeros(_FFT_N // 2 + 1, dtype=_np.float32)
    for i in range(n_frames):
        start = i * hop
        frame = samples[start:start + _FFT_N] * window
        spec = _np.fft.rfft(frame, n=_FFT_N)
        mag = _np.abs(spec) + 1e-9
        total += _np.log(mag)
    avg = total / n_frames
    # L2-normalise so cosine == dot.
    n = float(_np.linalg.norm(avg))
    if n <= 0:
        return None
    return (avg / n).tolist()


class VoiceIDEngine:
    def __init__(self):
        self._lock = threading.RLock()
        self._data: dict[str, list[list[float]]] = self._load()

    # ── persistence ───────────────────────────────────────────────

    def _load(self) -> dict[str, list[list[float]]]:
        if not _REG_PATH.exists():
            return {}
        try:
            with open(_REG_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {str(k): [list(map(float, v)) for v in vs]
                    for k, vs in raw.items() if isinstance(vs, list)}
        except Exception as e:
            log.warning("[voice_id] load failed: %s", e)
            return {}

    def _save(self) -> None:
        try:
            _REG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_REG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f)
        except Exception as e:
            log.warning("[voice_id] save failed: %s", e)

    # ── API ───────────────────────────────────────────────────────

    def is_available(self) -> bool:
        if not _NP_OK:
            return False
        try:
            import pyaudio  # type: ignore  # noqa: F401
            return True
        except Exception:
            return False

    def enroll(self, name: str, duration_s: float = 4.0) -> tuple[bool, str]:
        if not self.is_available():
            return False, "numpy/pyaudio missing — voice ID unavailable."
        name = (name or "").strip().lower()
        if not name:
            return False, "Name nahi diya."
        pcm = _record_pcm(duration_s)
        if not pcm:
            return False, "Recording fail ho gayi."
        sig = _pcm_to_signature(pcm)
        if sig is None:
            return False, "Signature compute fail."
        with self._lock:
            self._data.setdefault(name, []).append(sig)
            self._save()
            n = len(self._data[name])
        return True, f"Enrolled '{name}' — total samples: {n}"

    def identify(self, duration_s: float = 2.0) -> tuple[Optional[str], float]:
        if not self.is_available():
            return None, -1.0
        pcm = _record_pcm(duration_s)
        if not pcm:
            return None, -1.0
        sig = _pcm_to_signature(pcm)
        if sig is None:
            return None, -1.0
        return self._lookup(sig)

    def identify_pcm(self, pcm: bytes) -> tuple[Optional[str], float]:
        """For tests / hooked-up STT — match against an already-captured PCM."""
        sig = _pcm_to_signature(pcm)
        if sig is None:
            return None, -1.0
        return self._lookup(sig)

    def _lookup(self, sig) -> tuple[Optional[str], float]:
        if not _NP_OK:
            return None, -1.0
        q = _np.asarray(sig, dtype=_np.float32)
        best_name = None
        best_sim = -1.0
        with self._lock:
            for name, vecs in self._data.items():
                for v in vecs:
                    vv = _np.asarray(v, dtype=_np.float32)
                    if vv.shape != q.shape:
                        continue
                    sim = float(_np.dot(q, vv))
                    if sim > best_sim:
                        best_sim = sim
                        best_name = name
        if best_sim < _MATCH_THRESH:
            return None, best_sim
        return best_name, best_sim

    def list_speakers(self) -> list[str]:
        with self._lock:
            return sorted(self._data.keys())

    def forget(self, name: str) -> bool:
        with self._lock:
            if name in self._data:
                del self._data[name]
                self._save()
                return True
        return False


_DEFAULT: Optional[VoiceIDEngine] = None


def get_voice_id_engine() -> VoiceIDEngine:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = VoiceIDEngine()
    return _DEFAULT
