"""User-defined gestures — record landmark vectors, recognise by cosine.

The user holds a pose, AERIS records N MediaPipe Hands landmark frames,
collapses them to a wrist-relative, palm-width-normalised feature
vector, and stores it in ``data/custom_gestures.json``. On each
incoming frame the per-frame feature vector is compared against every
stored prototype via cosine similarity; matches above
``_MATCH_THRESH`` and held for ``_HOLD_FRAMES`` consecutive frames
fire as a custom gesture.

The feature vector is the flattened (x, y) of all 21 landmarks after:
  1. translate so wrist is at origin
  2. scale so MCP5↔MCP17 (palm width) == 1.0

That makes it position-independent and scale-invariant, so the user
can hold the pose anywhere in frame.

Public API:
    cg = get_custom_gesture_engine()
    cg.record(name, frames=N)        # record + persist
    cg.forget(name) -> bool
    cg.list_names() -> [str]
    cg.classify(landmarks) -> Optional[str]  # one-shot match
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_STORE_PATH = _ROOT / "data" / "custom_gestures.json"

# MediaPipe Hand landmark indices (match core/gesture_engine.py).
_WRIST = 0
_MCP_INDEX = 5
_MCP_PINKY = 17

# Number of (x, y) coords across 21 landmarks → 42-d vector.
_FEAT_DIM = 21 * 2

_MATCH_THRESH = 0.92      # cosine similarity above this counts as a match
_HOLD_FRAMES = 6           # need N consecutive matching frames to fire


_NP_OK = True
try:
    import numpy as _np  # type: ignore
except Exception:
    _np = None
    _NP_OK = False


def _features(landmarks) -> Optional[list[float]]:
    """Compute the 42-d wrist-relative, palm-normalised feature vector.

    ``landmarks`` is any iterable of 21 objects with ``.x`` and ``.y``
    attributes (matches both legacy MediaPipe and Tasks API outputs).
    """
    if not _NP_OK or landmarks is None:
        return None
    try:
        pts = [(float(p.x), float(p.y)) for p in landmarks]
    except Exception:
        return None
    if len(pts) < 21:
        return None
    wx, wy = pts[_WRIST]
    ix, iy = pts[_MCP_INDEX]
    px, py = pts[_MCP_PINKY]
    palm_w = ((ix - px) ** 2 + (iy - py) ** 2) ** 0.5
    if palm_w < 1e-4:
        return None
    out: list[float] = []
    for x, y in pts:
        out.append((x - wx) / palm_w)
        out.append((y - wy) / palm_w)
    # L2-normalise so cosine == dot.
    v = _np.asarray(out, dtype=_np.float32)
    n = float(_np.linalg.norm(v))
    if n <= 0:
        return None
    return (v / n).tolist()


class CustomGestureEngine:
    def __init__(self):
        self._lock = threading.RLock()
        self._data: dict[str, list[list[float]]] = self._load()
        # Consecutive-frame counters for ``classify``.
        self._streak_name: Optional[str] = None
        self._streak_count = 0
        # Recording state.
        self._rec_name: Optional[str] = None
        self._rec_buf: list[list[float]] = []
        self._rec_target_frames = 0

    # ── persistence ───────────────────────────────────────────────

    def _load(self) -> dict[str, list[list[float]]]:
        if not _STORE_PATH.exists():
            return {}
        try:
            with open(_STORE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            out = {}
            for k, vs in raw.items():
                if isinstance(vs, list):
                    out[str(k)] = [list(map(float, v)) for v in vs
                                   if isinstance(v, list) and len(v) == _FEAT_DIM]
            return out
        except Exception as e:
            log.warning("[custom_gestures] load failed: %s", e)
            return {}

    def _save(self) -> None:
        try:
            _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f)
        except Exception as e:
            log.warning("[custom_gestures] save failed: %s", e)

    # ── public API ────────────────────────────────────────────────

    def list_names(self) -> list[str]:
        with self._lock:
            return sorted(self._data.keys())

    def forget(self, name: str) -> bool:
        with self._lock:
            if name in self._data:
                del self._data[name]
                self._save()
                return True
        return False

    def start_recording(self, name: str, frames: int = 12) -> tuple[bool, str]:
        """Begin capturing landmark vectors under ``name`` for ``frames`` hits."""
        if not _NP_OK:
            return False, "numpy missing — install numpy."
        name = (name or "").strip().lower()
        if not name:
            return False, "Name nahi diya."
        with self._lock:
            self._rec_name = name
            self._rec_buf = []
            self._rec_target_frames = max(3, int(frames))
        return True, f"Recording '{name}' — hold the pose; need {frames} samples."

    def feed(self, landmarks) -> Optional[str]:
        """Push one frame of landmarks. Returns:
            * None        — nothing meaningful happened
            * "recorded:<name> N/T" — recording in progress
            * "saved:<name>"        — recording just completed
            * "<name>"              — match fired (cosine threshold + streak)
        """
        feat = _features(landmarks)
        if feat is None:
            return None
        with self._lock:
            # Recording path takes precedence.
            if self._rec_name is not None:
                self._rec_buf.append(feat)
                done = len(self._rec_buf) >= self._rec_target_frames
                name = self._rec_name
                if done:
                    self._data.setdefault(name, []).extend(self._rec_buf)
                    self._save()
                    self._rec_name = None
                    self._rec_buf = []
                    self._rec_target_frames = 0
                    return f"saved:{name}"
                return f"recorded:{name} {len(self._rec_buf)}/{self._rec_target_frames}"

            # Classification path.
            match = self._classify_locked(feat)
        if match is None:
            self._streak_name, self._streak_count = None, 0
            return None
        if match == self._streak_name:
            self._streak_count += 1
        else:
            self._streak_name = match
            self._streak_count = 1
        if self._streak_count == _HOLD_FRAMES:
            return match
        return None

    def classify(self, landmarks) -> Optional[str]:
        """One-shot classify — no streak gating. Used by tests."""
        feat = _features(landmarks)
        if feat is None:
            return None
        with self._lock:
            return self._classify_locked(feat)

    def _classify_locked(self, feat: list[float]) -> Optional[str]:
        if not _NP_OK or not self._data:
            return None
        q = _np.asarray(feat, dtype=_np.float32)
        best_name = None
        best_sim = -1.0
        for name, vecs in self._data.items():
            for v in vecs:
                vv = _np.asarray(v, dtype=_np.float32)
                if vv.shape != q.shape:
                    continue
                sim = float(_np.dot(q, vv))
                if sim > best_sim:
                    best_sim = sim
                    best_name = name
        return best_name if best_sim >= _MATCH_THRESH else None

    def is_recording(self) -> bool:
        with self._lock:
            return self._rec_name is not None

    def recording_progress(self) -> tuple[Optional[str], int, int]:
        with self._lock:
            return self._rec_name, len(self._rec_buf), self._rec_target_frames


_DEFAULT: Optional[CustomGestureEngine] = None


def get_custom_gesture_engine() -> CustomGestureEngine:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = CustomGestureEngine()
    return _DEFAULT
