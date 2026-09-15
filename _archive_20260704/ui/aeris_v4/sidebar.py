"""Left sidebar — brand, nav sections, brain card, user card.

Mirrors aeris-sidebar.jsx:
  - 240px expanded ↔ 62px collapsed (cubic-bezier-like animation, 320ms)
  - 8 distinct painted nav icons (chat, history, routines, automations,
    brain, memory, training, settings)
  - Animated cyan scanline at the top edge
  - Active item: cyan border + cyan tint bg + glow
  - Brain/user cards hidden in collapsed mode
"""
from __future__ import annotations

import math
import time
from typing import Optional

from PyQt5.QtCore import (
    QEasingCurve, QPointF, QRect, QSize, QTimer, QVariantAnimation, Qt, pyqtSignal
)
from PyQt5.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)

from .theme import C, inter, mono, rgba


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

EXPANDED_WIDTH  = 240
COLLAPSED_WIDTH = 62
ANIM_MS         = 320


# ─── Painted icons (one per nav key) ─────────────────────────────────────── #
#
# Each draws into a 16x16 box. `color` is a QColor for the stroke. We use
# QPainterPath / drawLine / drawEllipse rather than QSvgRenderer because
# bundling SVG files would add asset-management complexity for ~8 tiny icons.

def _draw_icon(p: QPainter, name: str, color: QColor) -> None:
    pen = QPen(color, 1.3)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    if name == "Chat":
        p.drawRoundedRect(2, 3, 12, 8, 1, 1)
        # speech-tail: little notch at lower-left
        path = QPainterPath()
        path.moveTo(5, 11); path.lineTo(2, 14); path.lineTo(2, 11)
        p.drawPath(path)

    elif name == "History":
        p.drawEllipse(QPointF(8, 8), 5, 5)
        p.drawLine(QPointF(8, 5), QPointF(8, 8))
        p.drawLine(QPointF(8, 8), QPointF(10, 10))

    elif name == "Routines":
        # two opposing arcs ≈ refresh/cycle glyph
        p.drawArc(3, 3, 10, 10, 0 * 16, 180 * 16)
        p.drawArc(3, 3, 10, 10, 180 * 16, 180 * 16)
        # arrowheads (tiny ticks)
        p.drawLine(QPointF(13, 6), QPointF(11, 4))
        p.drawLine(QPointF(3, 10),  QPointF(5, 12))

    elif name == "Automations":
        p.drawRoundedRect(3, 3, 4, 4, 1, 1)
        p.drawRoundedRect(9, 9, 4, 4, 1, 1)
        # connectors
        p.drawLine(QPointF(7, 5),  QPointF(11, 5))
        p.drawLine(QPointF(11, 5), QPointF(11, 9))
        p.drawLine(QPointF(5, 7),  QPointF(5, 11))
        p.drawLine(QPointF(5, 11), QPointF(9, 11))

    elif name == "Brain":
        # Tall ellipse + horizontal "fold" lines
        path = QPainterPath()
        path.addEllipse(QPointF(8, 8), 4, 5)
        p.drawPath(path)
        p.drawLine(QPointF(8, 3), QPointF(8, 13))
        p.drawLine(QPointF(4, 6), QPointF(12, 6))
        p.drawLine(QPointF(4, 10), QPointF(12, 10))

    elif name == "Memory":
        # Drive box + lock shackle on top
        p.drawRoundedRect(3, 5, 10, 7, 1, 1)
        # arc on top (lock)
        p.drawArc(6, 2, 4, 5, 0, 180 * 16)
        p.drawLine(QPointF(6, 9), QPointF(10, 9))

    elif name == "Training":
        # Triangle + center bar
        path = QPainterPath()
        path.moveTo(3, 12); path.lineTo(8, 4); path.lineTo(13, 12); path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(8, 8), QPointF(8, 12))

    elif name == "Settings":
        p.drawEllipse(QPointF(8, 8), 2.5, 2.5)
        for ang in (0, 45, 90, 135, 180, 225, 270, 315):
            rad = math.radians(ang)
            x1 = 8 + math.cos(rad) * 5; y1 = 8 + math.sin(rad) * 5
            x2 = 8 + math.cos(rad) * 6.5; y2 = 8 + math.sin(rad) * 6.5
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    else:
        p.drawRoundedRect(3, 3, 10, 10, 2, 2)


# ─── Nav item (icon + label + badge) ─────────────────────────────────────── #

class _NavItem(QPushButton):
    clicked_key = pyqtSignal(str)

    def __init__(self, key: str, badge: Optional[str], badge_color: Optional[QColor],
                 parent=None):
        super().__init__(parent)
        self.key         = key
        self.badge       = badge
        self.badge_color = badge_color
        self._active     = False
        self._hovered    = False
        self._collapsed  = False

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self.setMouseTracking(True)
        self.setFlat(True)
        self.clicked.connect(lambda: self.clicked_key.emit(self.key))

    def setActive(self, v: bool) -> None:
        self._active = v
        self.update()

    def setCollapsed(self, v: bool) -> None:
        self._collapsed = v
        self.setToolTip(self.key if v else "")
        self.update()

    def enterEvent(self, _):
        self._hovered = True
        self.update()

    def leaveEvent(self, _):
        self._hovered = False
        self.update()

    # ------------------------------------------------------------------ #

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 2, 0, -2)

        # ── background pill ────────────────────────────────────────────
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

        # ── glow under active item ────────────────────────────────────
        # Soft cyan halo via 2 concentric translucent rounded rects.
        if self._active:
            for dr, op in ((6, 0.10), (3, 0.16)):
                glow_pen = QPen(rgba(C.CYAN, op), 1)
                p.setPen(glow_pen); p.setBrush(Qt.NoBrush)
                gr = r.adjusted(-dr, -dr, dr, dr)
                p.drawRoundedRect(gr, 10 + dr, 10 + dr)

        # ── icon ──────────────────────────────────────────────────────
        icon_col = (
            C.CYAN if self._active
            else QColor(200, 220, 240, int(255 * 0.9)) if self._hovered
            else C.TEXT_MUT
        )
        if self._collapsed:
            ix = (self.width() - 16) / 2
        else:
            ix = 12
        p.save()
        p.translate(ix, r.center().y() - 8)
        _draw_icon(p, self.key, icon_col)
        p.restore()

        # In collapsed mode we stop here — no label, no badge.
        if self._collapsed:
            return

        # ── label ─────────────────────────────────────────────────────
        text_col = (
            C.TEXT_PRI if self._active
            else QColor(210, 225, 240) if self._hovered
            else C.TEXT_SEC
        )
        p.setPen(text_col)
        p.setFont(inter(13, 700 if self._active else 500))
        p.drawText(40, 0, r.width() - 80, r.height(),
                   Qt.AlignLeft | Qt.AlignVCenter, self.key)

        # ── badge ─────────────────────────────────────────────────────
        if self.badge:
            badge_col = self.badge_color or C.TEXT_SEC
            p.setFont(mono(9, 700))
            fm = p.fontMetrics()
            bw = fm.horizontalAdvance(self.badge) + 12
            bh = 16
            bx = r.right() - bw - 12
            by = r.center().y() - bh / 2
            p.setPen(QPen(rgba(badge_col, 0.4), 1))
            p.setBrush(rgba(badge_col, 0.15))
            p.drawRoundedRect(int(bx), int(by), bw, bh, 6, 6)
            p.setPen(badge_col)
            p.drawText(int(bx), int(by), bw, bh, Qt.AlignCenter, self.badge)


# ─── Section header label (hides itself in collapsed mode) ──────────────── #

class _SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(mono(9, 700))
        self.setStyleSheet(
            f"color: {C.TEXT_MUT.name()}; letter-spacing: 1.8px;"
            f"padding: 8px 12px 4px 12px;"
        )


# ─── Sidebar root ──────────────────────────────────────────────────────── #

class Sidebar(QWidget):
    tab_changed = pyqtSignal(str)
    collapsed_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = "Chat"
        self._collapsed = False
        self.setFixedWidth(EXPANDED_WIDTH)
        self.setAutoFillBackground(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 20)
        root.setSpacing(4)
        self._root_layout = root

        # Brand row
        self._brand_row = QWidget()
        brand_lay = QHBoxLayout(self._brand_row)
        brand_lay.setSpacing(12)
        brand_lay.setContentsMargins(0, 0, 0, 0)
        self._logo = _AnimatedLogo()
        brand_lay.addWidget(self._logo)
        self._brand_text = QWidget()
        bt_col = QVBoxLayout(self._brand_text)
        bt_col.setSpacing(2); bt_col.setContentsMargins(0, 0, 0, 0)
        name = QLabel("A.E.R.I.S"); name.setFont(inter(13, 700))
        name.setStyleSheet(f"color: {C.TEXT_PRI.name()}; letter-spacing: 1.8px;")
        sub = QLabel("Assistant Core"); sub.setFont(inter(10, 500))
        sub.setStyleSheet(f"color: {C.TEXT_MUT.name()}; letter-spacing: 0.4px;")
        bt_col.addWidget(name); bt_col.addWidget(sub)
        brand_lay.addWidget(self._brand_text)
        brand_lay.addStretch(1)
        root.addWidget(self._brand_row)
        root.addSpacing(14)

        # Nav sections
        self._items: dict[str, _NavItem] = {}
        self._section_labels: list[_SectionLabel] = []
        for section, items in SECTIONS:
            header = _SectionLabel(section)
            self._section_labels.append(header)
            root.addWidget(header)
            for key, badge, badge_color in items:
                it = _NavItem(key, badge, badge_color)
                it.clicked_key.connect(self._on_nav)
                self._items[key] = it
                root.addWidget(it)
            root.addSpacing(4)

        self._items[self._active].setActive(True)
        root.addStretch(1)

        # Brain card + user card (kept as instance attrs so we can hide them).
        self._brain_card = _BrainCard()
        root.addWidget(self._brain_card)
        root.addSpacing(6)
        self._user_card = _UserCard("Shivang", "Pro • Admin")
        root.addWidget(self._user_card)

        # Scanline animation phase (drawn in paintEvent; just needs a tick).
        self._scan_start = time.monotonic()
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self.update)
        self._scan_timer.start(50)

        # Width animation
        self._anim = QVariantAnimation(self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setDuration(ANIM_MS)
        self._anim.valueChanged.connect(self._set_width)

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def set_collapsed(self, v: bool) -> None:
        if v == self._collapsed:
            return
        self._collapsed = v

        # Toggle label/badge visibility on every nav item
        for it in self._items.values():
            it.setCollapsed(v)
        for lbl in self._section_labels:
            lbl.setVisible(not v)
        self._brand_text.setVisible(not v)
        self._brain_card.setVisible(not v)
        self._user_card.setVisible(not v)

        # Animate width
        start = self.width()
        end = COLLAPSED_WIDTH if v else EXPANDED_WIDTH
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

        # Tighten margins when collapsed (matches jsx '20px 10px').
        if v:
            self._root_layout.setContentsMargins(10, 20, 10, 20)
        else:
            self._root_layout.setContentsMargins(16, 20, 16, 20)

        self.collapsed_changed.emit(v)

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def _set_width(self, w):
        try:
            self.setFixedWidth(int(w))
        except (TypeError, ValueError):
            pass

    def _on_nav(self, key: str) -> None:
        if key == self._active:
            return
        self._items[self._active].setActive(False)
        self._items[key].setActive(True)
        self._active = key
        self.tab_changed.emit(key)

    # ------------------------------------------------------------------ #
    #  Painting (panel bg, right border, top scanline)                    #
    # ------------------------------------------------------------------ #

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Solid panel background
        p.fillRect(self.rect(), C.PANEL)

        # Right edge border
        p.setPen(QPen(C.BORDER, 1))
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        # Animated scanline along the top edge (cyan gradient, slides L→R).
        # The jsx uses linear-gradient(90deg, transparent, cyan, transparent)
        # plus aeris-scan 10s. We approximate by drawing a 60px-wide cyan
        # streak whose x-position cycles every 10s.
        elapsed = (time.monotonic() - self._scan_start) % 10.0
        prog = elapsed / 10.0   # 0..1
        streak_w = 60
        x = -streak_w + (self.width() + 2 * streak_w) * prog
        for i in range(streak_w):
            t = abs((i - streak_w / 2) / (streak_w / 2))
            alpha = (1 - t) * 0.12
            p.setPen(QPen(rgba(C.CYAN, alpha), 1))
            p.drawLine(int(x + i), 0, int(x + i), 0)


# ─── Brand mark, brain card, user card, helpers ─────────────────────────── #

class _AnimatedLogo(QWidget):
    """Mini animated arc reactor for the brand mark (32x32)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self._start = time.monotonic()
        t = QTimer(self); t.timeout.connect(self.update); t.start(30)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t_ms = (time.monotonic() - self._start) * 1000
        center = QPointF(self.width() / 2, self.height() / 2)

        # Outer ring (clockwise, 6s period)
        a1 = (t_ms / 6000) * 360 % 360
        p.save(); p.translate(center); p.rotate(a1)
        p.setPen(QPen(rgba(C.CYAN, 0.6), 1.5)); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), 14, 14)
        p.restore()

        # Inner ring (counter-clockwise, 4s period)
        a2 = -((t_ms / 4000) * 360 % 360)
        p.save(); p.translate(center); p.rotate(a2)
        p.setPen(QPen(rgba(C.CYAN, 0.4), 1))
        p.drawEllipse(QPointF(0, 0), 9, 9)
        p.restore()

        # Core
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(C.CYAN, 0.4))
        p.drawEllipse(center, 6, 6)
        p.setBrush(C.CYAN)
        p.drawEllipse(center, 3.5, 3.5)


class _BrainCard(QFrame):
    """Bottom 'BRAIN' card showing intent/pattern counts + accuracy."""
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
        h.addWidget(_BlinkDot(C.GREEN))
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
    """User avatar + name + role."""
    def __init__(self, name: str, role: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self); h.setContentsMargins(10, 10, 10, 10); h.setSpacing(10)

        h.addWidget(_Avatar(name[0]))
        col = QVBoxLayout(); col.setSpacing(2); col.setContentsMargins(0, 0, 0, 0)
        n = QLabel(name); n.setFont(inter(12, 700))
        n.setStyleSheet(f"color: {C.TEXT_PRI.name()};")
        r = QLabel(role); r.setFont(inter(10, 400))
        r.setStyleSheet(f"color: {C.TEXT_MUT.name()};")
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
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(C.PURPLE, 0.4))
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
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(self._color, alpha * 0.6))
        p.drawEllipse(self.rect())
        p.setBrush(rgba(self._color, alpha))
        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
