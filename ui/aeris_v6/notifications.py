"""NotificationLayer — proactive toast stack (jv6-notifications.jsx).

Anchored top-right inside the window. ``push(title, body, kind)`` slides in a
toast with an accent stripe and a progress bar that auto-dismisses after a few
seconds; toasts stack downward. ``reposition()`` keeps the stack glued to the
top-right corner when the window resizes.
"""
from __future__ import annotations

from PyQt5.QtCore import (
    QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, pyqtSignal,
)
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.aeris_v6.tokens import J, W_BOLD, W_SEMIBOLD, col, font_mono, font_ui, rgba_str
from ui.aeris_v6.widgets import StatusDot

_KIND_ACCENT = {
    "suggest": "cyan", "focus": "purple", "auto": "green",
    "pattern": "amber", "warn": "red", "info": "cyan",
}

_TOAST_W = 320
_LIFETIME_MS = 6000


class _Toast(QFrame):
    closed = pyqtSignal(object)
    actioned = pyqtSignal(dict)

    def __init__(self, title, body, kind, action, parent=None):
        super().__init__(parent)
        self._action = action or {}
        accent = _KIND_ACCENT.get(kind, "cyan")
        self._accent = accent
        self.setFixedWidth(_TOAST_W)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"_Toast{{background:{rgba_str((13,21,37), 0.97)};"
            f"border:1px solid {rgba_str(accent, 0.35)};border-radius:10px;}}"
        )
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 10, 12, 12); lay.setSpacing(5)
        top = QHBoxLayout(); top.setSpacing(7)
        top.addWidget(StatusDot(col(accent), size=5))
        t = QLabel(title); t.setFont(font_ui(11, W_SEMIBOLD))
        t.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
        top.addWidget(t); top.addStretch(1)
        lay.addLayout(top)
        b = QLabel(body); b.setWordWrap(True); b.setFont(font_mono(9))
        b.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        lay.addWidget(b)

        self._life = QTimer(self); self._life.setSingleShot(True)
        self._life.timeout.connect(lambda: self.closed.emit(self))
        self._life.start(_LIFETIME_MS)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.actioned.emit(self._action)
            self.closed.emit(self)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen); p.setBrush(col(self._accent))
        p.drawRoundedRect(QRectF(0, 0, 3, self.height()), 1.5, 1.5)
        p.end()


class NotificationLayer(QWidget):
    action = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._toasts = []
        self._host = QWidget(self)
        self._lay = QVBoxLayout(self._host)
        self._lay.setContentsMargins(0, 0, 0, 0); self._lay.setSpacing(10)
        self._lay.setAlignment(Qt.AlignTop)
        self.resize(_TOAST_W + 8, 600)
        self._host.resize(_TOAST_W + 8, 600)

    def push(self, title, body, kind="info", action=None):
        t = _Toast(title, body, kind, action)
        t.closed.connect(self._dismiss)
        t.actioned.connect(self.action)
        self._toasts.append(t)
        self._lay.addWidget(t)
        self.reposition()
        self.raise_()

    def _dismiss(self, toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
            toast.setParent(None); toast.deleteLater()
        self.reposition()

    def reposition(self):
        par = self.parentWidget()
        if par is None:
            return
        margin = 18
        w = _TOAST_W + 8
        self.resize(w, max(120, par.height() - 80))
        self._host.resize(w, self.height())
        self.move(par.width() - w - margin, 52)
