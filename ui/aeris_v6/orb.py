"""FloatingOrb — compact minimized presence (jv6-orb.jsx).

A small draggable always-on-top orb that shows the live AI-state colour and,
on click, asks the host to expand back to the full window. Reuses the
ArcReactor's look at a tiny scale via a self-painted ring + core.
"""
from __future__ import annotations

import math

from PyQt5.QtCore import QElapsedTimer, QPointF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget

from ui.aeris_v6.tokens import JSTATES, col


class FloatingOrb(QWidget):
    expand = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(76, 76)
        self.setCursor(Qt.PointingHandCursor)
        self._state = "IDLE"
        self._drag = None
        self._clock = QElapsedTimer(); self._clock.start()
        t = QTimer(self); t.timeout.connect(self.update); t.start(33)

    def set_state(self, state):
        if state in JSTATES:
            self._state = state

    def paintEvent(self, _ev):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        c = col(JSTATES.get(self._state, JSTATES["IDLE"])["key"])
        cx, cy = self.width() / 2, self.height() / 2
        p.translate(cx, cy)
        el = self._clock.elapsed() / 1000.0
        # outer rotating arc
        p.save(); p.rotate((el / (1.4 if self._state == "PROCESSING" else 6)) * 360)
        pen = QPen(c); pen.setWidthF(2.0); p.setPen(pen)
        p.drawArc(-30, -30, 60, 60, 0, 300 * 16)
        p.restore()
        # glow + core
        glow = QColor(c); glow.setAlphaF(0.4)
        p.setPen(Qt.NoPen); p.setBrush(glow)
        p.drawEllipse(QPointF(0, 0), 16, 16)
        pulse = 0.85 + 0.15 * math.sin(2 * math.pi * el / 2.4)
        p.setBrush(c)
        p.drawEllipse(QPointF(0, 0), 9 * pulse, 9 * pulse)
        p.end()

    # drag to move; click (no drag) to expand
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
            self._moved = False

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag); self._moved = True

    def mouseReleaseEvent(self, e):
        if self._drag is not None and not getattr(self, "_moved", False):
            self.expand.emit()
        self._drag = None
