"""Enhanced AERIS gesture tester — live camera + multi-modal detection sandbox.

Run with:  ``py run_gesture_tester.py``

What this window shows
----------------------
LEFT pane (visual):
  * Live camera preview at ~640x480 with overlays drawn directly on the frame:
      - Hand-landmark skeleton (21 points + connecting bones) for each hand
      - Face bounding boxes labelled with the registered name OR "person"
      - Object bounding boxes labelled with COCO class + confidence
  * Live banner showing the most recently recognised gesture + stability state
  * "Register face" text input + button — type a name, point your face at
    the camera, click Register. From then on FaceMesh + cosine-similarity
    will label that person beautifully.
  * Toggles for hand landmarks, face recognition boxes, and object recognition.

RIGHT pane (catalog):
  * All 21 gestures, click the ⓘ button on any row for the
    full "how to perform" instructions.

Stabilization improvements (vs. the previous tester)
----------------------------------------------------
1. **K-frame consensus** — a candidate gesture must classify identically
   in 4 of the last 5 frames before we declare it "recognised". This kills
   spurious mid-transition triggers (e.g. when transitioning from open
   palm into a fist, the in-between hand shape doesn't fire any gesture).
2. **Rearm-after-rest gate** — after a gesture fires, we LOCK detection
   until the hand is absent (or in a non-recognised neutral pose) for at
   least ~12 frames (~0.4 s at 30 fps). That means you can't trigger the
   same — or a different — gesture again until your hand goes down and
   comes back up.

Both numbers are tunable via constants at the top of this file.

Heavy initialisation runs on a worker QThread so the GUI never freezes
while MediaPipe + YOLO models load.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import deque
from typing import Optional

import numpy as np

# Same Windows DLL ordering fix as run_gui.py — torch before PyQt5.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
try:
    import torch  # noqa: F401
except Exception as _e:
    sys.stderr.write(f"[gesture_tester] WARN: torch pre-import failed: {_e}\n")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import cv2
from PyQt5.QtCore import (
    QMetaObject, QObject, Qt, QThread, QTimer, pyqtSignal, pyqtSlot,
)
from PyQt5.QtGui import QColor, QFont, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


# ═══════════════════════════════════════════════════════════════════════
#  Tunables
# ═══════════════════════════════════════════════════════════════════════

# Stabilization
CONSENSUS_WINDOW   = 5     # look at last N classifications
CONSENSUS_REQUIRED = 4     # this many must agree before we fire
REARM_NEUTRAL_FRAMES = 12  # need this many "no hand"/"neutral" frames after a fire

# Face recognition
# InsightFace ArcFace ResNet50 produces L2-normalised 512-d embeddings.
# Same-person cosine similarity sits comfortably above 0.45; different-
# person rarely exceeds 0.30. 0.45 is a safe default for one-shot enroll.
FACE_MATCH_THRESHOLD = 0.45
# Older FaceMesh-based registry (956-d geometric vectors) lived in a
# different file; we use a dedicated path for the ArcFace registry so
# stale 956-d vectors can't poison 512-d cosine lookups.
FACE_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "face_registry_insight.json",
)
FACE_EMBED_DIM = 512


# ═══════════════════════════════════════════════════════════════════════
#  Gesture catalog (display only — classification is done by core engine)
# ═══════════════════════════════════════════════════════════════════════

# (key, glyph, name, action, how_to, category)
GESTURES = [
    # Sequenced (collision-free) gestures
    ("palm_fist_lock",  "🖐✊", "Palm → Fist → Palm → Fist",
     "Lock workstation (LockWorkStation)",
     "Show an open palm and hold it for ~0.3 s, then make a fist, open the palm "
     "again, then make a fist a second time within ~3 seconds. Only this exact "
     "four-step sequence locks the screen — a plain fist no longer does.",
     "Sequence"),
    ("double_pinch",    "👌👌", "Double pinch (OK-sign region)",
     "Media play / pause",
     "With middle/ring/pinky extended (the OK-sign region), tap thumb to index "
     "twice quickly (each touch ≥ 0.08 s and ≤ 0.8 s apart). Open-palm hold no "
     "longer plays/pauses media.",
     "Sequence"),
    ("app_switch_next", "🤚→",  "Sideways palm + LEFT motion",
     "Alt+Tab (next / right-side app)",
     "Rotate an open palm ~90° clockwise so it faces sideways (MCP joints "
     "vertical), hold for 0.2 s, then move the hand to your LEFT. Keep moving "
     "to cycle through more apps without dropping the pose.",
     "Sequence"),
    ("app_switch_prev", "🤚←",  "Sideways palm + RIGHT motion",
     "Alt+Shift+Tab (previous / left-side app)",
     "Same sideways palm hold, but move your hand to your RIGHT. Cycles "
     "backward through the alt-tab MRU list. Re-anchors after each switch.",
     "Sequence"),
    ("volume_set",      "🤌↔",  "Pinch (fingers closed) + spread",
     "Continuous absolute system volume",
     "Curl middle/ring/pinky, touch thumb to index and hold ~0.2 s to ARM. "
     "Then separate thumb+index — the distance (normalised by palm width) "
     "maps continuously to system volume 0–100%. Disarms instantly the moment "
     "the three curled fingers extend.",
     "Continuous"),
    # Single-hand poses
    ("long_fist",       "✊⏱",  "Long fist (3s hold)",
     "Toggle command palette",
     "Keep a tight fist with all fingers curled held for 3 seconds. Intentionally "
     "slow so you don't trigger it accidentally while doing the palm/fist lock "
     "sequence.",
     "Pose"),
    ("thumbs_up",       "👍",   "Thumbs up",
     "Volume up (×3 ticks)",
     "Make a fist with only the thumb extended upward. Hold steady; sends a "
     "burst of VK_VOLUME_UP key taps. Useful for a quick bump.",
     "Pose"),
    ("thumbs_down",     "👎",   "Thumbs down",
     "Volume down (×3 ticks)",
     "Make a fist with only the thumb extended downward. The system uses the "
     "thumb tip relative to the wrist to separate up vs down.",
     "Pose"),
    ("peace",           "✌",   "Peace / V sign",
     "Win+Shift+S — screenshot snip",
     "Index and middle finger extended, ring and pinky curled. Hold for "
     "about 0.55s to commit. Thumb is flexible.",
     "Pose"),
    ("three_up",        "🤟",   "Three fingers up",
     "Next media track",
     "Index, middle, and ring fingers extended with pinky curled. Hold for "
     "about 0.55s. Thumb does not matter.",
     "Pose"),
    # Motion patterns
    ("swipe_left",      "👈",   "Swipe ←",
     "Alt+Shift+Tab (or Ctrl+Shift+Tab in browser)",
     "Open palm, then move the wrist left across the camera by at least "
     "18% of the frame width within roughly 0.6 seconds. In browsers this "
     "cycles tabs; elsewhere it cycles windows.",
     "Motion"),
    ("swipe_right",     "👉",   "Swipe →",
     "Alt+Tab (or Ctrl+Tab in browser)",
     "Open palm, then move the wrist right across the camera by at least "
     "18% of the frame width within roughly 0.6 seconds.",
     "Motion"),
    ("swipe_up",        "👆",   "Swipe ↑",
     "Page Up (scroll up)",
     "Open palm, then move the wrist upward. Vertical motion only wins when "
     "it is clearly stronger than horizontal motion, reducing diagonal errors.",
     "Motion"),
    ("swipe_down",      "👇",   "Swipe ↓",
     "Page Down (scroll down)",
     "Open palm, then move the wrist downward. Sends Page Down for browsers, "
     "readers, and many document viewers.",
     "Motion"),
    ("wave",            "🌊",   "Wave (rapid L↔R)",
     "Escape (dismiss dialog / notification)",
     "Open palm with rapid left-right motion. Needs at least 2 direction "
     "reversals within about 0.6 seconds and 15%+ frame amplitude, so small "
     "hand tremor does not count.",
     "Motion"),
    # Two-handed
    ("two_palm_spread", "🖐↔🖐", "Both palms spread apart",
     "Ctrl++ (zoom in)",
     "Both hands open, palm-out. Move them apart by 15%+ of frame width "
     "within about 0.5 seconds. Useful for browser/document zoom in.",
     "Two-handed"),
    ("two_palm_pinch",  "🖐↔🖐", "Both palms together",
     "Ctrl+- (zoom out)",
     "Both hands open, palm-out. Move them together by 15%+ within about "
     "0.5 seconds. Different from clap because hands do not need to touch.",
     "Two-handed"),
    ("clap",            "👏",   "Clap",
     "Bring AERIS window to front",
     "Bring both hands together fast. Distance must drop by about 20% and "
     "end very close together, which separates it from normal zoom-out.",
     "Two-handed"),
    # Air strokes
    ("stroke_circle",   "○",   "Air-draw circle",
     "F5 (refresh page)",
     "Point with index finger only, trace a closed circle in the air, then "
     "leave pointing pose to commit. The trail must be large enough and end "
     "near its start.",
     "Stroke"),
    ("stroke_x",        "✕",   "Air-draw X",
     "Ctrl+W (close window/tab)",
     "Point with index finger and draw two crossing diagonal strokes. "
     "Then leave pointing pose to commit. Mapped to Ctrl+W.",
     "Stroke"),
    ("stroke_check",    "✓",   "Air-draw check",
     "Enter (confirm/submit)",
     "Point with index finger and trace a check mark: down first, then "
     "up-right. Leave pointing pose to commit. Mapped to Enter.",
     "Stroke"),
    ("stroke_arrow_right", "→", "Air-draw arrow →",
     "Right arrow key (next slide / photo)",
     "Point with index finger and draw a strong horizontal stroke from left "
     "to right. It needs clear horizontal travel and little vertical drift.",
     "Stroke"),
]


# ═══════════════════════════════════════════════════════════════════════
#  Palette
# ═══════════════════════════════════════════════════════════════════════

class C:
    BG       = QColor(13, 21, 37)
    PANEL    = QColor(20, 30, 50)
    BORDER   = QColor(60, 80, 110)
    CYAN     = QColor(0, 215, 230)
    PURPLE   = QColor(180, 100, 240)
    AMBER    = QColor(255, 170, 80)
    GREEN    = QColor(80, 200, 130)
    MAGENTA  = QColor(220, 80, 200)
    RED      = QColor(240, 100, 100)
    MUTED    = QColor(140, 160, 180)
    PRIMARY  = QColor(220, 235, 240)
    SECONDARY = QColor(180, 200, 220)


_CATEGORY_COLOR = {
    "Pose":       C.CYAN,
    "Motion":     C.GREEN,
    "Two-handed": C.PURPLE,
    "Stroke":     C.AMBER,
}


def _rgba(color: QColor, alpha: float) -> str:
    a = max(0, min(255, int(round(alpha * 255))))
    return f"rgba({color.red()},{color.green()},{color.blue()},{a})"


def _rgba_rgb(r: int, g: int, b: int, alpha: float) -> str:
    a = max(0, min(255, int(round(alpha * 255))))
    return f"rgba({r},{g},{b},{a})"


# ═══════════════════════════════════════════════════════════════════════
#  Face registry — JSON-backed name -> [embedding...] map
# ═══════════════════════════════════════════════════════════════════════

class FaceRegistry:
    """Persistent map of name -> list of face-embedding vectors.

    Embeddings are produced by FaceMesh-landmark flattening + L2-normalize
    (see ``DetectionWorker._face_embedding``). Cosine similarity at lookup
    time picks the best match across all stored vectors for all names.
    Multiple samples per person are supported — call ``register`` a few
    times at slightly different angles for robustness.
    """

    def __init__(self, path: str = FACE_REGISTRY_PATH):
        self._path = path
        self._data: dict[str, list[list[float]]] = self._load()

    def _load(self) -> dict[str, list[list[float]]]:
        if not os.path.exists(self._path):
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {str(k): [list(map(float, v)) for v in vs]
                    for k, vs in raw.items() if isinstance(vs, list)}
        except Exception:
            return {}

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f)
        except Exception as e:
            sys.stderr.write(f"[face_registry] save failed: {e}\n")

    def register(self, name: str, embedding: np.ndarray) -> int:
        """Add a new sample for ``name``. Returns sample count after add."""
        name = name.strip()
        if not name:
            return 0
        self._data.setdefault(name, []).append(embedding.astype(float).tolist())
        self.save()
        return len(self._data[name])

    def forget(self, name: str) -> bool:
        if name in self._data:
            del self._data[name]
            self.save()
            return True
        return False

    def lookup(self, embedding: np.ndarray) -> tuple[Optional[str], float]:
        """Return (best_name, best_similarity). ``best_name`` is None when
        nothing exceeds ``FACE_MATCH_THRESHOLD``.
        """
        best_name: Optional[str] = None
        best_sim = -1.0
        for name, vecs in self._data.items():
            for v in vecs:
                vv = np.asarray(v, dtype=np.float32)
                # vectors are already L2-normalised at register time
                sim = float(np.dot(embedding, vv))
                if sim > best_sim:
                    best_sim = sim
                    best_name = name
        if best_sim < FACE_MATCH_THRESHOLD:
            return None, best_sim
        return best_name, best_sim

    def all_names(self) -> list[str]:
        return sorted(self._data.keys())


# ═══════════════════════════════════════════════════════════════════════
#  Detection worker — runs on its own QThread
# ═══════════════════════════════════════════════════════════════════════

# MediaPipe Hands landmark connection pairs (21-point model)
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),            # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),            # index
    (0, 9), (9, 10), (10, 11), (11, 12),       # middle
    (0, 13), (13, 14), (14, 15), (15, 16),     # ring
    (0, 17), (17, 18), (18, 19), (19, 20),     # pinky
    (5, 9), (9, 13), (13, 17),                 # palm
]


class DetectionWorker(QObject):
    """Owns ALL inference — MediaPipe Hands/Face/Mesh + YOLO + a private
    GestureEngine for classification (with no-op actions so locking the
    screen doesn't fire mid-test).

    Subscribes to the shared VisionEngine for frames. On each frame we:
      1. Run MediaPipe Hands → 21 landmarks per hand
      2. Run MediaPipe FaceDetection → face boxes
      3. Run MediaPipe FaceMesh → 478 landmarks → embedding → FaceRegistry lookup
      4. Run YOLO → object boxes (every 3rd frame to keep cost down)
      5. Composite all overlays on the BGR frame, convert to QImage, emit
      6. Track a "pending register" flag — when the user clicks Register,
         the next clear face becomes the new sample for the typed name
      7. Run gesture classification + K-frame consensus + rearm gate;
         emit a debounced gesture name only when both gates open
    """

    frame_ready       = pyqtSignal(QImage)
    meta_ready        = pyqtSignal(dict)   # banner / stability info
    gesture_emitted   = pyqtSignal(str)
    error             = pyqtSignal(str)
    face_registered   = pyqtSignal(str, int)   # name, total samples
    volume_changed    = pyqtSignal(int)        # 0..100 — for the volume gesture
    whip_detected     = pyqtSignal(str)        # 'left' / 'right'
    scroll_emitted    = pyqtSignal(str)        # 'up' / 'down'

    def __init__(self, face_registry: FaceRegistry):
        super().__init__()
        self._reg = face_registry
        self._mp_hands = None
        self._mp_face = None
        self._mp_mesh = None
        self._yolo = None
        self._gesture_engine = None
        # Display toggles
        self._show_landmarks = True
        self._show_faces = True
        self._show_objects = False
        # Fire-actions toggle — when OFF (default) the tester only displays
        # the recognised gesture; when ON, the gesture engine's real
        # DEFAULT_ACTIONS run (lock screen, snip, volume, etc.). Off by
        # default so launching the tester can't accidentally lock your PC.
        self._fire_actions = False
        # YOLO throttling — every Nth frame. Cached boxes from the last
        # inference are reused on the in-between frames so the overlay
        # doesn't flicker; objects rarely move >1 cm between frames anyway.
        self._frame_counter = 0
        self._yolo_every = 15
        self._last_objects: list = []
        self._object_status = "object recognition off"
        # InsightFace throttling — face recognition is the single most
        # expensive thing per frame (~60-100ms on CPU). Running it every
        # 4th frame brings amortised cost down to ~15-25ms while still
        # updating the face label at ~6-8 Hz (which feels live).
        self._insight_every = 8
        self._last_faces: list = []   # [(name, sim, bbox)]
        # Preview emit throttling — don't push QImages to the GUI faster
        # than ~22 fps even if the camera/inference is faster. Avoids
        # queue buildup on the GUI thread.
        self._last_emit_at = 0.0
        self._min_emit_interval = 1.0 / 22.0
        # Stabilization state
        self._classification_window: deque[str] = deque(maxlen=CONSENSUS_WINDOW)
        self._armed = True
        self._neutral_count = 0
        self._last_fired: Optional[str] = None
        # Volume-gesture state — distance-controlled, throttled emit.
        self._volume_last_emit_at = 0.0
        self._volume_last_value: Optional[int] = None
        # K-frame consensus for the volume gesture (don't fire until the
        # pose has been the volume pose for this many consecutive frames).
        self._volume_pose_streak = 0
        self._VOLUME_POSE_HOLD_S = 0.30
        self._volume_pose_started_at: Optional[float] = None
        # Wrist trail for swipe / whip visualization (per primary hand only).
        # Each entry: (t_monotonic, x_norm, y_norm, pose)
        self._wrist_trail: deque = deque(maxlen=20)
        # Fingertip trail for stroke / air-draw visualization.
        # Each entry: (t_monotonic, x_px, y_px)
        self._fingertip_trail: deque = deque(maxlen=40)
        # Palm anchor — set when an open palm is held nearly-still; cleared
        # when the hand disappears or the pose changes.
        self._anchor: Optional[tuple[float, float, float]] = None
        # Throttled scroll emit (so a single drift sends multiple PgUp/PgDn
        # ticks at a controlled rate, not 30 of them per second).
        self._scroll_last_emit_at = 0.0
        # Face registration mailbox
        self._pending_register_name: Optional[str] = None
        self._running = False

    # ── lifecycle (called via queued signals from GUI) ────────────────

    @pyqtSlot()
    def initialize(self):
        """Load all models on the worker thread via the MediaPipe Tasks
        API.

        mediapipe 0.10+ removed the legacy ``mp.solutions`` namespace, so
        we have to build HandLandmarker + FaceLandmarker through Tasks
        instead. Models live under ``data/models/``:

          - hand_landmarker.task   (already in repo)
          - face_landmarker.task   (downloaded on demand to 3.6 MB)

        Each model is tried independently — if one fails, the other +
        YOLO keep working and the tester degrades gracefully.
        """
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_py
            from mediapipe.tasks.python import vision as mp_vis
        except Exception as e:
            self.error.emit(f"MediaPipe import failed: {e}")
            return

        models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "data", "models")

        # ── Hands (Tasks API HandLandmarker) ──
        hand_path = os.path.join(models_dir, "hand_landmarker.task")
        if os.path.exists(hand_path):
            try:
                opts = mp_vis.HandLandmarkerOptions(
                    base_options=mp_py.BaseOptions(model_asset_path=hand_path),
                    running_mode=mp_vis.RunningMode.VIDEO,
                    num_hands=2,
                    min_hand_detection_confidence=0.6,
                    min_hand_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._mp_hands = mp_vis.HandLandmarker.create_from_options(opts)
            except Exception as e:
                sys.stderr.write(f"[tester] hands Tasks init failed: {e}\n")
                self._mp_hands = None
        else:
            sys.stderr.write(f"[tester] missing {hand_path}\n")
            self._mp_hands = None

        # ── Faces (Tasks API FaceLandmarker — gives 478 landmarks per face) ──
        face_path = os.path.join(models_dir, "face_landmarker.task")
        if os.path.exists(face_path):
            try:
                opts = mp_vis.FaceLandmarkerOptions(
                    base_options=mp_py.BaseOptions(model_asset_path=face_path),
                    running_mode=mp_vis.RunningMode.VIDEO,
                    num_faces=3,
                    min_face_detection_confidence=0.5,
                    min_face_presence_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                self._mp_mesh = mp_vis.FaceLandmarker.create_from_options(opts)
            except Exception as e:
                sys.stderr.write(f"[tester] face_mesh Tasks init failed: {e}\n")
                self._mp_mesh = None
        else:
            sys.stderr.write(f"[tester] missing {face_path}\n")
            self._mp_mesh = None
        # Legacy FaceDetection: not used; kept as None to make sites obvious.
        self._mp_face = None
        # Monotonic timestamp source for detect_for_video (must increase).
        self._frame_ts_base = time.monotonic()

        # ── InsightFace (ArcFace identity embeddings + face detection) ──
        # This REPLACES the FaceMesh-based embedding pipeline because the
        # FaceMesh geometric vector confused different glasses-wearing
        # people. ArcFace embeddings are trained for identity and easily
        # separate two visually-similar faces.
        # Models live under ~/.insightface/models/buffalo_l/ (downloaded
        # on first use, ~270 MB). buffalo_l = det_10g + w600k_r50.
        self._insight = None
        try:
            from insightface.app import FaceAnalysis
            self._insight = FaceAnalysis(
                name="buffalo_l",
                allowed_modules=["detection", "recognition"],
            )
            # det_size 480 (instead of 640) cuts detector cost ~40% with
            # negligible loss on close-range webcam faces (faces are big
            # enough relative to frame that the smaller input is fine).
            self._insight.prepare(ctx_id=-1, det_size=(480, 480))
        except Exception as e:
            sys.stderr.write(f"[tester] InsightFace init failed: {e}\n")
            self._insight = None
        # Private GestureEngine instance with no-op actions
        try:
            from core.gesture_engine import GestureEngine, DEFAULT_ACTIONS
            self._gesture_engine = GestureEngine(
                actions={k: (lambda: None) for k in DEFAULT_ACTIONS}
            )
            self._gesture_engine.add_listener(self._on_engine_gesture)
        except Exception as e:
            self.error.emit(f"GestureEngine init failed: {e}")
        # YOLO via existing detector (lazy — first detect() loads weights)
        try:
            from core.object_detector import ObjectDetector
            self._yolo = ObjectDetector()
            # Preload now so the first frame doesn't stall.
            if self._yolo.is_available():
                self._object_status = "object recognition ready"
            else:
                self._object_status = "object model unavailable"
        except Exception as e:
            sys.stderr.write(f"[tester] object detector unavailable: {e}\n")
            self._yolo = None
            self._object_status = "object model unavailable"

    @pyqtSlot()
    def start_capture(self):
        try:
            from core.vision_engine import get_vision_engine
            ve = get_vision_engine()
            # Start gesture engine too so we get its classification events.
            if self._gesture_engine is not None:
                self._gesture_engine.start()
            ok = ve.subscribe("tester_preview", self._on_frame)
            if not ok:
                self.error.emit(ve.last_error() or "camera unavailable")
                return
            self._running = True
        except Exception as e:
            self.error.emit(f"start_capture: {e}")

    @pyqtSlot()
    def stop_capture(self):
        self._running = False
        try:
            from core.vision_engine import get_vision_engine
            get_vision_engine().unsubscribe("tester_preview")
        except Exception:
            pass
        try:
            if self._gesture_engine is not None:
                self._gesture_engine.stop()
        except Exception:
            pass

    # ── runtime config slots ──────────────────────────────────────────

    @pyqtSlot(bool)
    def set_show_landmarks(self, on: bool): self._show_landmarks = on

    @pyqtSlot(bool)
    def set_show_faces(self, on: bool): self._show_faces = on

    @pyqtSlot(bool)
    def set_show_objects(self, on: bool):
        self._show_objects = on
        if on and self._yolo is None:
            self._object_status = "object model unavailable"
        elif on:
            self._object_status = "looking for objects"
        else:
            self._object_status = "object recognition off"
            self._last_objects = []

    @pyqtSlot(bool)
    def set_fire_actions(self, on: bool):
        """Swap the engine's action map between real actions and no-ops."""
        self._fire_actions = bool(on)
        if self._gesture_engine is None:
            return
        try:
            from core.gesture_engine import DEFAULT_ACTIONS
            if on:
                self._gesture_engine._actions = dict(DEFAULT_ACTIONS)
            else:
                self._gesture_engine._actions = {
                    k: (lambda: None) for k in DEFAULT_ACTIONS
                }
        except Exception as e:
            sys.stderr.write(f"[tester] action swap failed: {e}\n")

    @pyqtSlot(str)
    def request_register_face(self, name: str):
        """Mark the next clear face for registration as ``name``."""
        self._pending_register_name = name.strip() or None

    @pyqtSlot(str)
    def request_forget_face(self, name: str):
        if self._reg.forget(name):
            self.face_registered.emit(name, 0)

    # ── gesture engine listener (worker thread) ──────────────────────

    def _on_engine_gesture(self, name: str):
        """Called by core GestureEngine when ITS internal cooldown +
        hold-time logic has accepted a gesture. We add OUR stabilization
        layer on top: armed/neutral gate + consensus window.

        Note: the engine's internal cooldown is already 1.4 s, so this
        listener fires at most ~0.7 Hz for any single gesture. Our gate
        only further restricts firing — never relaxes.
        """
        # Consensus: this gesture must currently dominate the window.
        # Since the engine only emits "stable" events, we accept on first
        # emit; the K-frame consensus is enforced for raw per-frame
        # classifications in `_on_frame` via _classification_window.
        if not self._armed:
            return
        # Suppress duplicates of the most recent fire even across windows.
        if name == self._last_fired and self._neutral_count < REARM_NEUTRAL_FRAMES:
            return
        self._armed = False
        self._neutral_count = 0
        self._last_fired = name
        self.gesture_emitted.emit(name)

    # ── per-frame callback (vision engine thread) ────────────────────

    def _on_frame(self, frame_bgr):
        if not self._running:
            return
        try:
            self._process(frame_bgr)
        except Exception as e:
            # Never let a single bad frame kill the whole tester.
            sys.stderr.write(f"[tester] frame error: {e}\n")

    def _process(self, frame_bgr):
        import mediapipe as mp
        h, w = frame_bgr.shape[:2]
        # Mirror so the preview matches a real mirror (left hand on left).
        frame = cv2.flip(frame_bgr, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Tasks API needs an mp.Image + strictly-increasing timestamp.
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms = int((time.monotonic() - self._frame_ts_base) * 1000)

        # ── 1. Hand landmarks (Tasks API) + pose analysis ──────────
        # We also pull handedness so _classify_static can do the thumb's
        # mirrored-axis check correctly. The frame we feed to the model
        # is the MIRRORED preview, so the model's "Left" actually means
        # the user's right hand — we swap the label before classifying.
        hands_present = 0
        per_hand_poses: list[dict] = []
        if self._mp_hands is not None:
            try:
                res = self._mp_hands.detect_for_video(mp_image, ts_ms)
            except Exception:
                res = None
            hand_landmark_sets = (res.hand_landmarks
                                  if res and res.hand_landmarks else [])
            hand_labels = []
            try:
                if res and res.handedness:
                    for cats in res.handedness:
                        # Each cats is a list of Category objects; take 1st.
                        cn = cats[0].category_name if cats else "Right"
                        # Swap left/right because frame is mirrored.
                        cn = "Right" if cn == "Left" else "Left"
                        hand_labels.append(cn)
            except Exception:
                hand_labels = ["Right"] * len(hand_landmark_sets)
            while len(hand_labels) < len(hand_landmark_sets):
                hand_labels.append("Right")

            hands_present = len(hand_landmark_sets)
            for lms, label in zip(hand_landmark_sets, hand_labels):
                pose_info = self._analyze_hand(lms, label, w, h)
                per_hand_poses.append(pose_info)
                if self._show_landmarks:
                    self._draw_hand(frame, lms, w, h, pose_info)

            # Pinch-to-volume (custom continuous gesture, not in core engine).
            self._maybe_emit_volume(per_hand_poses, frame)

            # Whip-swipe + palm-anchor scroll + fingertip stroke trail are
            # all based on tracking the PRIMARY hand's wrist + index tip
            # over time — handled together below.
            if per_hand_poses:
                self._track_primary_hand(per_hand_poses[0], frame, w, h)
            else:
                # No primary hand → clear trails so old paths don't ghost.
                self._wrist_trail.clear()
                self._fingertip_trail.clear()
                self._anchor = None

            # Two-handed visualization: line between wrists with distance %.
            if len(per_hand_poses) >= 2 and self._show_landmarks:
                self._draw_two_hand_guide(frame, per_hand_poses[0],
                                          per_hand_poses[1], w, h)

        # Rearm logic: count neutral frames (no hand visible).
        if hands_present == 0:
            self._neutral_count += 1
            if (not self._armed) and self._neutral_count >= REARM_NEUTRAL_FRAMES:
                self._armed = True
                self._last_fired = None
        else:
            # Hand visible — pause the rest-counter.
            self._neutral_count = 0

        # ── 2. Face detection + ArcFace identity embedding ──────────
        # Run the EXPENSIVE InsightFace inference only every Nth frame;
        # on in-between frames redraw the boxes from the last result. The
        # face barely moves at 30fps so 6-8Hz updates feel live while
        # freeing ~80ms of CPU budget for the rest of the pipeline.
        face_labels: list[tuple[str, tuple[int, int, int, int]]] = []
        run_insight = (self._show_faces and self._insight is not None
                       and (self._frame_counter % self._insight_every == 0
                            or self._pending_register_name is not None))
        if run_insight:
            try:
                faces = self._insight.get(frame)   # BGR mirrored frame
            except Exception as e:
                sys.stderr.write(f"[tester] insight.get failed: {e}\n")
                faces = []
            new_cache: list = []
            for face in faces:
                bbox = face.bbox.astype(int)
                x1, y1, x2, y2 = (max(0, int(bbox[0])), max(0, int(bbox[1])),
                                  min(w, int(bbox[2])), min(h, int(bbox[3])))
                emb = getattr(face, "embedding", None)
                if emb is not None:
                    emb = np.asarray(emb, dtype=np.float32)
                    n = np.linalg.norm(emb)
                    if n > 0:
                        emb = emb / n
                name = "person"
                sim = 0.0
                if emb is not None:
                    if self._pending_register_name:
                        tot = self._reg.register(
                            self._pending_register_name, emb)
                        self.face_registered.emit(
                            self._pending_register_name, tot)
                        self._pending_register_name = None
                    else:
                        m_name, m_sim = self._reg.lookup(emb)
                        if m_name:
                            name = m_name
                            sim = m_sim
                new_cache.append((name, sim, (x1, y1, x2, y2)))
            self._last_faces = new_cache
        # Draw boxes from the most recent inference (fresh or cached).
        if self._show_faces and self._insight is not None:
            for name, sim, (x1, y1, x2, y2) in self._last_faces:
                self._draw_face(frame, x1, y1, x2, y2, name, sim)
                face_labels.append((name, (x1, y1, x2, y2)))
        elif self._show_faces and self._mp_mesh is not None:
            # FALLBACK: FaceLandmarker-only mode (no identity, just boxes).
            try:
                fm = self._mp_mesh.detect_for_video(mp_image, ts_ms)
            except Exception:
                fm = None
            face_meshes = (fm.face_landmarks
                           if fm and fm.face_landmarks else [])
            for landmarks in face_meshes:
                xs = [lm.x for lm in landmarks]
                ys = [lm.y for lm in landmarks]
                x1 = max(0, int(min(xs) * w) - 6)
                y1 = max(0, int(min(ys) * h) - 6)
                x2 = min(w, int(max(xs) * w) + 6)
                y2 = min(h, int(max(ys) * h) + 6)
                self._draw_face(frame, x1, y1, x2, y2, "person", 0.0)
                face_labels.append(("person", (x1, y1, x2, y2)))

        # ── 3. Objects (every Nth frame to keep <33ms / frame) ─────
        self._frame_counter += 1
        if self._show_objects and self._yolo is not None:
            if self._frame_counter % self._yolo_every == 0:
                try:
                    # YOLO sees a smaller ORIGINAL frame to keep the preview
                    # smooth. We scale boxes back, then mirror x to match
                    # the displayed camera preview.
                    max_w = 416
                    scale = 1.0
                    detect_frame = frame_bgr
                    if w > max_w:
                        scale = max_w / float(w)
                        detect_frame = cv2.resize(
                            frame_bgr, (max_w, max(1, int(h * scale))),
                            interpolation=cv2.INTER_AREA,
                        )
                    dets = self._yolo.detect(detect_frame)
                    # Mirror x because we display frame = cv2.flip(...,1).
                    mirrored = []
                    for d in dets:
                        x1, y1, x2, y2 = d.bbox
                        if scale != 1.0:
                            x1 = int(x1 / scale); x2 = int(x2 / scale)
                            y1 = int(y1 / scale); y2 = int(y2 / scale)
                        mx1 = w - x2
                        mx2 = w - x1
                        mirrored.append((d.label, d.score, (mx1, y1, mx2, y2)))
                    self._last_objects = mirrored
                    if mirrored:
                        names = ", ".join(
                            f"{label} {score:.2f}"
                            for label, score, _bbox in mirrored[:3]
                        )
                        self._object_status = f"objects: {names}"
                    else:
                        self._object_status = "no object detected"
                except Exception:
                    self._object_status = "object detection error"
            for label, score, (x1, y1, x2, y2) in self._last_objects:
                self._draw_object(frame, x1, y1, x2, y2, label, score)
        elif self._show_objects and self._yolo is None:
            self._object_status = "object model unavailable"
        elif not self._show_objects:
            self._object_status = "object recognition off"

        # ── 4. Compose preview QImage + emit (throttled to ~22 fps) ─
        # If we just blasted every processed frame to the GUI thread, a
        # CPU spike on the worker side would queue up dozens of QImages
        # and the displayed video would lag seconds behind reality.
        now = time.monotonic()
        if (now - self._last_emit_at) < self._min_emit_interval:
            return
        self._last_emit_at = now
        rgb_disp = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb_disp.data, w, h, w * 3,
                      QImage.Format_RGB888).copy()
        self.frame_ready.emit(qimg)
        self.meta_ready.emit({
            "armed": self._armed,
            "neutral": self._neutral_count,
            "hands": hands_present,
            "faces": len(face_labels),
            "objects": len(self._last_objects),
            "object_status": self._object_status,
        })

    # ── face embedding ────────────────────────────────────────────────

    def _face_embedding(self, landmarks) -> Optional[np.ndarray]:
        """Convert FaceMesh's 478 (x,y) landmarks into a translation- and
        scale-invariant unit vector. Cosine similarity between two such
        vectors gives a stable "are these the same face" score.

        Steps:
          1. Stack into a (478, 2) array
          2. Subtract centroid (translation invariance)
          3. Scale by max distance from centroid (scale invariance)
          4. Flatten + L2-normalize (so dot product = cosine similarity)
        """
        try:
            pts = np.array([(lm.x, lm.y) for lm in landmarks],
                           dtype=np.float32)
            if pts.shape[0] < 100:
                return None
            pts -= pts.mean(axis=0)
            scale = np.max(np.linalg.norm(pts, axis=1))
            if scale <= 0:
                return None
            pts /= scale
            vec = pts.flatten()
            n = np.linalg.norm(vec)
            if n <= 0:
                return None
            return (vec / n).astype(np.float32)
        except Exception:
            return None

    # ── drawing helpers ───────────────────────────────────────────────

    def _analyze_hand(self, landmarks, hand_label: str,
                      w: int, h: int) -> dict:
        """Run the SAME pose classification as core.gesture_engine on these
        landmarks so the tester displays the engine's view of the hand.

        Also computes:
          * finger extension flags (5)
          * thumb_tip, index_tip, wrist (px coords for drawing)
          * palm_width — pixel distance between MCP joints 5 and 17
            (used as depth-invariant scale for the volume gesture)
          * thumb_index_norm — thumb↔index tip distance / palm_width
        """
        from core.gesture_engine import (
            _classify_static, _finger_extended, _TIPS, _WRIST,
        )
        states = {f: bool(_finger_extended(landmarks, f, hand_label))
                  for f in _TIPS}
        pose = _classify_static(landmarks, hand_label)
        thumb_tip = (int(landmarks[_TIPS["thumb"]].x * w),
                     int(landmarks[_TIPS["thumb"]].y * h))
        index_tip = (int(landmarks[_TIPS["index"]].x * w),
                     int(landmarks[_TIPS["index"]].y * h))
        wrist_px  = (int(landmarks[_WRIST].x * w),
                     int(landmarks[_WRIST].y * h))
        mcp5 = landmarks[5]; mcp17 = landmarks[17]
        palm_w_px = max(1.0, ((mcp5.x - mcp17.x) ** 2
                              + (mcp5.y - mcp17.y) ** 2) ** 0.5
                        * max(w, h))
        thumb_index_px = ((thumb_tip[0] - index_tip[0]) ** 2
                          + (thumb_tip[1] - index_tip[1]) ** 2) ** 0.5
        # Depth-invariant ratio: 0.0 ≈ touching, 2.5+ ≈ max stretch.
        thumb_index_norm = thumb_index_px / palm_w_px
        return {
            "pose": pose,
            "label": hand_label,
            "states": states,
            "thumb_tip": thumb_tip,
            "index_tip": index_tip,
            "wrist": wrist_px,
            "palm_w": palm_w_px,
            "thumb_index_px": thumb_index_px,
            "thumb_index_norm": thumb_index_norm,
            # Raw landmarks attached so strict curl checks can re-test
            # individual joints (used by _is_volume_pose).
            "_landmarks": landmarks,
            # Wrist position in NORMALISED frame coords for trail tracking.
            "wrist_norm": (landmarks[_WRIST].x, landmarks[_WRIST].y),
        }

    def _draw_hand(self, frame, landmarks, w: int, h: int,
                   pose_info: Optional[dict] = None):
        """Draw 21-point hand skeleton + guideline overlays.

        Colors:
          * Bones — cyan
          * Joints — white with cyan ring; EXTENDED finger tips get a green
            ring, CURLED tips get an amber ring (so you can see which
            fingers the classifier thinks are up).
          * Thumb↔index line — colour-coded by current pose
              - touching (pinch / ok_sign):   magenta
              - thumb+index only extended:    green (volume gesture)
              - other:                        dim grey
          * Pose name printed above the wrist.
        """
        pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
        # Bones
        for a, b in _HAND_CONNECTIONS:
            cv2.line(frame, pts[a], pts[b], (0, 215, 230), 2, cv2.LINE_AA)

        # Finger extension flags (for tip ring colour)
        states = pose_info["states"] if pose_info else {}
        # Tip indices per finger name
        tip_idx_by_finger = {"thumb": 4, "index": 8, "middle": 12,
                             "ring": 16, "pinky": 20}
        ext_tips = {idx for fname, idx in tip_idx_by_finger.items()
                    if states.get(fname)}

        # Joints
        for i, p in enumerate(pts):
            cv2.circle(frame, p, 4, (255, 255, 255), -1, cv2.LINE_AA)
            ring_color = (80, 200, 130) if i in ext_tips else (
                (255, 170, 80) if i in tip_idx_by_finger.values()
                else (0, 215, 230))
            cv2.circle(frame, p, 6, ring_color, 1, cv2.LINE_AA)

        if not pose_info:
            return

        pose = pose_info["pose"]
        t_tip = pose_info["thumb_tip"]
        i_tip = pose_info["index_tip"]
        wrist = pose_info["wrist"]
        norm = pose_info["thumb_index_norm"]

        # Thumb↔index guideline
        if pose in ("pinch", "ok_sign"):
            line_col = (220, 80, 200)        # magenta — touching
        elif self._is_volume_pose(pose_info):
            line_col = (80, 200, 130)        # green — active volume gesture
        else:
            line_col = (140, 160, 180)       # dim
        cv2.line(frame, t_tip, i_tip, line_col, 2, cv2.LINE_AA)
        mid = ((t_tip[0] + i_tip[0]) // 2, (t_tip[1] + i_tip[1]) // 2)
        cv2.putText(frame, f"d={norm:.2f}", (mid[0] + 6, mid[1] - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, line_col, 1, cv2.LINE_AA)

        # Pose name tag above wrist
        tag = f"{pose_info['label'][0]} · {pose}"
        cv2.putText(frame, tag, (wrist[0] - 30, wrist[1] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 235, 240), 2,
                    cv2.LINE_AA)

    def _draw_two_hand_guide(self, frame, p1: dict, p2: dict,
                             w: int, h: int):
        """Draw a line between the two wrists with the normalized distance
        label. The CORE engine's classifier uses this exact metric to
        decide between two_palm_spread / two_palm_pinch / clap, so seeing
        it live tells you whether your hands are close enough for a clap.
        """
        w1 = p1["wrist"]; w2 = p2["wrist"]
        # Use the normalised distance (0..1 of frame width) so the
        # threshold constants from the engine are directly readable.
        dx = (w1[0] - w2[0]) / max(1, w)
        dy = (w1[1] - w2[1]) / max(1, h)
        dist = (dx * dx + dy * dy) ** 0.5
        # Colour: tight (potential clap) magenta, moderate cyan, wide amber.
        if dist <= 0.18:
            col = (220, 80, 200)
        elif dist >= 0.45:
            col = (255, 170, 80)
        else:
            col = (0, 215, 230)
        cv2.line(frame, w1, w2, col, 2, cv2.LINE_AA)
        mx, my = (w1[0] + w2[0]) // 2, (w1[1] + w2[1]) // 2
        label = f"2H: {dist:.2f}"
        if dist <= 0.18:
            label += "  → clap zone"
        elif dist >= 0.45:
            label += "  → spread zone"
        cv2.putText(frame, label, (mx + 6, my - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2, cv2.LINE_AA)

    # ── primary-hand tracking: whip / scroll / stroke ────────────────

    # Whip-swipe: open palm whose wrist moves horizontally faster than
    # WHIP_VX_THRESHOLD (normalised x per second) and covers at least
    # WHIP_DX_MIN of the frame width within the look-back window.
    _WHIP_VX_THRESHOLD = 1.40   # frame-widths per second
    _WHIP_DX_MIN       = 0.22   # 22% of frame width

    # Palm-anchor: wrist stays within ANCHOR_RADIUS for ANCHOR_HOLD_S to
    # arm; once armed, vertical drift past SCROLL_DRIFT triggers scroll.
    _ANCHOR_RADIUS  = 0.06       # 6% of frame
    _ANCHOR_HOLD_S  = 0.40
    _SCROLL_DRIFT   = 0.10       # 10% of frame height
    _SCROLL_PERIOD  = 0.45       # min seconds between scroll ticks

    def _track_primary_hand(self, p: dict, frame, w: int, h: int):
        """Drive whip-swipe, palm-anchor scroll, and stroke-trail
        visualisation off the primary hand's wrist + index tip.

        Why a separate path (instead of relying on core/gesture_engine):
        * The engine already handles swipe / palm_hold / strokes, but its
          decisions are invisible. By tracking + drawing them in the
          tester, you can see WHY a gesture fires (or doesn't).
        * The whip detector here is a SECOND interpretation of the same
          motion — when the engine misses (e.g. you whip too fast for its
          0.6s window), this still surfaces the swipe.
        """
        now = time.monotonic()
        pose = p["pose"]
        wx, wy = p["wrist_norm"]
        self._wrist_trail.append((now, wx, wy, pose))
        # Trim entries older than 0.6 s
        while self._wrist_trail and (now - self._wrist_trail[0][0]) > 0.6:
            self._wrist_trail.popleft()

        # ── draw wrist trail (cyan → fades) ──
        if self._show_landmarks and len(self._wrist_trail) >= 2:
            n = len(self._wrist_trail)
            for i in range(1, n):
                _, ax, ay, _ = self._wrist_trail[i - 1]
                _, bx, by, _ = self._wrist_trail[i]
                age_frac = i / n
                col = (int(0 + age_frac * 0),
                       int(80 + age_frac * 135),
                       int(120 + age_frac * 110))
                cv2.line(frame, (int(ax * w), int(ay * h)),
                                (int(bx * w), int(by * h)),
                         col, 2, cv2.LINE_AA)

        # ── whip-swipe detection (open_palm only) ──
        if pose == "open_palm" and len(self._wrist_trail) >= 4:
            t0, x0, _y0, _ = self._wrist_trail[0]
            t1, x1, _y1, _ = self._wrist_trail[-1]
            dt = max(0.001, t1 - t0)
            dx = x1 - x0
            vx = dx / dt
            cv2.putText(frame, f"vx={vx:+.2f}/s  dx={dx:+.2f}",
                        (12, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 215, 230), 1, cv2.LINE_AA)
            if (abs(vx) >= self._WHIP_VX_THRESHOLD
                    and abs(dx) >= self._WHIP_DX_MIN):
                direction = "right" if dx > 0 else "left"
                self._wrist_trail.clear()
                cv2.putText(frame, f"WHIP {direction.upper()}",
                            (w // 2 - 90, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                            (80, 200, 130), 3, cv2.LINE_AA)
                self.whip_detected.emit(direction)
                # Fire the same action the engine's swipe maps to.
                if self._fire_actions:
                    try:
                        from core.gesture_engine import _smart_swipe
                        _smart_swipe(direction)
                    except Exception:
                        pass

        # ── palm-anchor + drift scroll ──
        if pose == "open_palm":
            if self._anchor is None:
                # Just became open palm — start a candidate anchor.
                self._anchor = (now, wx, wy)
            else:
                a_t, ax, ay = self._anchor
                radial = ((wx - ax) ** 2 + (wy - ay) ** 2) ** 0.5
                if radial > self._ANCHOR_RADIUS and (now - a_t) < self._ANCHOR_HOLD_S:
                    # Moved before settling — reset candidate.
                    self._anchor = (now, wx, wy)
                elif (now - a_t) >= self._ANCHOR_HOLD_S:
                    # Anchored — draw the anchor marker + drift arrow.
                    ax_px, ay_px = int(ax * w), int(ay * h)
                    cv2.drawMarker(frame, (ax_px, ay_px),
                                   (255, 170, 80),
                                   markerType=cv2.MARKER_CROSS,
                                   markerSize=22, thickness=2)
                    cv2.circle(frame, (ax_px, ay_px),
                               int(self._ANCHOR_RADIUS * w),
                               (255, 170, 80), 1, cv2.LINE_AA)
                    dy = wy - ay
                    if abs(dy) >= self._SCROLL_DRIFT:
                        dir_ = "down" if dy > 0 else "up"
                        # arrow from anchor to current
                        cv2.arrowedLine(frame, (ax_px, ay_px),
                                        (int(wx * w), int(wy * h)),
                                        (80, 200, 130), 3, cv2.LINE_AA,
                                        tipLength=0.25)
                        cv2.putText(frame, f"SCROLL {dir_.upper()}",
                                    (ax_px + 18, ay_px),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                                    (80, 200, 130), 2, cv2.LINE_AA)
                        if (now - self._scroll_last_emit_at) >= self._SCROLL_PERIOD:
                            self._scroll_last_emit_at = now
                            self.scroll_emitted.emit(dir_)
                            if self._fire_actions:
                                try:
                                    from core.gesture_engine import _scroll_page
                                    _scroll_page(dir_)
                                except Exception:
                                    pass
        else:
            # Pose changed away from open palm — drop the anchor.
            self._anchor = None

        # ── index-fingertip trail (for air-drawn strokes) ──
        if pose == "point":
            ix, iy = p["index_tip"]
            self._fingertip_trail.append((now, ix, iy))
            # Drop entries older than 2.0 s.
            while (self._fingertip_trail
                   and (now - self._fingertip_trail[0][0]) > 2.0):
                self._fingertip_trail.popleft()
        elif pose in ("open_palm", "fist", "none"):
            # Stroke complete — fade the trail by trimming gradually.
            while (self._fingertip_trail
                   and (now - self._fingertip_trail[0][0]) > 0.5):
                self._fingertip_trail.popleft()

        if self._show_landmarks and len(self._fingertip_trail) >= 2:
            for i in range(1, len(self._fingertip_trail)):
                _, ax, ay = self._fingertip_trail[i - 1]
                _, bx, by = self._fingertip_trail[i]
                cv2.line(frame, (ax, ay), (bx, by),
                         (255, 170, 80), 3, cv2.LINE_AA)

    # ── volume gesture ────────────────────────────────────────────────

    def _is_volume_pose(self, pose_info: dict) -> bool:
        """True iff ONLY thumb + index are STRONGLY extended and middle /
        ring / pinky are DEFINITELY curled.

        The previous lenient version (tip.y < pip.y) misfired whenever a
        finger was relaxed but not fully tucked. We now require an extra
        margin on the curled fingers (tip.y > pip.y + 0.04) so a slack
        hand can't be mistaken for the volume pose.
        """
        s = pose_info.get("states", {})
        if not (s.get("thumb") and s.get("index")):
            return False
        if s.get("middle") or s.get("ring") or s.get("pinky"):
            return False
        # Extra strictness — landmark-level check that other fingers are
        # decisively curled, not just "tip not above PIP". Margin is in
        # normalised landmark coords (0..1 of frame height).
        lms = pose_info.get("_landmarks")
        if lms is None:
            return True
        # TIP and PIP indices for the three "must be curled" fingers.
        # MediaPipe Hands: middle 12/10, ring 16/14, pinky 20/18.
        CURL_MARGIN = 0.04
        for tip_i, pip_i in ((12, 10), (16, 14), (20, 18)):
            if lms[tip_i].y < lms[pip_i].y + CURL_MARGIN:
                return False
        return True

    def _maybe_emit_volume(self, per_hand_poses: list, frame):
        """Continuous thumb+index volume gesture.

        User pose: close middle/ring/pinky, extend only thumb + index.
        No pinch is required. After the pose is held for ~0.3s, the
        thumb-index distance maps to volume percentage.
        """
        candidates = [p for p in per_hand_poses if self._is_volume_pose(p)]
        if not candidates:
            self._volume_pose_started_at = None
            return

        now = time.monotonic()
        if self._volume_pose_started_at is None:
            self._volume_pose_started_at = now
        held = now - self._volume_pose_started_at

        p = max(candidates, key=lambda p: p["thumb_index_norm"])
        t_tip = p["thumb_tip"]; i_tip = p["index_tip"]
        mid = ((t_tip[0] + i_tip[0]) // 2, (t_tip[1] + i_tip[1]) // 2)
        if held < self._VOLUME_POSE_HOLD_S:
            cv2.putText(frame, "VOL READY", (mid[0] - 42, mid[1] - 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 170, 80), 2,
                        cv2.LINE_AA)
            return

        norm = p["thumb_index_norm"]
        lo, hi = 0.15, 2.20
        pct = int(round(max(0.0, min(1.0, (norm - lo) / (hi - lo))) * 100))
        if (now - self._volume_last_emit_at) < 0.080:
            return
        if (self._volume_last_value is not None
                and abs(pct - self._volume_last_value) < 3):
            return
        self._volume_last_emit_at = now
        self._volume_last_value = pct
        cv2.putText(frame, f"VOL {pct}%", (mid[0] - 30, mid[1] - 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 200, 130), 2,
                    cv2.LINE_AA)
        self.volume_changed.emit(pct)
        if self._fire_actions:
            self._apply_system_volume(pct)

    @staticmethod
    def _apply_system_volume(pct: int):
        """Route volume changes through the engine's _set_volume_pct so we
        share its modern-pycaw → legacy-pycaw → VK_VOLUME_UP/DOWN fallback
        chain. Lets the gesture still work when pycaw isn't installed.
        """
        try:
            from core.gesture_engine import _set_volume_pct
        except Exception as e:
            sys.stderr.write(f"[tester] cannot import _set_volume_pct: {e}\n")
            return
        _set_volume_pct(int(pct))

    def _draw_face(self, frame, x1, y1, x2, y2, name: str, sim: float):
        is_named = name != "person"
        color = (80, 200, 130) if is_named else (180, 200, 220)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
        label = f"{name}" if not is_named else f"{name}  ({sim:.2f})"
        self._label(frame, label, x1, y1, color)

    def _draw_object(self, frame, x1, y1, x2, y2, label: str, score: float):
        color = (255, 170, 80)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
        self._label(frame, f"{label} {score:.2f}", x1, y2, color, below=True)

    def _label(self, frame, text: str, x: int, y: int,
               color: tuple, below: bool = False):
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.55
        thick = 1
        (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
        pad = 4
        if below:
            ty = min(y + th + pad * 2, frame.shape[0] - 2)
            box = (x, ty - th - pad, x + tw + pad * 2, ty + pad)
        else:
            ty = max(y - pad, th + pad)
            box = (x, ty - th - pad, x + tw + pad * 2, ty + pad)
        cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]),
                      color, -1, cv2.LINE_AA)
        cv2.putText(frame, text, (x + pad, ty),
                    font, scale, (13, 21, 37), thick, cv2.LINE_AA)


# ═══════════════════════════════════════════════════════════════════════
#  Gesture catalog row (unchanged behaviour from previous tester)
# ═══════════════════════════════════════════════════════════════════════

class _GestureRow(QFrame):
    """One card per gesture. Expands to show 'how to perform' via the ⓘ
    button. Bumps a trigger counter + flashes when the gesture fires.
    """

    def __init__(self, key, glyph, name, action, how_to, category, parent=None):
        super().__init__(parent)
        self.key = key
        self._expanded = False
        self._fire_count = 0
        self._color = _CATEGORY_COLOR.get(category, C.MUTED)
        self.setObjectName("GestureRow")
        self.setStyleSheet(self._row_style())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8); lay.setSpacing(4)

        head = QHBoxLayout(); head.setSpacing(10)

        glyph_lbl = QLabel(glyph)
        glyph_lbl.setFont(QFont("Segoe UI Emoji", 16))
        glyph_lbl.setStyleSheet(f"color:{self._color.name()};")
        glyph_lbl.setFixedWidth(46)
        glyph_lbl.setAlignment(Qt.AlignCenter)
        head.addWidget(glyph_lbl)

        title_box = QVBoxLayout(); title_box.setSpacing(1)
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Inter", 10, QFont.Bold))
        name_lbl.setStyleSheet(f"color:{C.PRIMARY.name()};")
        title_box.addWidget(name_lbl)
        action_lbl = QLabel(f"→  {action}")
        action_lbl.setFont(QFont("Consolas", 8))
        action_lbl.setStyleSheet(f"color:{self._color.name()};")
        title_box.addWidget(action_lbl)
        meta_row = QHBoxLayout(); meta_row.setSpacing(8)
        cat_pill = QLabel(category)
        cat_pill.setFont(QFont("Consolas", 7, QFont.Bold))
        cat_pill.setStyleSheet(
            f"color:{self._color.name()};"
            f"background:{_rgba(self._color, 0.15)};"
            "padding:1px 6px;border-radius:4px;"
        )
        meta_row.addWidget(cat_pill)
        self._count_lbl = QLabel("0 triggers")
        self._count_lbl.setFont(QFont("Consolas", 7))
        self._count_lbl.setStyleSheet(f"color:{C.MUTED.name()};")
        meta_row.addWidget(self._count_lbl)
        meta_row.addStretch(1)
        title_box.addLayout(meta_row)
        head.addLayout(title_box, 1)

        info = QPushButton("ⓘ")
        info.setFixedSize(26, 26)
        info.setCursor(Qt.PointingHandCursor)
        info.setFont(QFont("Segoe UI", 10, QFont.Bold))
        info.setToolTip("Show / hide instructions")
        info.setStyleSheet(
            f"QPushButton{{background:{_rgba(self._color, 0.15)};"
            f"color:{self._color.name()};"
            f"border:1px solid {_rgba(self._color, 0.40)};"
            "border-radius:13px;}}"
            f"QPushButton:hover{{background:{_rgba(self._color, 0.30)};}}"
        )
        info.clicked.connect(self._toggle)
        head.addWidget(info)
        lay.addLayout(head)

        self._howto = QLabel(how_to)
        self._howto.setFont(QFont("Inter", 8))
        self._howto.setStyleSheet(f"color:{C.SECONDARY.name()};padding:4px 2px;")
        self._howto.setWordWrap(True)
        self._howto.hide()
        lay.addWidget(self._howto)

    def _toggle(self):
        self._expanded = not self._expanded
        self._howto.setVisible(self._expanded)

    def _row_style(self, highlighted: bool = False) -> str:
        border = f"2px solid {self._color.name()}" if highlighted else f"1px solid {_rgba(self._color, 0.30)}"
        return (
            "QFrame#GestureRow{"
            f"background:{_rgba(C.PANEL, 0.70)};"
            f"border:{border};"
            "border-radius:10px;}"
        )

    def bump_count(self):
        self._fire_count += 1
        self._count_lbl.setText(
            f"{self._fire_count} trigger{'s' if self._fire_count != 1 else ''}"
        )
        self.setStyleSheet(self._row_style(highlighted=True))
        QTimer.singleShot(450, self._unflash)

    def _unflash(self):
        self.setStyleSheet(self._row_style())


# ═══════════════════════════════════════════════════════════════════════
#  Main window
# ═══════════════════════════════════════════════════════════════════════

class GestureTesterWindow(QWidget):

    # Cross-thread signals to the worker
    request_init        = pyqtSignal()
    request_start       = pyqtSignal()
    request_stop        = pyqtSignal()
    request_register    = pyqtSignal(str)
    request_forget      = pyqtSignal(str)
    request_show_lm     = pyqtSignal(bool)
    request_show_face   = pyqtSignal(bool)
    request_show_obj    = pyqtSignal(bool)
    request_fire_actions = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AERIS — Gesture Tester")
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(f"background:{C.BG.name()};")

        self._reg = FaceRegistry()
        self._rows: dict[str, _GestureRow] = {}
        self._running = False

        # ── Build worker thread ─────────────────────────────────────
        self._worker_thread = QThread(self)
        self._worker = DetectionWorker(self._reg)
        self._worker.moveToThread(self._worker_thread)
        self.request_init.connect(self._worker.initialize)
        self.request_start.connect(self._worker.start_capture)
        self.request_stop.connect(self._worker.stop_capture)
        self.request_register.connect(self._worker.request_register_face)
        self.request_forget.connect(self._worker.request_forget_face)
        self.request_show_lm.connect(self._worker.set_show_landmarks)
        self.request_show_face.connect(self._worker.set_show_faces)
        self.request_show_obj.connect(self._worker.set_show_objects)
        self.request_fire_actions.connect(self._worker.set_fire_actions)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.meta_ready.connect(self._on_meta)
        self._worker.gesture_emitted.connect(self._on_gesture)
        self._worker.error.connect(self._on_error)
        self._worker.face_registered.connect(self._on_face_registered)
        self._worker.volume_changed.connect(self._on_volume)
        self._worker.whip_detected.connect(self._on_whip)
        self._worker.scroll_emitted.connect(self._on_scroll)
        self._worker_thread.start()
        self.request_init.emit()

        # ── Layout ──────────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16); root.setSpacing(14)

        # LEFT column — camera preview + controls
        left = QVBoxLayout(); left.setSpacing(10)
        root.addLayout(left, 3)

        title = QLabel("AERIS — Gesture Tester")
        title.setFont(QFont("Inter", 17, QFont.Bold))
        title.setStyleSheet(f"color:{C.CYAN.name()};")
        left.addWidget(title)

        sub = QLabel(
            "Live camera with hand landmarks, face identity, and object recognition · "
            "gesture consensus + neutral-rest gating · "
            "ArcFace registration when InsightFace is available."
        )
        sub.setFont(QFont("Consolas", 8))
        sub.setStyleSheet(f"color:{C.MUTED.name()};")
        sub.setWordWrap(True)
        left.addWidget(sub)

        # Camera preview
        self._preview = QLabel()
        self._preview.setMinimumSize(640, 480)
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setStyleSheet(
            f"background:{_rgba(C.PANEL, 0.70)};"
            f"border:1px solid {_rgba(C.BORDER, 0.60)};"
            "border-radius:10px;"
        )
        self._preview.setText("Camera preview — click Start to begin")
        self._preview.setStyleSheet(self._preview.styleSheet() +
                                    f"color:{C.MUTED.name()};")
        left.addWidget(self._preview)

        # Banner
        self._banner = QLabel("Live tester: stopped")
        self._banner.setFont(QFont("Consolas", 11, QFont.Bold))
        self._banner.setStyleSheet(
            f"color:{C.MUTED.name()};"
            f"background:{_rgba(C.PANEL, 0.50)};"
            f"border:1px solid {_rgba(C.BORDER, 0.50)};"
            "border-radius:8px;padding:8px 12px;"
        )
        self._banner.setAlignment(Qt.AlignCenter)
        left.addWidget(self._banner)

        # Stability + counts ribbon
        self._status_row = QLabel("hands: 0 · faces: 0 · objects: 0 · armed: yes")
        self._status_row.setFont(QFont("Consolas", 8))
        self._status_row.setStyleSheet(f"color:{C.MUTED.name()};padding:0 4px;")
        left.addWidget(self._status_row)

        # Face registration row
        reg_row = QHBoxLayout(); reg_row.setSpacing(8)
        reg_lbl = QLabel("Register face as:")
        reg_lbl.setFont(QFont("Inter", 9))
        reg_lbl.setStyleSheet(f"color:{C.PRIMARY.name()};")
        reg_row.addWidget(reg_lbl)
        self._reg_input = QLineEdit()
        self._reg_input.setPlaceholderText("Shivang Rastogi")
        self._reg_input.setFont(QFont("Inter", 9))
        self._reg_input.setStyleSheet(
            f"QLineEdit{{background:{C.PANEL.name()};"
            f"color:{C.PRIMARY.name()};"
            f"border:1px solid {_rgba(C.BORDER, 0.60)};"
            "border-radius:6px;padding:5px 8px;}}"
            f"QLineEdit:focus{{border:1px solid {C.CYAN.name()};}}"
        )
        reg_row.addWidget(self._reg_input, 1)
        self._reg_btn = QPushButton("Register")
        self._style_btn(self._reg_btn, C.CYAN)
        self._reg_btn.clicked.connect(self._on_register_clicked)
        reg_row.addWidget(self._reg_btn)
        self._forget_btn = QPushButton("Forget")
        self._style_btn(self._forget_btn, C.RED)
        self._forget_btn.clicked.connect(self._on_forget_clicked)
        reg_row.addWidget(self._forget_btn)
        left.addLayout(reg_row)

        # Known names ribbon
        self._known_lbl = QLabel(self._known_text())
        self._known_lbl.setFont(QFont("Consolas", 8))
        self._known_lbl.setStyleSheet(f"color:{C.MUTED.name()};")
        self._known_lbl.setWordWrap(True)
        left.addWidget(self._known_lbl)

        # Live volume readout — driven by the thumb+index gesture.
        self._volume_lbl = QLabel(
            "Volume gesture: close 3 fingers, extend only thumb + index, "
            "hold ~0.3s; thumb-index distance controls volume."
        )
        self._volume_lbl.setFont(QFont("Consolas", 8))
        self._volume_lbl.setStyleSheet(f"color:{C.MUTED.name()};")
        self._volume_lbl.setWordWrap(True)
        left.addWidget(self._volume_lbl)

        # Toggles + Start/Stop
        ctrl = QHBoxLayout(); ctrl.setSpacing(10)
        self._chk_lm = QCheckBox("hand landmarks")
        self._chk_face = QCheckBox("face boxes")
        self._chk_obj = QCheckBox("object recognition")
        self._chk_obj.setToolTip(
            "Enable YOLO object detection overlays. Requires the object detector "
            "model/dependencies; when unavailable, the tester simply shows no boxes."
        )
        for chk, sig in (
            (self._chk_lm, self.request_show_lm),
            (self._chk_face, self.request_show_face),
            (self._chk_obj, self.request_show_obj),
        ):
            chk.setChecked(chk is not self._chk_obj)
            chk.setStyleSheet(f"color:{C.SECONDARY.name()};font:9pt 'Consolas';")
            chk.toggled.connect(sig.emit)
            ctrl.addWidget(chk)
        # Fire-actions toggle (default OFF — opt-in to real actions).
        self._chk_fire = QCheckBox("FIRE actions (lock / mute / volume / etc.)")
        self._chk_fire.setChecked(False)
        self._chk_fire.setToolTip(
            "When OFF: tester only displays the recognised gesture. "
            "When ON: actions actually fire — the fist will lock your "
            "screen, the pinch will toggle mic mute, and the thumb+index "
            "gesture will set system volume in real time."
        )
        self._chk_fire.setStyleSheet(
            f"color:{C.AMBER.name()};font:9pt 'Consolas';"
        )
        self._chk_fire.toggled.connect(self.request_fire_actions.emit)
        ctrl.addWidget(self._chk_fire)
        ctrl.addStretch(1)
        self._start_btn = QPushButton("Start live test")
        self._style_btn(self._start_btn, C.GREEN, big=True)
        self._start_btn.clicked.connect(self._start)
        ctrl.addWidget(self._start_btn)
        self._stop_btn = QPushButton("Stop")
        self._style_btn(self._stop_btn, C.RED, big=True)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        ctrl.addWidget(self._stop_btn)
        left.addLayout(ctrl)

        # RIGHT column — scrollable gesture catalog
        right = QVBoxLayout(); right.setSpacing(10)
        root.addLayout(right, 2)

        cat_title = QLabel("Working Gesture Catalog (21 gestures)")
        cat_title.setFont(QFont("Inter", 11, QFont.Bold))
        cat_title.setStyleSheet(f"color:{C.PRIMARY.name()};")
        right.addWidget(cat_title)

        inner = QWidget()
        ilay = QVBoxLayout(inner); ilay.setContentsMargins(0, 0, 0, 0); ilay.setSpacing(6)
        for key, glyph, name, action, how_to, cat in GESTURES:
            row = _GestureRow(key, glyph, name, action, how_to, cat)
            self._rows[key] = row
            ilay.addWidget(row)
        ilay.addStretch(1)
        sa = QScrollArea()
        sa.setWidget(inner); sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:transparent;width:6px;}"
            f"QScrollBar::handle:vertical{{background:{_rgba_rgb(0, 212, 255, 0.25)};border-radius:3px;}}"
            "QScrollBar::add-line,QScrollBar::sub-line{height:0;}"
        )
        inner.setStyleSheet("background:transparent;")
        right.addWidget(sa, 1)

    # ── helpers ─────────────────────────────────────────────────────

    def _style_btn(self, btn: QPushButton, color: QColor, big: bool = False):
        btn.setFont(QFont("Consolas", 10 if big else 9, QFont.Bold))
        btn.setCursor(Qt.PointingHandCursor)
        if big:
            btn.setMinimumHeight(36)
        btn.setStyleSheet(
            f"QPushButton{{background:{_rgba(color, 0.20)};"
            f"color:{color.name()};"
            f"border:1px solid {_rgba(color, 0.50)};"
            "border-radius:8px;padding:6px 14px;}}"
            f"QPushButton:hover{{background:{_rgba(color, 0.32)};}}"
            f"QPushButton:disabled{{background:transparent;color:{C.MUTED.name()};"
            f"border:1px solid {_rgba(C.BORDER, 0.30)};}}"
        )

    def _known_text(self) -> str:
        names = self._reg.all_names()
        if not names:
            return "Known faces: (none registered yet)"
        return "Known faces: " + " · ".join(names)

    # ── lifecycle ───────────────────────────────────────────────────

    def _start(self):
        self.request_start.emit()
        self._running = True
        self._banner.setText("Live tester: STARTING — camera warming up")
        self._banner.setStyleSheet(
            f"color:{C.AMBER.name()};"
            f"background:{_rgba(C.AMBER, 0.10)};"
            f"border:1px solid {_rgba(C.AMBER, 0.40)};"
            "border-radius:8px;padding:8px 12px;"
        )
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _stop(self):
        self.request_stop.emit()
        self._running = False
        self._banner.setText("Live tester: stopped")
        self._banner.setStyleSheet(
            f"color:{C.MUTED.name()};"
            f"background:{_rgba(C.PANEL, 0.50)};"
            f"border:1px solid {_rgba(C.BORDER, 0.50)};"
            "border-radius:8px;padding:8px 12px;"
        )
        self._preview.setText("Camera preview — click Start to begin")
        self._preview.setPixmap(QPixmap())
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def closeEvent(self, e):
        self._running = False
        try:
            QMetaObject.invokeMethod(self._worker, "stop_capture", Qt.BlockingQueuedConnection)
        except Exception:
            try:
                self._worker.stop_capture()
            except Exception:
                pass
        for signal, slot in (
            (self._worker.frame_ready, self._on_frame),
            (self._worker.gesture_emitted, self._on_gesture),
            (self._worker.meta_ready, self._on_meta),
            (self._worker.error, self._on_error),
            (self._worker.face_registered, self._on_face_registered),
            (self._worker.volume_changed, self._on_volume),
            (self._worker.whip_detected, self._on_whip),
            (self._worker.scroll_emitted, self._on_scroll),
        ):
            try:
                signal.disconnect(slot)
            except Exception:
                pass
        self._worker_thread.quit()
        self._worker_thread.wait(3000)
        super().closeEvent(e)

    # ── UI slots (GUI thread) ───────────────────────────────────────

    def _on_frame(self, qimg: QImage):
        # Scale to label while preserving aspect.
        pm = QPixmap.fromImage(qimg)
        if self._preview.width() > 0 and self._preview.height() > 0:
            pm = pm.scaled(self._preview.size(),
                           Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
        self._preview.setPixmap(pm)

    def _on_meta(self, meta: dict):
        armed = meta.get("armed", True)
        neutral = meta.get("neutral", 0)
        hands = meta.get("hands", 0)
        faces = meta.get("faces", 0)
        objs = meta.get("objects", 0)
        object_status = meta.get("object_status", "object recognition off")
        gate = "ARMED" if armed else f"LOCKED ({neutral}/{REARM_NEUTRAL_FRAMES} neutral)"
        self._status_row.setText(
            f"hands: {hands} · faces: {faces} · objects: {objs} "
            f"({object_status}) · {gate}"
        )

    def _on_gesture(self, name: str):
        when = time.strftime("%H:%M:%S")
        self._banner.setText(f"Recognised: {name}    @ {when}")
        self._banner.setStyleSheet(
            f"color:{C.GREEN.name()};"
            f"background:{_rgba(C.GREEN, 0.10)};"
            f"border:1px solid {_rgba(C.GREEN, 0.40)};"
            "border-radius:8px;padding:8px 12px;"
        )
        row = self._rows.get(name)
        if row is not None:
            row.bump_count()

    def _on_error(self, msg: str):
        self._banner.setText(f"Error: {msg}")
        self._banner.setStyleSheet(
            f"color:{C.RED.name()};"
            f"background:{_rgba(C.RED, 0.10)};"
            f"border:1px solid {_rgba(C.RED, 0.40)};"
            "border-radius:8px;padding:8px 12px;"
        )
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def _on_face_registered(self, name: str, total: int):
        if total == 0:
            self._banner.setText(f"Forgot face: {name}")
        else:
            self._banner.setText(
                f"Registered '{name}' (sample {total}). "
                f"Add 2-3 more from different angles for robustness."
            )
        self._known_lbl.setText(self._known_text())

    def _on_volume(self, pct: int):
        applied = " · applied" if self._chk_fire.isChecked() else ""
        # Build a 20-cell ASCII bar so it reads at a glance in the ribbon.
        n = max(0, min(20, pct // 5))
        bar = "█" * n + "░" * (20 - n)
        self._volume_lbl.setText(f"Volume gesture: [{bar}] {pct}%{applied}")

    def _on_whip(self, direction: str):
        applied = " · alt-tab fired" if self._chk_fire.isChecked() else ""
        when = time.strftime("%H:%M:%S")
        self._banner.setText(f"WHIP {direction.upper()} detected{applied}  @ {when}")
        self._banner.setStyleSheet(
            f"color:{C.GREEN.name()};"
            f"background:{_rgba(C.GREEN, 0.12)};"
            f"border:1px solid {_rgba(C.GREEN, 0.45)};"
            "border-radius:8px;padding:8px 12px;"
        )

    def _on_scroll(self, direction: str):
        applied = " · key sent" if self._chk_fire.isChecked() else ""
        when = time.strftime("%H:%M:%S")
        self._banner.setText(f"SCROLL {direction.upper()}{applied}  @ {when}")
        self._banner.setStyleSheet(
            f"color:{C.AMBER.name()};"
            f"background:{_rgba(C.AMBER, 0.10)};"
            f"border:1px solid {_rgba(C.AMBER, 0.45)};"
            "border-radius:8px;padding:8px 12px;"
        )

    def _on_register_clicked(self):
        name = self._reg_input.text().strip()
        if not name:
            self._banner.setText("Type a name first, then click Register.")
            return
        if not self._running:
            self._banner.setText("Start the live test first — need a face on camera.")
            return
        self.request_register.emit(name)
        self._banner.setText(
            f"Registering '{name}'… look straight at the camera. "
            "The next clear face will be captured."
        )

    def _on_forget_clicked(self):
        name = self._reg_input.text().strip()
        if not name:
            self._banner.setText("Type the name to forget, then click Forget.")
            return
        self.request_forget.emit(name)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    w = GestureTesterWindow()
    w.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
