"""Face recognition shared module — JSON registry + InsightFace embedder.

Lifted out of ``run_gesture_tester.py`` so both the tester and the live
GestureEngine can use the same identification path. Stores ArcFace 512-d
embeddings keyed by name in ``data/face_registry_insight.json``.

Graceful degrade: every method is a no-op (or returns an "unavailable"
sentinel) when InsightFace / numpy / cv2 isn't installed. Lazy init —
the heavy detector model only loads on first ``identify_faces()`` call.

Public surface:
    reg = get_registry()
    reg.register("shivang", embedding)   # ndarray, L2-normalised
    name, sim = reg.lookup(embedding)    # (None, sim) if no match

    rec = get_recognizer()
    names = rec.identify_faces(frame_bgr) # ['shivang', None, ...]  (None = stranger)
    rec.register_from_frame("shivang", frame_bgr)
"""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Optional

log = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
REGISTRY_PATH = os.path.join(_ROOT, "data", "face_registry_insight.json")

# Cosine-similarity threshold. ArcFace embeddings are L2-normalised, so
# the dot product is the cosine. 0.45 is conservative enough that two
# different glasses-wearing colleagues don't collide.
FACE_MATCH_THRESHOLD = 0.45
EMBED_DIM = 512


# ── numpy / insightface gates ─────────────────────────────────────


_NP_OK = True
try:
    import numpy as _np  # type: ignore
except Exception:
    _np = None  # type: ignore
    _NP_OK = False

_IF_OK = True
try:
    import insightface as _if  # type: ignore  # noqa: F401
except Exception:
    _IF_OK = False


# ── FaceRegistry ──────────────────────────────────────────────────


class FaceRegistry:
    """Persistent name → list-of-embeddings store with cosine lookup."""

    def __init__(self, path: str = REGISTRY_PATH):
        self._path = path
        self._lock = threading.RLock()
        self._data: dict[str, list[list[float]]] = self._load()

    def _load(self) -> dict[str, list[list[float]]]:
        if not os.path.exists(self._path):
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {str(k): [list(map(float, v)) for v in vs]
                    for k, vs in raw.items() if isinstance(vs, list)}
        except Exception as e:
            log.warning("[face_registry] load failed: %s", e)
            return {}

    def save(self) -> None:
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self._path), exist_ok=True)
                with open(self._path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f)
            except Exception as e:
                log.warning("[face_registry] save failed: %s", e)

    def register(self, name: str, embedding) -> int:
        if not _NP_OK:
            return 0
        name = (name or "").strip().lower()
        if not name:
            return 0
        vec = _np.asarray(embedding, dtype=float).reshape(-1)
        # L2-normalise so cosine == dot.
        n = float(_np.linalg.norm(vec))
        if n > 0:
            vec = vec / n
        with self._lock:
            self._data.setdefault(name, []).append(vec.tolist())
            self.save()
            return len(self._data[name])

    def forget(self, name: str) -> bool:
        name = (name or "").strip().lower()
        with self._lock:
            if name in self._data:
                del self._data[name]
                self.save()
                return True
        return False

    def lookup(self, embedding) -> tuple[Optional[str], float]:
        if not _NP_OK:
            return None, -1.0
        emb = _np.asarray(embedding, dtype=_np.float32).reshape(-1)
        best_name: Optional[str] = None
        best_sim = -1.0
        with self._lock:
            for name, vecs in self._data.items():
                for v in vecs:
                    vv = _np.asarray(v, dtype=_np.float32)
                    sim = float(_np.dot(emb, vv))
                    if sim > best_sim:
                        best_sim = sim
                        best_name = name
        if best_sim < FACE_MATCH_THRESHOLD:
            return None, best_sim
        return best_name, best_sim

    def all_names(self) -> list[str]:
        with self._lock:
            return sorted(self._data.keys())


_REG_SINGLETON: Optional[FaceRegistry] = None


def get_registry() -> FaceRegistry:
    global _REG_SINGLETON
    if _REG_SINGLETON is None:
        _REG_SINGLETON = FaceRegistry()
    return _REG_SINGLETON


# ── Recognizer (InsightFace wrapper) ──────────────────────────────


class FaceRecognizer:
    """Lazy InsightFace detector + recognizer.

    Loads the ``buffalo_l`` model bundle on first use (~270 MB on disk,
    downloaded once into ``~/.insightface/models/``). Subsequent inference
    is CPU-only (~80 ms per frame at 480x480 input).
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._app = None
        self._init_failed = False

    def is_available(self) -> bool:
        return _IF_OK and _NP_OK

    def _ensure_app(self):
        if self._app is not None or self._init_failed:
            return self._app
        with self._lock:
            if self._app is not None or self._init_failed:
                return self._app
            try:
                from insightface.app import FaceAnalysis  # type: ignore
                app = FaceAnalysis(
                    name="buffalo_l",
                    allowed_modules=["detection", "recognition"],
                )
                app.prepare(ctx_id=-1, det_size=(480, 480))
                self._app = app
                log.info("[face_recognizer] InsightFace loaded.")
            except Exception as e:
                log.warning("[face_recognizer] init failed: %s", e)
                self._init_failed = True
        return self._app

    def identify_faces(self, frame_bgr) -> list[Optional[str]]:
        """Return one identified name per detected face (None for stranger)."""
        app = self._ensure_app()
        if app is None:
            return []
        try:
            faces = app.get(frame_bgr)
        except Exception as e:
            log.debug("[face_recognizer] get() failed: %s", e)
            return []
        reg = get_registry()
        out: list[Optional[str]] = []
        for f in faces:
            emb = getattr(f, "normed_embedding", None)
            if emb is None:
                emb = getattr(f, "embedding", None)
                if emb is not None and _NP_OK:
                    n = float(_np.linalg.norm(emb))
                    if n > 0:
                        emb = emb / n
            if emb is None:
                out.append(None)
                continue
            name, _sim = reg.lookup(emb)
            out.append(name)
        return out

    def register_from_frame(self, name: str, frame_bgr) -> tuple[bool, str]:
        """Detect the largest face in ``frame_bgr`` and add it to the registry
        under ``name``. Returns (ok, message)."""
        app = self._ensure_app()
        if app is None:
            return False, "InsightFace nahi mila — pip install insightface."
        if not _NP_OK:
            return False, "numpy nahi mila — pip install numpy."
        try:
            faces = app.get(frame_bgr)
        except Exception as e:
            return False, f"face detect fail: {e}"
        if not faces:
            return False, "Koi face frame mein nahi mila."
        # Pick the LARGEST face (closest to camera).
        def _area(f):
            try:
                x1, y1, x2, y2 = f.bbox
                return max(0, (x2 - x1)) * max(0, (y2 - y1))
            except Exception:
                return 0
        face = max(faces, key=_area)
        emb = getattr(face, "normed_embedding", None) or getattr(face, "embedding", None)
        if emb is None:
            return False, "Face embedding nahi mila."
        n = get_registry().register(name, emb)
        return True, f"Registered '{name}' — total samples: {n}"


_REC_SINGLETON: Optional[FaceRecognizer] = None


def get_recognizer() -> FaceRecognizer:
    global _REC_SINGLETON
    if _REC_SINGLETON is None:
        _REC_SINGLETON = FaceRecognizer()
    return _REC_SINGLETON
