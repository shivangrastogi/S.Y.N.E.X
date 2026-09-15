"""AR camera overlay — translucent always-on-top live preview with YOLO boxes.

Subscribes to the shared ``VisionEngine`` for frames, runs YOLO every Nth
frame (default 4), draws bounding boxes + labels on a copy, and pipes
the image into a QLabel at the corner of the screen. Stays on top so
the user can see what AERIS sees alongside whatever app they're using.

Public API:
    show_ar_overlay(corner='top-right', width=320) -> bool
    hide_ar_overlay() -> bool
    is_ar_visible() -> bool
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)


_INSTANCE = None             # type: ignore  (QDialog ref)
_LOCK = threading.RLock()


def is_ar_visible() -> bool:
    with _LOCK:
        if _INSTANCE is None:
            return False
        try:
            return bool(_INSTANCE.isVisible())
        except Exception:
            return False


def hide_ar_overlay() -> bool:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            return False
        try:
            _INSTANCE.close()
        except Exception:
            pass
        _INSTANCE = None
        return True


def show_ar_overlay(corner: str = "top-right", width: int = 320) -> bool:
    global _INSTANCE
    try:
        from PyQt5.QtWidgets import (
            QApplication, QDialog, QVBoxLayout, QLabel, QShortcut,
        )
        from PyQt5.QtCore import Qt, QTimer
        from PyQt5.QtGui import QImage, QPixmap, QKeySequence
    except Exception as e:
        log.info("[ar_overlay] PyQt5 unavailable: %s", e)
        return False
    try:
        import cv2  # type: ignore
    except Exception as e:
        log.info("[ar_overlay] cv2 unavailable: %s", e)
        return False

    if QApplication.instance() is None:
        log.info("[ar_overlay] no QApplication — refusing off-main spawn.")
        return False

    with _LOCK:
        if _INSTANCE is not None and _INSTANCE.isVisible():
            return True

        try:
            from core.vision_engine import get_vision_engine
            from core.object_detector import ObjectDetector
        except Exception as e:
            log.info("[ar_overlay] vision import failed: %s", e)
            return False

        detector = ObjectDetector()
        # The first detect() lazy-loads the model; do nothing here.

        dlg = QDialog(None,
                      Qt.FramelessWindowHint
                      | Qt.WindowStaysOnTopHint
                      | Qt.Tool)
        dlg.setAttribute(Qt.WA_TranslucentBackground, False)
        dlg.setAttribute(Qt.WA_ShowWithoutActivating)
        dlg.setStyleSheet(
            "QDialog { background-color: rgba(15, 20, 30, 230); "
            "border: 1px solid #58a6ff; border-radius: 8px; }"
        )

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(6, 6, 6, 6)
        title = QLabel("AERIS · AR preview")
        title.setStyleSheet("color: #58a6ff; font: 600 10pt 'Segoe UI';")
        layout.addWidget(title)
        view = QLabel()
        view.setMinimumSize(width, int(width * 3 / 4))
        view.setScaledContents(True)
        layout.addWidget(view)

        # Latest frame pipeline — populated by the vision callback on the
        # camera thread; drained on a Qt timer so QPixmap mutation lands
        # on the GUI thread.
        latest = {"frame_bgr": None}
        frame_lock = threading.Lock()
        # Throttled detection cache.
        det_state = {"frame_count": 0, "last_dets": []}

        def _on_frame(frame_bgr):
            det_state["frame_count"] += 1
            try:
                # Run YOLO every 4th frame (~7.5 fps inference at 30 fps).
                if det_state["frame_count"] % 4 == 0 and detector.is_available():
                    try:
                        det_state["last_dets"] = detector.detect(frame_bgr) or []
                    except Exception as e:
                        log.debug("[ar_overlay] detect failed: %s", e)
                # Draw a copy.
                annotated = frame_bgr.copy()
                for d in det_state["last_dets"]:
                    try:
                        x1, y1, x2, y2 = d.bbox
                        cv2.rectangle(annotated, (x1, y1), (x2, y2),
                                      (88, 166, 255), 2)
                        label = f"{d.label} {d.score:.2f}"
                        cv2.putText(annotated, label, (x1, max(20, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                    (88, 166, 255), 1, cv2.LINE_AA)
                    except Exception:
                        continue
                with frame_lock:
                    latest["frame_bgr"] = annotated
            except Exception as e:
                log.debug("[ar_overlay] _on_frame raised: %s", e)

        ok = get_vision_engine().subscribe("ar_overlay", _on_frame)
        if not ok:
            log.info("[ar_overlay] vision subscribe failed.")
            return False

        # Position
        try:
            geom = QApplication.primaryScreen().availableGeometry()
            margin = 16
            h = int(width * 3 / 4) + 30
            corners = {
                "top-right":    (geom.right() - width - margin,
                                 geom.top() + margin),
                "top-left":     (geom.left() + margin,
                                 geom.top() + margin),
                "bottom-right": (geom.right() - width - margin,
                                 geom.bottom() - h - margin),
                "bottom-left":  (geom.left() + margin,
                                 geom.bottom() - h - margin),
            }
            x, y = corners.get(corner, corners["top-right"])
            dlg.move(int(x), int(y))
            dlg.resize(width + 12, h)
        except Exception:
            pass

        def _drain():
            with frame_lock:
                frame = latest["frame_bgr"]
                latest["frame_bgr"] = None
            if frame is None:
                return
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, _ = rgb.shape
                img = QImage(rgb.tobytes(), w, h, w * 3, QImage.Format_RGB888)
                view.setPixmap(QPixmap.fromImage(img))
            except Exception as e:
                log.debug("[ar_overlay] paint failed: %s", e)

        timer = QTimer(dlg)
        timer.timeout.connect(_drain)
        timer.start(80)        # ~12 fps repaint — enough for an overlay

        def _on_close(_ev):
            timer.stop()
            try:
                from core.vision_engine import get_vision_engine
                get_vision_engine().unsubscribe("ar_overlay")
            except Exception:
                pass
            try:
                _ev.accept()
            except Exception:
                pass
        dlg.closeEvent = _on_close   # type: ignore

        # Escape closes
        QShortcut(QKeySequence(Qt.Key_Escape), dlg, activated=dlg.close)

        dlg.show()
        _INSTANCE = dlg
        log.info("[ar_overlay] shown at corner=%s width=%d", corner, width)
        return True
