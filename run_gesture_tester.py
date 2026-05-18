"""Standalone gesture catalog + live tester for AERIS.

Run with:  ``py run_gesture_tester.py``

Shows every recognized gesture with:
  * Name + glyph + one-line action
  * Detailed "how to perform" description (toggle via ⓘ button)
  * Current live trigger count (filled in once you start the tester)

Bottom toolbar:
  * **Start live test** — turns on the gesture engine + camera; the
    most-recent-recognized gesture flashes in the top banner, and the
    per-card counter ticks up.
  * **Stop** — releases the camera (does NOT touch any AERIS instance
    you might also have running; this script uses its OWN gesture
    engine instance to avoid stepping on the main app).

Why a separate tester
---------------------
1. Learn the vocabulary without scrolling chat history.
2. Verify your camera + lighting works for AERIS before relying on
   it during a meeting/cooking/coding.
3. Tune your hand pose — the live trigger counter tells you whether
   your "peace sign" registers as ``peace`` or as something else.
"""
from __future__ import annotations

import os
import sys
import time

# Same Windows DLL ordering fix as run_gui.py — torch before PyQt5.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
try:
    import torch  # noqa: F401
except Exception as _e:
    sys.stderr.write(f"[gesture_tester] WARN: torch pre-import failed: {_e}\n")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)


# ─── Catalog ──────────────────────────────────────────────────────── #

# One entry per gesture the engine emits. Order = how we display.
# (key, glyph, name, action, how_to, category)
GESTURES = [
    # Single-hand poses
    ("fist",            "✊",   "Fist (0.6s hold)",
     "Lock workstation (LockWorkStation)",
     "Make a tight fist with all fingers curled. Hold for 0.6s. "
     "Holding the SAME fist past 3 seconds triggers `long_fist` instead.",
     "Pose"),
    ("long_fist",       "✊⏱",  "Long fist (3s hold)",
     "Toggle command palette",
     "Keep the fist held for 3 seconds total. Distinct from the "
     "0.6s fist=lock so you don't lock by accident.",
     "Pose"),
    ("open_palm_hold",  "🖐⏸",  "Open palm hold (~1s)",
     "Media play / pause",
     "Show an open palm to the camera and hold it still for ~1 second. "
     "Don't move — motion triggers swipe gestures instead.",
     "Pose"),
    ("thumbs_up",       "👍",   "Thumbs up",
     "Volume up (×3 ticks)",
     "Make a fist with thumb extended, thumb pointing up "
     "(above the wrist).",
     "Pose"),
    ("thumbs_down",     "👎",   "Thumbs down",
     "Volume down (×3 ticks)",
     "Make a fist with thumb extended, thumb pointing down "
     "(below the wrist).",
     "Pose"),
    ("peace",           "✌",   "Peace / V sign",
     "Win+Shift+S — screenshot snip",
     "Index and middle finger extended, ring and pinky curled. "
     "Hold for 0.35s to commit.",
     "Pose"),
    ("pinch",           "👌•",  "Pinch (closed)",
     "Toggle mic mute (pycaw)",
     "Thumb tip touching index tip with the other three fingers CURLED. "
     "Distinct from OK sign which has the other three extended.",
     "Pose"),
    ("three_up",        "🤟",   "Three fingers up",
     "Next media track",
     "Index + middle + ring fingers extended, pinky curled. Thumb "
     "doesn't matter.",
     "Pose"),
    ("ok_sign",         "👌",   "OK sign",
     "Toggle command palette",
     "Thumb tip touching index tip, with middle + ring + pinky "
     "all EXTENDED (the classic 'OK' / 'A-OK' sign).",
     "Pose"),

    # Motion patterns
    ("swipe_left",      "👈",   "Swipe ←",
     "Alt+Shift+Tab (or Ctrl+Shift+Tab in browser)",
     "Open palm, swipe horizontally LEFT across the camera by at "
     "least 18% of the frame width within 0.6 seconds.",
     "Motion"),
    ("swipe_right",     "👉",   "Swipe →",
     "Alt+Tab (or Ctrl+Tab in browser)",
     "Open palm, swipe horizontally RIGHT across the camera.",
     "Motion"),
    ("swipe_up",        "👆",   "Swipe ↑",
     "Page Up (scroll up)",
     "Open palm, swipe UP across the camera. Vertical motion wins "
     "over horizontal if both axes move.",
     "Motion"),
    ("swipe_down",      "👇",   "Swipe ↓",
     "Page Down (scroll down)",
     "Open palm, swipe DOWN across the camera. Useful when reading "
     "a recipe with wet hands.",
     "Motion"),
    ("wave",            "🌊",   "Wave (rapid L↔R)",
     "Escape (dismiss dialog / notification)",
     "Open palm with rapid back-and-forth motion — at least 2 "
     "direction reversals within 0.6 seconds, 15%+ amplitude.",
     "Motion"),

    # Two-handed
    ("two_palm_spread", "🖐↔🖐", "Both palms spread apart",
     "Ctrl++ (zoom in)",
     "Both hands open, palm-out. Move them APART by 15%+ of frame "
     "width within 0.5 seconds. Most useful in browsers and viewers.",
     "Two-handed"),
    ("two_palm_pinch",  "🖐↔🖐", "Both palms together",
     "Ctrl+- (zoom out)",
     "Both hands open, palm-out. Move them TOGETHER by 15%+ within "
     "0.5 seconds.",
     "Two-handed"),
    ("clap",            "👏",   "Clap",
     "Bring AERIS window to front",
     "Bring both hands together fast (≥20% drop in distance), final "
     "inter-hand distance ≤0.18. Different from zoom-out by tighter "
     "end state.",
     "Two-handed"),

    # Air strokes (point + trace)
    ("stroke_circle",   "○",   "Air-draw circle",
     "F5 (refresh page)",
     "Point with INDEX finger only, trace a closed circle in the air. "
     "Lower your hand from pointing pose to commit. Works whenever "
     "you can refresh — browser, file explorer, etc.",
     "Stroke"),
    ("stroke_x",        "✕",   "Air-draw X",
     "Ctrl+W (close window/tab)",
     "Point with index finger, draw two crossing diagonal strokes. "
     "Then lower your hand.",
     "Stroke"),
    ("stroke_check",    "✓",   "Air-draw check",
     "Enter (confirm/submit)",
     "Point with index finger, trace a check mark — down then up-right. "
     "Then lower your hand.",
     "Stroke"),
    ("stroke_arrow_right", "→", "Air-draw arrow →",
     "Right arrow key (next slide / photo)",
     "Point with index finger, draw a strong horizontal stroke "
     "from left to right (net dx > 0.25, almost no vertical drift).",
     "Stroke"),
]


# Compact OS colour palette so we don't import the full tokens module.
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


# ─── Gesture row widget ───────────────────────────────────────────── #

class _GestureRow(QFrame):
    """One card per gesture. Expands to show the 'how to perform' text
    when the ⓘ button is clicked.
    """

    def __init__(self, key, glyph, name, action, how_to, category, parent=None):
        super().__init__(parent)
        self.key = key
        self._expanded = False
        self._fire_count = 0
        self._color = _CATEGORY_COLOR.get(category, C.MUTED)
        self.setObjectName("GestureRow")
        self.setStyleSheet(
            "QFrame#GestureRow{"
            f"background:rgba({C.PANEL.red()},{C.PANEL.green()},{C.PANEL.blue()},0.7);"
            f"border:1px solid rgba({self._color.red()},{self._color.green()},{self._color.blue()},0.30);"
            "border-radius:10px;}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(6)

        head = QHBoxLayout(); head.setSpacing(10)

        glyph_lbl = QLabel(glyph)
        glyph_lbl.setFont(QFont("Segoe UI Emoji", 18))
        glyph_lbl.setStyleSheet(f"color:{self._color.name()};")
        glyph_lbl.setFixedWidth(54)
        glyph_lbl.setAlignment(Qt.AlignCenter)
        head.addWidget(glyph_lbl)

        title_box = QVBoxLayout(); title_box.setSpacing(1)
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Inter", 11, QFont.Bold))
        name_lbl.setStyleSheet(f"color:{C.PRIMARY.name()};")
        title_box.addWidget(name_lbl)
        action_lbl = QLabel(f"→  {action}")
        action_lbl.setFont(QFont("Consolas", 9))
        action_lbl.setStyleSheet(f"color:{self._color.name()};")
        title_box.addWidget(action_lbl)
        meta_row = QHBoxLayout(); meta_row.setSpacing(8)
        cat_pill = QLabel(category)
        cat_pill.setFont(QFont("Consolas", 8, QFont.Bold))
        cat_pill.setStyleSheet(
            f"color:{self._color.name()};"
            f"background:rgba({self._color.red()},{self._color.green()},{self._color.blue()},0.15);"
            "padding:1px 6px;border-radius:4px;"
        )
        meta_row.addWidget(cat_pill)
        self._count_lbl = QLabel("0 triggers")
        self._count_lbl.setFont(QFont("Consolas", 8))
        self._count_lbl.setStyleSheet(f"color:{C.MUTED.name()};")
        meta_row.addWidget(self._count_lbl)
        meta_row.addStretch(1)
        title_box.addLayout(meta_row)
        head.addLayout(title_box, 1)

        info = QPushButton("ⓘ")
        info.setFixedSize(28, 28)
        info.setCursor(Qt.PointingHandCursor)
        info.setFont(QFont("Segoe UI", 11, QFont.Bold))
        info.setToolTip("Show / hide instructions")
        info.setStyleSheet(
            f"QPushButton{{background:rgba({self._color.red()},{self._color.green()},{self._color.blue()},0.15);"
            f"color:{self._color.name()};"
            f"border:1px solid rgba({self._color.red()},{self._color.green()},{self._color.blue()},0.4);"
            "border-radius:14px;}}"
            f"QPushButton:hover{{background:rgba({self._color.red()},{self._color.green()},{self._color.blue()},0.30);}}"
        )
        info.clicked.connect(self._toggle)
        head.addWidget(info)
        lay.addLayout(head)

        self._howto = QLabel(how_to)
        self._howto.setFont(QFont("Inter", 9))
        self._howto.setStyleSheet(f"color:{C.SECONDARY.name()};padding:6px 4px;")
        self._howto.setWordWrap(True)
        self._howto.hide()
        lay.addWidget(self._howto)

    def _toggle(self):
        self._expanded = not self._expanded
        self._howto.setVisible(self._expanded)

    def bump_count(self):
        self._fire_count += 1
        self._count_lbl.setText(
            f"{self._fire_count} trigger{'s' if self._fire_count != 1 else ''}"
        )
        # Brief flash
        self.setStyleSheet(self.styleSheet().replace(
            f"border:1px solid rgba({self._color.red()},{self._color.green()},{self._color.blue()},0.30);",
            f"border:2px solid {self._color.name()};",
        ))
        QTimer.singleShot(450, self._unflash)

    def _unflash(self):
        self.setStyleSheet(
            "QFrame#GestureRow{"
            f"background:rgba({C.PANEL.red()},{C.PANEL.green()},{C.PANEL.blue()},0.7);"
            f"border:1px solid rgba({self._color.red()},{self._color.green()},{self._color.blue()},0.30);"
            "border-radius:10px;}"
        )


# ─── Main window ──────────────────────────────────────────────────── #

class GestureTesterWindow(QWidget):

    gesture_emitted = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AERIS — Gesture Tester")
        self.setMinimumSize(720, 720)
        self.setStyleSheet(f"background:{C.BG.name()};")

        self._engine = None
        self._rows: dict[str, _GestureRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20); root.setSpacing(14)

        # Header
        title = QLabel("AERIS — Gesture Catalog")
        title.setFont(QFont("Inter", 18, QFont.Bold))
        title.setStyleSheet(f"color:{C.CYAN.name()};letter-spacing:2px;")
        root.addWidget(title)

        sub = QLabel(f"21 gestures across 4 categories — click ⓘ on any row "
                     f"for instructions. Use the live tester at the bottom "
                     f"to verify your camera sees the right thing.")
        sub.setFont(QFont("Consolas", 9))
        sub.setStyleSheet(f"color:{C.MUTED.name()};")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # Live banner — shows the latest recognized gesture name
        self._banner = QLabel("Live tester: stopped")
        self._banner.setFont(QFont("Consolas", 11, QFont.Bold))
        self._banner.setStyleSheet(
            f"color:{C.MUTED.name()};"
            f"background:rgba({C.PANEL.red()},{C.PANEL.green()},{C.PANEL.blue()},0.5);"
            f"border:1px solid rgba({C.BORDER.red()},{C.BORDER.green()},{C.BORDER.blue()},0.5);"
            "border-radius:8px;padding:10px 14px;"
        )
        self._banner.setAlignment(Qt.AlignCenter)
        root.addWidget(self._banner)

        # Scrollable grid of rows
        inner = QWidget()
        ilay = QVBoxLayout(inner); ilay.setContentsMargins(0, 0, 0, 0); ilay.setSpacing(8)
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
            "QScrollBar::handle:vertical{background:rgba(0,212,255,0.25);border-radius:3px;}"
            "QScrollBar::add-line,QScrollBar::sub-line{height:0;}"
        )
        inner.setStyleSheet("background:transparent;")
        root.addWidget(sa, 1)

        # Footer with controls
        ft = QHBoxLayout(); ft.setSpacing(10)
        self._start_btn = QPushButton("Start live test")
        self._start_btn.setFont(QFont("Consolas", 10, QFont.Bold))
        self._start_btn.setCursor(Qt.PointingHandCursor)
        self._start_btn.setMinimumHeight(36)
        self._start_btn.setStyleSheet(
            f"QPushButton{{background:rgba({C.GREEN.red()},{C.GREEN.green()},{C.GREEN.blue()},0.20);"
            f"color:{C.GREEN.name()};"
            f"border:1px solid rgba({C.GREEN.red()},{C.GREEN.green()},{C.GREEN.blue()},0.5);"
            "border-radius:8px;padding:6px 16px;}}"
            f"QPushButton:hover{{background:rgba({C.GREEN.red()},{C.GREEN.green()},{C.GREEN.blue()},0.32);}}"
        )
        self._start_btn.clicked.connect(self._start_test)
        ft.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setFont(QFont("Consolas", 10, QFont.Bold))
        self._stop_btn.setCursor(Qt.PointingHandCursor)
        self._stop_btn.setMinimumHeight(36)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet(
            f"QPushButton{{background:rgba({C.RED.red()},{C.RED.green()},{C.RED.blue()},0.18);"
            f"color:{C.RED.name()};"
            f"border:1px solid rgba({C.RED.red()},{C.RED.green()},{C.RED.blue()},0.4);"
            "border-radius:8px;padding:6px 16px;}}"
            f"QPushButton:hover{{background:rgba({C.RED.red()},{C.RED.green()},{C.RED.blue()},0.28);}}"
            f"QPushButton:disabled{{background:transparent;color:{C.MUTED.name()};"
            f"border:1px solid rgba({C.BORDER.red()},{C.BORDER.green()},{C.BORDER.blue()},0.3);}}"
        )
        self._stop_btn.clicked.connect(self._stop_test)
        ft.addWidget(self._stop_btn)
        ft.addStretch(1)
        hint = QLabel("Triggers count + flash on each card · ⓘ for help")
        hint.setFont(QFont("Consolas", 8))
        hint.setStyleSheet(f"color:{C.MUTED.name()};")
        ft.addWidget(hint)
        root.addLayout(ft)

        # Marshals gesture-engine events (worker thread) to GUI thread.
        self.gesture_emitted.connect(self._on_gesture_gui)

    # ── lifecycle ──────────────────────────────────────────────────

    def _start_test(self):
        try:
            from core.gesture_engine import get_gesture_engine
            self._engine = get_gesture_engine()
        except Exception as e:
            self._banner.setText(f"Could not load gesture engine: {e}")
            return
        if not self._engine.is_available():
            self._banner.setText(
                "Gesture engine offline — install mediapipe + opencv-python."
            )
            return
        if not self._engine.start():
            try:
                from core.vision_engine import get_vision_engine
                reason = get_vision_engine().last_error() or "webcam check karo"
            except Exception:
                reason = "webcam check karo"
            self._banner.setText(f"Camera open nahi ho paya — {reason}")
            return
        self._engine.add_listener(self.gesture_emitted.emit)
        self._banner.setText("Live tester: RUNNING — perform a gesture in front of the camera")
        self._banner.setStyleSheet(
            f"color:{C.GREEN.name()};"
            f"background:rgba({C.GREEN.red()},{C.GREEN.green()},{C.GREEN.blue()},0.10);"
            f"border:1px solid rgba({C.GREEN.red()},{C.GREEN.green()},{C.GREEN.blue()},0.4);"
            "border-radius:8px;padding:10px 14px;"
        )
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

    def _stop_test(self):
        if self._engine is not None:
            try: self._engine.stop()
            except Exception: pass
        self._banner.setText("Live tester: stopped")
        self._banner.setStyleSheet(
            f"color:{C.MUTED.name()};"
            f"background:rgba({C.PANEL.red()},{C.PANEL.green()},{C.PANEL.blue()},0.5);"
            f"border:1px solid rgba({C.BORDER.red()},{C.BORDER.green()},{C.BORDER.blue()},0.5);"
            "border-radius:8px;padding:10px 14px;"
        )
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def closeEvent(self, e):
        self._stop_test()
        super().closeEvent(e)

    # ── event handler (GUI thread) ─────────────────────────────────

    def _on_gesture_gui(self, name: str):
        when = time.strftime("%H:%M:%S")
        self._banner.setText(f"Recognized: {name}    @ {when}")
        row = self._rows.get(name)
        if row is not None:
            row.bump_count()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    w = GestureTesterWindow()
    w.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
