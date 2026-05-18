"""Lightweight pre-boot splash window.

Painted before the main window builds so Windows sees a responsive process
during the heavy ML pre-imports (torch / sentence-transformers / spaCy).
Without this the user gets the "Python is not responding" dialog because no
window exists yet for the OS to mark as responsive.

Only depends on PyQt5 core widgets — must remain import-cheap or it defeats
its own purpose. Do not import anything from this package's other modules
(tokens, animation_bus, etc.) here; the splash exists to cover their load.
"""
from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, QTimer, Qt
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget


class BootSplash(QWidget):
    """Frameless 380x150 panel — title, subtitle, status, accent line."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.SplashScreen
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(380, 150)

        self._status = "Initializing runtime"
        self._dot_phase = 0

        scr = QApplication.primaryScreen().geometry()
        self.move((scr.width() - self.width()) // 2,
                  (scr.height() - self.height()) // 2)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(180)

    def update_status(self, status: str) -> None:
        self._status = status
        self.update()
        QApplication.processEvents()

    def _tick(self) -> None:
        self._dot_phase = (self._dot_phase + 1) % 4
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        bg = QColor(13, 21, 37)
        bg.setAlphaF(0.96)
        p.setPen(QPen(QColor(0, 215, 230, 90), 1))
        p.setBrush(bg)
        p.drawRoundedRect(
            QRectF(0, 0, self.width() - 1, self.height() - 1), 12, 12
        )

        p.setPen(QColor(0, 215, 230))
        p.setFont(QFont("Consolas", 16, QFont.Bold))
        p.drawText(QRectF(22, 18, self.width() - 44, 28),
                   Qt.AlignVCenter | Qt.AlignLeft, "A.E.R.I.S")

        p.setPen(QColor(200, 220, 230, 170))
        p.setFont(QFont("Consolas", 9, QFont.Normal))
        p.drawText(QRectF(22, 46, self.width() - 44, 16),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   "JARVIS v3.1 · boot sequence")

        p.setPen(QColor(220, 235, 240, 230))
        p.setFont(QFont("Consolas", 10, QFont.Normal))
        dots = "." * (self._dot_phase + 1)
        p.drawText(QRectF(22, 92, self.width() - 44, 18),
                   Qt.AlignVCenter | Qt.AlignLeft, f"{self._status}{dots}")

        grad = QLinearGradient(22, 122, self.width() - 22, 122)
        grad.setColorAt(0.0, QColor(0, 215, 230, 0))
        grad.setColorAt(0.5, QColor(0, 215, 230, 200))
        grad.setColorAt(1.0, QColor(0, 215, 230, 0))
        p.setPen(QPen(grad, 1.5))
        p.drawLine(QPointF(22, 122), QPointF(self.width() - 22, 122))

    def finish(self, _target_window=None) -> None:
        self._timer.stop()
        self.close()
