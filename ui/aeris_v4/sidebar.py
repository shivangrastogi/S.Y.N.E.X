"""Left sidebar — brand, nav sections, brain card, user card."""
from __future__ import annotations

import math
import time
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QIcon
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QPushButton
)

from .theme import C, rgba, inter, mono


SECTIONS = [
    ("NAVIGATION", [
        ("Chat",        "3",    C.CYAN),
        ("History",     None,   None),
        ("Routines",    None,   None),
        ("Automations", None,   None),
    ]),
    ("INTELLIGENCE", [
        ("Brain",       "LIVE", C.GREEN),
        ("Memory",      None,   None),
        ("Training",    None,   None),
    ]),
    ("SYSTEM", [
        ("Settings",    None,   None),
    ]),
]


class _NavItem(QPushButton):
    clicked_key = pyqtSignal(str)

    def __init__(self, key: str, badge: str | None, badge_color: QColor | None, parent=None):
        super().__init__(parent)
        self.key = key
        self.badge = badge
        self.badge_color = badge_color
        self._active = False
        self._hovered = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self.setMouseTracking(True)
        self.clicked.connect(lambda: self.clicked_key.emit(self.key))
        self.setFlat(True)

    def setActive(self, v: bool):
        self._active = v
        self.update()

    def enterEvent(self, _): self._hovered = True; self.update()
    def leaveEvent(self, _): self._hovered = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 2, 0, -2)

        # background
        if self._active:
            p.setPen(QPen(rgba(C.CYAN, 0.38), 1))
            p.setBrush(rgba(C.CYAN, 0.10))
        elif self._hovered:
            p.setPen(QPen(rgba(C.CYAN, 0.15), 1))
            p.setBrush(rgba(C.CYAN, 0.05))
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.transparent)
        p.drawRoundedRect(r, 10, 10)

        # icon placeholder (simple rounded square)
        icon_col = C.CYAN if self._active else (rgba(C.WHITE, 0.7) if self._hovered else C.TEXT_MUT)
        p.setPen(QPen(icon_col, 1.4))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(16, r.center().y() - 8, 16, 16, 3, 3)

        # label
        text_col = C.TEXT_PRI if self._active else (QColor(210, 225, 240) if self._hovered else C.TEXT_SEC)
        p.setPen(text_col)
        p.setFont(inter(13, 700 if self._active else 500))
        p.drawText(44, 0, r.width() - 90, r.height(), Qt.AlignLeft | Qt.AlignVCenter, self.key)

        # badge
        if self.badge:
            badge_col = self.badge_color or C.TEXT_SEC
            fm = p.fontMetrics()
            text = self.badge
            bw = fm.horizontalAdvance(text) + 12
            bh = 16
            bx = r.right() - bw - 12
            by = r.center().y() - bh / 2
            p.setPen(QPen(rgba(badge_col, 0.4), 1))
            p.setBrush(rgba(badge_col, 0.15))
            p.drawRoundedRect(bx, by, bw, bh, 6, 6)
            p.setPen(badge_col)
            p.setFont(mono(9, 700))
            p.drawText(bx, by, bw, bh, Qt.AlignCenter, text)


class Sidebar(QWidget):
    tab_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = "Chat"
        self.setFixedWidth(240)
        self.setAutoFillBackground(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 20)
        root.setSpacing(4)

        # Brand row
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        self._logo = _AnimatedLogo()
        brand_row.addWidget(self._logo)
        brand_col = QVBoxLayout(); brand_col.setSpacing(2); brand_col.setContentsMargins(0, 0, 0, 0)
        name = QLabel("A.E.R.I.S"); name.setFont(inter(13, 700))
        name.setStyleSheet(f"color: {C.TEXT_PRI.name()}; letter-spacing: 1.8px;")
        sub = QLabel("Assistant Core"); sub.setFont(inter(10, 500))
        sub.setStyleSheet(f"color: {C.TEXT_MUT.name()}; letter-spacing: 0.4px;")
        brand_col.addWidget(name); brand_col.addWidget(sub)
        brand_row.addLayout(brand_col)
        brand_row.addStretch(1)
        root.addLayout(brand_row)
        root.addSpacing(14)

        # Nav items
        self._items: dict[str, _NavItem] = {}
        for section, items in SECTIONS:
            header = QLabel(section); header.setFont(mono(9, 700))
            header.setStyleSheet(f"color: {C.TEXT_MUT.name()}; letter-spacing: 1.8px; padding: 8px 12px 4px 12px;")
            root.addWidget(header)
            for key, badge, badge_color in items:
                it = _NavItem(key, badge, badge_color)
                it.clicked_key.connect(self._on_nav)
                self._items[key] = it
                root.addWidget(it)
            root.addSpacing(4)

        self._items[self._active].setActive(True)
        root.addStretch(1)

        # Brain card
        root.addWidget(_BrainCard())
        root.addSpacing(6)
        # User card
        root.addWidget(_UserCard("Shivang", "Pro • Admin"))

    def _on_nav(self, key: str):
        if key == self._active:
            return
        self._items[self._active].setActive(False)
        self._items[key].setActive(True)
        self._active = key
        self.tab_changed.emit(key)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), C.PANEL)
        p.setPen(QPen(C.BORDER, 1))
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())


class _AnimatedLogo(QWidget):
    """Mini animated arc reactor for brand."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self._start = time.monotonic()
        t = QTimer(self); t.timeout.connect(self.update); t.start(30)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = (time.monotonic() - self._start) * 1000
        center = QPointF(self.width()/2, self.height()/2)

        # outer ring (spinning)
        a1 = (t / 6000) * 360 % 360
        p.save(); p.translate(center); p.rotate(a1)
        p.setPen(QPen(rgba(C.CYAN, 0.6), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), 14, 14)
        p.restore()

        # inner ring (counter-rotating)
        a2 = -((t / 4000) * 360 % 360)
        p.save(); p.translate(center); p.rotate(a2)
        p.setPen(QPen(rgba(C.CYAN, 0.4), 1))
        p.drawEllipse(QPointF(0, 0), 9, 9)
        p.restore()

        # core
        p.setPen(Qt.NoPen)
        glow = QColor(C.CYAN); glow.setAlphaF(0.4)
        p.setBrush(glow)
        p.drawEllipse(center, 6, 6)
        p.setBrush(C.CYAN)
        p.drawEllipse(center, 3.5, 3.5)


class _BrainCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(False)
        self.setFixedHeight(76)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12); v.setSpacing(4)

        h = QHBoxLayout(); h.setSpacing(5)
        lbl = QLabel("BRAIN"); lbl.setFont(mono(10, 700))
        lbl.setStyleSheet(f"color: {C.TEXT_SEC.name()}; letter-spacing: 1.5px;")
        h.addWidget(lbl); h.addStretch(1)
        self._blink = _BlinkDot(C.GREEN); h.addWidget(self._blink)
        active = QLabel("ACTIVE"); active.setFont(mono(9, 700))
        active.setStyleSheet(f"color: {C.GREEN.name()};")
        h.addWidget(active)
        v.addLayout(h)

        stats = QLabel("21 intents • 301 patterns"); stats.setFont(mono(10, 400))
        stats.setStyleSheet(f"color: {C.TEXT_PRI.name()};")
        v.addWidget(stats)
        acc = QLabel("99.8% accuracy"); acc.setFont(mono(10, 400))
        acc.setStyleSheet(f"color: {C.CYAN.name()};")
        v.addWidget(acc)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(C.BORDER, 1))
        p.setBrush(C.CARD)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)


class _UserCard(QFrame):
    def __init__(self, name: str, role: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self); h.setContentsMargins(10, 10, 10, 10); h.setSpacing(10)

        avatar = _Avatar(name[0])
        h.addWidget(avatar)
        col = QVBoxLayout(); col.setSpacing(2); col.setContentsMargins(0, 0, 0, 0)
        n = QLabel(name); n.setFont(inter(12, 700)); n.setStyleSheet(f"color: {C.TEXT_PRI.name()};")
        r = QLabel(role); r.setFont(inter(10, 400)); r.setStyleSheet(f"color: {C.TEXT_MUT.name()};")
        col.addWidget(n); col.addWidget(r)
        h.addLayout(col); h.addStretch(1)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(C.BORDER, 1))
        p.setBrush(C.CARD)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)


class _Avatar(QWidget):
    def __init__(self, letter: str, parent=None):
        super().__init__(parent)
        self.letter = letter
        self.setFixedSize(32, 32)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        glow = QColor(C.PURPLE); glow.setAlphaF(0.4)
        p.setPen(Qt.NoPen); p.setBrush(glow)
        p.drawEllipse(self.rect())
        p.setBrush(C.PURPLE)
        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
        p.setPen(Qt.white)
        p.setFont(inter(13, 700))
        p.drawText(self.rect(), Qt.AlignCenter, self.letter)


class _BlinkDot(QWidget):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(8, 8)
        self._start = time.monotonic()
        t = QTimer(self); t.timeout.connect(self.update); t.start(80)

    def paintEvent(self, _):
        phase = (time.monotonic() - self._start) * 2 * math.pi / 2.0
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(phase))
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        glow = QColor(self._color); glow.setAlphaF(alpha * 0.6)
        p.setPen(Qt.NoPen); p.setBrush(glow)
        p.drawEllipse(self.rect())
        c = QColor(self._color); c.setAlphaF(alpha)
        p.setBrush(c)
        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
