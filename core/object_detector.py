"""On-demand object detection for "what am I holding" / "what do you see".

Two backends, picked at runtime in this order:
  1. ultralytics YOLOv8n  - 80 COCO classes, ~6 MB model, downloaded on first use
  2. mediapipe ObjectDetector with EfficientDet-Lite0  (fallback)

Both are lazy-loaded — no cost at boot. The first call may take a few
seconds while the model file downloads to ``data/models/``.

Detected objects are returned as a list of (label, confidence, bbox).
Helpers also produce a spoken summary that prioritizes "in-hand" objects
(detections near the image center) over background clutter.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_MODEL_DIR = os.path.join(_ROOT, "data", "models")
os.makedirs(_MODEL_DIR, exist_ok=True)


@dataclass
class Detection:
    label: str
    score: float
    bbox: tuple[int, int, int, int]   # x1, y1, x2, y2

    def area(self) -> int:
        return max(0, self.bbox[2] - self.bbox[0]) * max(0, self.bbox[3] - self.bbox[1])

    def center(self) -> tuple[float, float]:
        return ((self.bbox[0] + self.bbox[2]) / 2.0,
                (self.bbox[1] + self.bbox[3]) / 2.0)


class ObjectDetector:
    """Lazy-init detector that picks the best backend available."""

    def __init__(self):
        self._lock = threading.RLock()
        self._backend: Optional[str] = None
        self._model = None

    def _ensure_loaded(self) -> bool:
        with self._lock:
            if self._backend is not None:
                return self._model is not None
            # Try YOLO first.
            try:
                from ultralytics import YOLO
                model_path = os.path.join(_MODEL_DIR, "yolov8n.pt")
                # Ultralytics auto-downloads if path is just "yolov8n.pt", but
                # we want the file in our models dir so we can clean it up.
                if not os.path.exists(model_path):
                    log.info("[object] downloading yolov8n.pt (~6 MB)...")
                    self._model = YOLO("yolov8n.pt")
                    # Save copy for later runs.
                    try:
                        import shutil
                        cached = self._model.ckpt_path or "yolov8n.pt"
                        if os.path.exists(cached) and cached != model_path:
                            shutil.copy(cached, model_path)
                    except Exception:
                        pass
                else:
                    self._model = YOLO(model_path)
                self._backend = "yolo"
                log.info("[object] YOLOv8n ready.")
                return True
            except Exception as e:
                log.info("[object] ultralytics unavailable: %s", e)
            # Fallback: mediapipe object detector.
            try:
                import mediapipe as mp
                from mediapipe.tasks import python as mp_py
                from mediapipe.tasks.python import vision as mp_vision
                model_path = os.path.join(_MODEL_DIR, "efficientdet_lite0.tflite")
                if not os.path.exists(model_path):
                    log.info("[object] mediapipe model missing; cannot run.")
                    return False
                base_opts = mp_py.BaseOptions(model_asset_path=model_path)
                opts = mp_vision.ObjectDetectorOptions(
                    base_options=base_opts,
                    running_mode=mp_vision.RunningMode.IMAGE,
                    score_threshold=0.4,
                    max_results=8,
                )
                self._model = mp_vision.ObjectDetector.create_from_options(opts)
                self._backend = "mediapipe"
                log.info("[object] mediapipe EfficientDet ready.")
                return True
            except Exception as e:
                log.info("[object] mediapipe object detector unavailable: %s", e)
            self._backend = "none"
            return False

    def is_available(self) -> bool:
        return self._ensure_loaded()

    # ------------------------------------------------------------------ #
    #  Detect                                                             #
    # ------------------------------------------------------------------ #

    def detect(self, frame_bgr) -> list[Detection]:
        if not self._ensure_loaded():
            return []
        if self._backend == "yolo":
            return self._detect_yolo(frame_bgr)
        if self._backend == "mediapipe":
            return self._detect_mediapipe(frame_bgr)
        return []

    def _detect_yolo(self, frame_bgr) -> list[Detection]:
        try:
            results = self._model.predict(frame_bgr, verbose=False, conf=0.35)
        except Exception as e:
            log.warning("[object] yolo predict failed: %s", e)
            return []
        out: list[Detection] = []
        for r in results:
            names = r.names
            if r.boxes is None:
                continue
            for box in r.boxes:
                try:
                    cls_id = int(box.cls.item())
                    conf = float(box.conf.item())
                    xyxy = box.xyxy.cpu().numpy().flatten()
                    x1, y1, x2, y2 = (int(xyxy[0]), int(xyxy[1]),
                                      int(xyxy[2]), int(xyxy[3]))
                    out.append(Detection(
                        label=str(names.get(cls_id, str(cls_id))),
                        score=conf, bbox=(x1, y1, x2, y2),
                    ))
                except Exception:
                    continue
        return out

    def _detect_mediapipe(self, frame_bgr) -> list[Detection]:
        try:
            import cv2
            import mediapipe as mp
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = self._model.detect(mp_image)
        except Exception as e:
            log.warning("[object] mediapipe detect failed: %s", e)
            return []
        out: list[Detection] = []
        for det in (res.detections or []):
            try:
                cat = det.categories[0]
                bbox = det.bounding_box
                out.append(Detection(
                    label=str(cat.category_name or "object"),
                    score=float(cat.score),
                    bbox=(int(bbox.origin_x), int(bbox.origin_y),
                          int(bbox.origin_x + bbox.width),
                          int(bbox.origin_y + bbox.height)),
                ))
            except Exception:
                continue
        return out


# --------------------------------------------------------------------------- #
#  Spoken-summary helpers                                                     #
# --------------------------------------------------------------------------- #

def rank_for_holding(detections: list[Detection], frame_shape) -> list[Detection]:
    """Rank detections by how plausibly they're being HELD by the user.

    Heuristic: prefer (a) larger area + (b) detection center close to image
    centroid. People in COCO are usually background here, so we down-weight them.
    """
    if not detections:
        return []
    h, w = frame_shape[:2]
    cx, cy = w / 2.0, h / 2.0
    scored: list[tuple[float, Detection]] = []
    for d in detections:
        ox, oy = d.center()
        dist = ((ox - cx) ** 2 + (oy - cy) ** 2) ** 0.5
        max_d = (w ** 2 + h ** 2) ** 0.5
        center_score = 1.0 - (dist / max_d)
        area_score = min(1.0, d.area() / (w * h * 0.3))   # area cap at 30 % of frame
        bonus = -0.3 if d.label.lower() in ("person",) else 0.0
        score = 0.55 * center_score + 0.35 * area_score + 0.10 * d.score + bonus
        scored.append((score, d))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [d for _, d in scored]


def format_holding_response(detections: list[Detection], frame_shape) -> str:
    if not detections:
        return "Mujhe to kuch nahi dikh raha sir — camera ke saamne object dikhao."
    ranked = rank_for_holding(detections, frame_shape)
    top = ranked[0]
    extras = [d.label for d in ranked[1:4] if d.label != top.label]
    base = f"Aap {top.label} hold kar rahe ho lagta hai (confidence {top.score*100:.0f}%)."
    if extras:
        base += f" Saath mein dikh raha hai: {', '.join(extras)}."
    return base


def format_scene_response(detections: list[Detection]) -> str:
    if not detections:
        return "Camera bilkul khali dikh raha hai, sir."
    counts: dict[str, int] = {}
    for d in detections:
        counts[d.label] = counts.get(d.label, 0) + 1
    parts = [f"{n} {label}{'s' if n > 1 else ''}" for label, n in counts.items()]
    return f"Main {len(detections)} cheezein dekh raha hoon: {', '.join(parts)}."


# Singleton.
_DEFAULT: Optional[ObjectDetector] = None


def get_object_detector() -> ObjectDetector:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = ObjectDetector()
    return _DEFAULT
