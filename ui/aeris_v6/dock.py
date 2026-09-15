"""FloatingDock — left navigation rail, ported from ``jv3-dock.jsx``.

Collapsed to a 56 px icon rail; expands to 210 px on hover (animated) to
reveal labels, a spinning logo mark and a user card. Emits ``navigate(key)``.
"""
from __future__ import annotations

from PyQt5.QtCore import (
    QEasingCurve, QElapsedTimer, QPointF, QPropertyAnimation, QRectF, Qt,
    QTimer, pyqtSignal,
)
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from ui.aeris_v6.tokens import (
    J, W_BOLD, W_MEDIUM, W_SEMIBOLD, ca, col, font_ui, rgba_str,
)
from ui.aeris_v6.widgets import IconWidget, paint_icon

DOCK_ITEMS = [
    ("home", "Home", "home"),
    ("chat", "Conversations", "chat"),
    ("auto", "Automations", "auto"),
    None,
    ("brain", "Brain", "brain"),
    ("memory", "Memory", "memory"),
    None,
    ("system", "System", "system"),
    ("settings", "Settings", "settings"),
]

_COLLAPSED = 56
_EXPANDED = 210


class _LogoMark(QWidget):
    """Two counter-rotating rings + a glowing cyan core."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self._clock = QElapsedTimer(); self._clock.start()
        t = QTimer(self); t.timeout.connect(self.update); t.start(33)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        el = self._clock.elapsed() / 1000.0
        cx, cy = self.width() / 2, self.height() / 2
        p.translate(cx, cy)
        # outer ring
        p.save(); p.rotate((el / 6.0) * 360)
        pen = QPen(ca("cyan", 0.6)); pen.setWidthF(1.5); p.setPen(pen)
        p.drawArc(QRectF(-13, -13, 26, 26), 0, 300 * 16)
        p.restore()
        # inner ring reverse
        p.save(); p.rotate(-(el / 4.0) * 360)
        pen = QPen(ca("cyan", 0.4)); pen.setWidthF(1.0); p.setPen(pen)
        p.drawArc(QRectF(-9, -9, 18, 18), 0, 280 * 16)
        p.restore()
        # core
        core = col("cyan"); p.setPen(Qt.NoPen)
        glow = QColor(core); glow.setAlphaF(0.5)
        p.setBrush(glow); p.drawEllipse(QPointF(0, 0), 7, 7)
        p.setBrush(core); p.drawEllipse(QPointF(0, 0), 4, 4)
        p.end()


class DockItem(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, key, label, icon, parent=None):
        super().__init__(parent)
        self.key = key
        self._active = False
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 14, 0); lay.setSpacing(12)
        self._icon = IconWidget(icon, 18, col("textMut"))
        lay.addWidget(self._icon)
        self._label = QLabel(label)
        self._label.setFont(font_ui(11, W_MEDIUM))
        self._label.setStyleSheet(f"color:{rgba_str('textSec', 1.0)};background:transparent;")
        lay.addWidget(self._label)
        lay.addStretch(1)
        self._restyle()

    def set_active(self, on: bool):
        self._active = on
        self._restyle()

    def set_expanded(self, on: bool):
        self._label.setVisible(on)

    def _restyle(self):
        if self._active:
            bg, bd, glow = rgba_str("cyan", 0.09), rgba_str("cyan", 0.35), rgba_str("cyan", 0.18)
            self._icon.set_color(col("cyan"))
            self._label.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
            self._label.setFont(font_ui(11, W_BOLD))
        elif self._hover:
            bg, bd, glow = rgba_str("cyan", 0.05), rgba_str("cyan", 0.15), "transparent"
            self._icon.set_color(ca("cyan", 0.85))
            self._label.setStyleSheet("color:rgb(210,225,240);background:transparent;")
            self._label.setFont(font_ui(11, W_MEDIUM))
        else:
            bg, bd, glow = "transparent", "transparent", "transparent"
            self._icon.set_color(col("textMut"))
            self._label.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
            self._label.setFont(font_ui(11, W_MEDIUM))
        self.setStyleSheet(
            f"DockItem{{background:{bg};border:1px solid {bd};border-radius:10px;}}"
        )

    def enterEvent(self, _e):
        self._hover = True; self._restyle()

    def leaveEvent(self, _e):
        self._hover = False; self._restyle()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.key)


class FloatingDock(QFrame):
    navigate = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._items = {}
        self.setFixedWidth(_COLLAPSED)
        self.setStyleSheet(
            f"FloatingDock{{background:{rgba_str('panel', 0.88)};"
            f"border:1px solid {rgba_str('border', 0.8)};border-radius:18px;}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 14, 8, 12); lay.setSpacing(3)

        # logo row
        logo_row = QHBoxLayout(); logo_row.setContentsMargins(2, 0, 2, 0); logo_row.setSpacing(10)
        logo_row.addWidget(_LogoMark())
        self._brand = QWidget()
        bl = QVBoxLayout(self._brand); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(0)
        t1 = QLabel("A.E.R.I.S"); t1.setFont(font_ui(11, W_BOLD, 1.5))
        t1.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
        t2 = QLabel("JARVIS v6"); t2.setFont(font_ui(8))
        t2.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        bl.addWidget(t1); bl.addWidget(t2)
        logo_row.addWidget(self._brand); logo_row.addStretch(1)
        lay.addLayout(logo_row)

        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{rgba_str('cyan', 0.1)};border:0;")
        lay.addWidget(sep)
        lay.addSpacing(4)

        for entry in DOCK_ITEMS:
            if entry is None:
                s = QFrame(); s.setFixedHeight(1)
                s.setStyleSheet(f"background:{rgba_str('cyan', 0.06)};border:0;")
                lay.addWidget(s)
                continue
            key, label, icon = entry
            it = DockItem(key, label, icon)
            it.clicked.connect(self.navigate)
            self._items[key] = it
            lay.addWidget(it)

        lay.addStretch(1)

        # user card
        sep2 = QFrame(); sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{rgba_str('cyan', 0.08)};border:0;")
        lay.addWidget(sep2)
        user_row = QHBoxLayout(); user_row.setContentsMargins(4, 6, 4, 0); user_row.setSpacing(10)
        av = QLabel("S"); av.setFixedSize(28, 28); av.setAlignment(Qt.AlignCenter)
        av.setFont(font_ui(11, W_BOLD))
        av.setStyleSheet(
            "color:white;border-radius:14px;"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 rgb(168,85,247), stop:1 rgb(255,45,149));"
        )
        user_row.addWidget(av)
        self._user = QWidget()
        ul = QVBoxLayout(self._user); ul.setContentsMargins(0, 0, 0, 0); ul.setSpacing(0)
        un = QLabel("Shivang"); un.setFont(font_ui(11, W_SEMIBOLD))
        un.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
        ur = QLabel("Pro · Admin"); ur.setFont(font_ui(8))
        ur.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        ul.addWidget(un); ul.addWidget(ur)
        user_row.addWidget(self._user); user_row.addStretch(1)
        lay.addLayout(user_row)

        self._anim = QPropertyAnimation(self, b"minimumWidth", self)
        self._anim.setDuration(320)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim2 = QPropertyAnimation(self, b"maximumWidth", self)
        self._anim2.setDuration(320)
        self._anim2.setEasingCurve(QEasingCurve.OutCubic)
        self._set_expanded_widgets(False)

    def set_active(self, key: str):
        for k, it in self._items.items():
            it.set_active(k == key)

    def _set_expanded_widgets(self, on: bool):
        self._brand.setVisible(on)
        self._user.setVisible(on)
        for it in self._items.values():
            it.set_expanded(on)

    def _animate(self, target: int):
        for a in (self._anim, self._anim2):
            a.stop(); a.setStartValue(self.width()); a.setEndValue(target); a.start()

    def enterEvent(self, _e):
        if not self._expanded:
            self._expanded = True
            self._set_expanded_widgets(True)
            border = rgba_str("cyan", 0.2)
            self.setStyleSheet(
                f"FloatingDock{{background:{rgba_str('panel', 0.92)};"
                f"border:1px solid {border};border-radius:18px;}}"
            )
            self._animate(_EXPANDED)

    def leaveEvent(self, _e):
        if self._expanded:
            self._expanded = False
            self._set_expanded_widgets(False)
            self.setStyleSheet(
                f"FloatingDock{{background:{rgba_str('panel', 0.88)};"
                f"border:1px solid {rgba_str('border', 0.8)};border-radius:18px;}}"
            )
            self._animate(_COLLAPSED)
