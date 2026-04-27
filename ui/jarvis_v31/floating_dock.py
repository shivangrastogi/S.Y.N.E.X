"""JARVIS v3.1 floating dock — overlay nav rail.

Mirrors jv3-dock.jsx::FloatingDock:
  - Pinned 12px from left edge, vertically centered
  - 56px wide collapsed, 240px when hovered (cubic-bezier 320ms)
  - Items grouped: core (home/chat/auto) → intel (brain/memory) → system
  - Animated brand mark on top, gradient avatar on bottom
  - Active item: cyan tint bg + cyan border + edge trace + glow

The brand mark and the avatar use ABSOLUTE positioning inside their row
widgets — never move when text labels appear/disappear. This avoids the
QHBoxLayout reflow jitter that plagued the previous implementation.

It's an overlay (lives ABOVE the center column, not inside it), so the
parent must use it with `setParent()` + `raise_()` after layout instead
of via a layout slot.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import (
    QEasingCurve, QPoint, QPointF, QRectF, QTimer, QVariantAnimation, Qt,
    pyqtSignal
)
from PyQt5.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
)
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .tokens import J, inter, mono, rgba


# ─── Item config ─────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class _Item:
    key: str
    label: str
    icon: str
    section: str   # 'core' / 'intel' / 'system'


DOCK_ITEMS: list[Optional[_Item]] = [
    _Item("home",     "Home",          "home",     "core"),
    _Item("chat",     "Conversations", "chat",     "core"),
    _Item("auto",     "Automations",   "auto",     "core"),
    None,                                                       # divider
    _Item("brain",    "Brain",         "brain",    "intel"),
    _Item("memory",   "Memory",        "memory",   "intel"),
    None,                                                       # divider
    _Item("system",   "System",        "system",   "system"),
    _Item("settings", "Settings",      "settings", "system"),
]

COLLAPSED_W = 56
EXPANDED_W  = 240
ANIM_MS     = 320

# Layout constants used by both row widgets and the items.
# Dock has 8px horizontal padding inside its rounded card. So the inner content
# area is COLLAPSED_W - 16 = 40px wide when collapsed. We center 30px brand and
# 28px avatar inside this 40px box, giving the same x-coordinate forever.
_PAD_X      = 8                   # dock-left padding (matches root margins)
_INNER_W    = COLLAPSED_W - 2 * _PAD_X    # = 40 — collapsed inner width
_BRAND_X    = (_INNER_W - 30) // 2        # = 5
_AVATAR_X   = (_INNER_W - 28) // 2        # = 6
_ICON_X     = (_INNER_W - 18) // 2        # = 11 (used by _DockItem)
_TEXT_GAP   = 10                  # gap between mark/avatar and the text block


# ─── Painted icons (one per dock key) ────────────────────────────────── #

def _draw_icon(p: QPainter, name: str, color: QColor) -> None:
    pen = QPen(color, 1.4)
    pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen); p.setBrush(Qt.NoBrush)

    if name == "home":
        path = QPainterPath()
        path.moveTo(2, 7); path.lineTo(8, 2); path.lineTo(14, 7)
        path.lineTo(14, 14); path.lineTo(10, 14); path.lineTo(10, 9)
        path.lineTo(6, 9); path.lineTo(6, 14); path.lineTo(2, 14)
        path.closeSubpath()
        p.drawPath(path)

    elif name == "chat":
        p.drawRoundedRect(2, 3, 12, 8, 1, 1)
        p.drawLine(QPointF(5, 11), QPointF(2.5, 13.5))

    elif name == "auto":
        # Cog: small circle + 4 spokes (NSEW)
        p.drawEllipse(QPointF(8, 8), 3, 3)
        for x1, y1, x2, y2 in ((8,2,8,5),(8,11,8,14),(2,8,5,8),(11,8,14,8)):
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    elif name == "brain":
        p.drawEllipse(QPointF(8, 7), 4, 5)
        p.drawLine(QPointF(6, 12), QPointF(6, 14))
        p.drawLine(QPointF(10, 12), QPointF(10, 14))
        p.drawLine(QPointF(5, 7), QPointF(11, 7))

    elif name == "memory":
        p.drawRoundedRect(3, 4, 10, 8, 1.5, 1.5)
        # vertical pin notches
        for x in (6, 10):
            p.drawLine(QPointF(x, 4), QPointF(x, 2.5))
            p.drawLine(QPointF(x, 12), QPointF(x, 13.5))
        p.drawLine(QPointF(3, 8), QPointF(13, 8))

    elif name == "system":
        p.drawRoundedRect(2, 3, 12, 9, 1.5, 1.5)
        # base + foot
        p.drawLine(QPointF(5, 14), QPointF(11, 14))
        p.drawLine(QPointF(8, 12), QPointF(8, 14))

    elif name == "settings":
        p.drawEllipse(QPointF(8, 8), 2.5, 2.5)
        # 8 spokes around the gear
        for ang in (0, 45, 90, 135, 180, 225, 270, 315):
            r = math.radians(ang)
            x1 = 8 + math.cos(r) * 5;   y1 = 8 + math.sin(r) * 5
            x2 = 8 + math.cos(r) * 6.5; y2 = 8 + math.sin(r) * 6.5
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    else:
        p.drawEllipse(QPointF(8, 8), 4, 4)


# ─── Item button ─────────────────────────────────────────────────────── #

class _DockItem(QPushButton):
    clicked_key = pyqtSignal(str)

    def __init__(self, item: _Item, parent=None):
        super().__init__(parent)
        self.item = item
        self._active = False
        self._hover = False
        self._expanded = False

        self.setFixedHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setFlat(True)
        self.clicked.connect(lambda: self.clicked_key.emit(self.item.key))

    def setActive(self, v): self._active = v; self.update()
    def setExpanded(self, v):
        self._expanded = v
        self.setToolTip(self.item.label if not v else "")
        self.update()

    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 1, 0, -1)

        # ── background pill ─────────────────────────────────────────
        if self._active:
            p.setPen(QPen(rgba(J.CYAN, 0.35), 1))
            p.setBrush(rgba(J.CYAN, 0.09))
        elif self._hover:
            p.setPen(QPen(rgba(J.CYAN, 0.15), 1))
            p.setBrush(rgba(J.CYAN, 0.05))
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.transparent)
        p.drawRoundedRect(r, 10, 10)

        # ── active edge trace (vertical line on left side) ─────────
        if self._active:
            grad = QLinearGradient(0, r.top() + r.height() * 0.2,
                                   0, r.bottom() - r.height() * 0.2)
            grad.setColorAt(0.0, rgba(J.CYAN, 0))
            grad.setColorAt(0.5, J.CYAN)
            grad.setColorAt(1.0, rgba(J.CYAN, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(0, r.top() + r.height() * 0.2, 2,
                                     r.height() * 0.6), 1, 1)

        # ── icon ───────────────────────────────────────────────────
        accent = (
            J.CYAN if self._active
            else QColor(0, 212, 255, int(255 * 0.85)) if self._hover
            else J.TEXT_MUT
        )
        # Fixed x — icon never moves during expand/collapse animation.
        ix = _ICON_X
        p.save()
        p.translate(ix, (self.height() - 18) / 2 + 1)
        _draw_icon(p, self.item.icon, accent)
        p.restore()

        # ── label (only when expanded) ─────────────────────────────
        if self._expanded:
            text_col = (
                J.TEXT_PRI if self._active
                else QColor(210, 225, 240) if self._hover
                else J.TEXT_SEC
            )
            p.setPen(text_col)
            p.setFont(inter(13, 700 if self._active else 500))
            label_x = ix + 18 + _TEXT_GAP   # icon end + gap = 39
            p.drawText(label_x, 0, self.width() - label_x - 6, self.height(),
                       Qt.AlignVCenter | Qt.AlignLeft, self.item.label)

        # ── hover edge dot (right side) ────────────────────────────
        if self._hover and not self._active:
            p.setPen(Qt.NoPen)
            p.setBrush(rgba(J.CYAN, 0.6))
            p.drawEllipse(QPointF(self.width() - 10, self.height() / 2), 2, 2)


# ─── Brand mark + avatar (painted children) ──────────────────────────── #

class _BrandMark(QWidget):
    """30x30 reactor — outer ring spins clockwise, inner ring counter."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self._start = time.monotonic()
        t = QTimer(self); t.timeout.connect(self.update); t.start(33)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        center = QPointF(self.width() / 2, self.height() / 2)
        t_ms = (time.monotonic() - self._start) * 1000

        a1 = (t_ms / 6000) * 360 % 360
        p.save(); p.translate(center); p.rotate(a1)
        p.setPen(QPen(rgba(J.CYAN, 0.6), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), 14, 14)
        p.restore()

        a2 = -((t_ms / 4000) * 360 % 360)
        p.save(); p.translate(center); p.rotate(a2)
        p.setPen(QPen(rgba(J.CYAN, 0.4), 1))
        p.drawEllipse(QPointF(0, 0), 9, 9)
        p.restore()

        p.setPen(Qt.NoPen)
        p.setBrush(rgba(J.CYAN, 0.4))
        p.drawEllipse(center, 6, 6)
        p.setBrush(J.CYAN)
        p.drawEllipse(center, 4, 4)


class _Avatar(QWidget):
    """28x28 gradient circle (purple→magenta) with a white letter."""
    def __init__(self, letter: str, parent=None):
        super().__init__(parent)
        self.letter = letter
        self.setFixedSize(28, 28)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, J.PURPLE)
        grad.setColorAt(1.0, J.MAGENTA)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(self.rect())
        p.setPen(Qt.white)
        p.setFont(inter(12, 700))
        p.drawText(self.rect(), Qt.AlignCenter, self.letter)


# ─── Brand row + user row (absolute positioning — no layout reflow) ──── #

class _BrandRow(QWidget):
    """Brand mark at fixed (_BRAND_X, 2); text block to its right.

    The widget is added to the dock's QVBoxLayout so it stretches to the dock
    width, but its children use `move()` and stay at fixed pixel positions.
    Visibility of the text block is toggled — never re-laid-out.
    """
    HEIGHT = 34

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)

        self._mark = _BrandMark(self)
        self._mark.move(_BRAND_X, 2)

        self._text = QWidget(self)
        tl = QVBoxLayout(self._text)
        tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(0)
        n = QLabel("A.E.R.I.S")
        n.setFont(inter(12, 700))
        n.setStyleSheet(f"color: {J.TEXT_PRI.name()}; letter-spacing: 1.5px;")
        s = QLabel("JARVIS v3.0")
        s.setFont(inter(9, 500))
        s.setStyleSheet(f"color: {J.TEXT_MUT.name()}; letter-spacing: 0.5px;")
        tl.addWidget(n); tl.addWidget(s)
        self._text.adjustSize()
        self._text.move(_BRAND_X + 30 + _TEXT_GAP, 0)
        self._text.setVisible(False)

    def set_text_visible(self, v: bool) -> None:
        self._text.setVisible(v)


class _UserRow(QWidget):
    """Avatar at fixed (_AVATAR_X, 4); text block to its right.

    Emits `clicked` when the user presses anywhere on the row — used to
    toggle the inline options panel above it.
    """
    HEIGHT = 38
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

        self._avatar = _Avatar("S", self)
        self._avatar.move(_AVATAR_X, 4)

        self._text = QWidget(self)
        tl = QVBoxLayout(self._text)
        tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(1)
        un = QLabel("Shivang")
        un.setFont(inter(12, 600))
        un.setStyleSheet(f"color: {J.TEXT_PRI.name()};")
        ur_l = QLabel("Pro · Admin")
        ur_l.setFont(inter(9, 400))
        ur_l.setStyleSheet(f"color: {J.TEXT_MUT.name()};")
        tl.addWidget(un); tl.addWidget(ur_l)
        self._text.adjustSize()
        self._text.move(_AVATAR_X + 28 + _TEXT_GAP, 4)
        self._text.setVisible(False)

        # Chevron — visible only when text is shown, painted in paintEvent
        self._chevron_visible = False

    def set_text_visible(self, v: bool) -> None:
        self._text.setVisible(v)
        self._chevron_visible = v
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def paintEvent(self, _):
        if not self._chevron_visible:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Small chevron-up glyph at the right edge to hint click target.
        p.setPen(QPen(QColor(J.TEXT_MUT), 1.4, Qt.SolidLine, Qt.RoundCap))
        cx = self.width() - 14
        cy = self.height() / 2
        p.drawLine(QPointF(cx - 4, cy + 2), QPointF(cx, cy - 2))
        p.drawLine(QPointF(cx, cy - 2), QPointF(cx + 4, cy + 2))


class _OptionsPanel(QWidget):
    """Inline options panel that slides up above the user row when profile
    is clicked. Hosts a few action rows: Account, Settings, Sign out.
    """
    HEIGHT = 132
    action = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self.setVisible(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(2)

        for key, label, icon in (
            ("account",  "Account",       "memory"),
            ("settings", "Preferences",   "settings"),
            ("theme",    "Switch Theme",  "auto"),
            ("logout",   "Sign Out",      "system"),
        ):
            row = _OptionsItem(key, label, icon)
            row.clicked_key.connect(self.action.emit)
            lay.addWidget(row)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        bg = QColor(13, 21, 37); bg.setAlphaF(0.96)
        p.setPen(QPen(rgba(J.CYAN, 0.22), 1))
        p.setBrush(bg)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)


class _OptionsItem(QPushButton):
    """A single row inside the options panel — icon + label, hover highlight."""
    clicked_key = pyqtSignal(str)

    def __init__(self, key: str, label: str, icon: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._label = label
        self._icon = icon
        self._hover = False
        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.clicked.connect(lambda: self.clicked_key.emit(self._key))

    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        if self._hover:
            p.setPen(QPen(rgba(J.CYAN, 0.18), 1))
            p.setBrush(rgba(J.CYAN, 0.06))
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(Qt.transparent)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 7, 7)

        accent = J.CYAN if self._hover else J.TEXT_MUT
        p.save(); p.translate(8, (self.height() - 18) / 2 + 1)
        _draw_icon(p, self._icon, accent)
        p.restore()

        p.setPen(J.TEXT_PRI if self._hover else J.TEXT_SEC)
        p.setFont(inter(11, 500))
        p.drawText(34, 0, self.width() - 38, self.height(),
                   Qt.AlignVCenter | Qt.AlignLeft, self._label)


# ─── Dock root ───────────────────────────────────────────────────────── #

class FloatingDock(QWidget):
    """Overlay nav rail. Caller sets the parent and absolute position.

    Width animates 56 ↔ 240 on mouse enter/leave. Emits `tab_changed(key)`
    and `profile_action(action_key)`.
    """

    tab_changed    = pyqtSignal(str)
    profile_action = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._active = "chat"
        self._options_open = False
        self.setFixedWidth(COLLAPSED_W)
        self.setMinimumHeight(480)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        # Layout
        root = QVBoxLayout(self)
        root.setContentsMargins(_PAD_X, 14, _PAD_X, 14)
        root.setSpacing(3)

        # ── Brand row (absolute positioning inside) ─────────────────
        self._brand_row = _BrandRow()
        root.addWidget(self._brand_row)

        # ── Brand → items separator ────────────────────────────────
        self._brand_sep = _ThinDivider()
        root.addWidget(self._brand_sep)

        # ── Items + dividers ───────────────────────────────────────
        self._items: dict[str, _DockItem] = {}
        self._dividers: list[_ThinDivider] = []
        for x in DOCK_ITEMS:
            if x is None:
                d = _ThinDivider()
                self._dividers.append(d)
                root.addWidget(d)
            else:
                btn = _DockItem(x)
                btn.clicked_key.connect(self._on_nav)
                self._items[x.key] = btn
                root.addWidget(btn)

        if self._active in self._items:
            self._items[self._active].setActive(True)

        root.addStretch(1)

        # ── User card ───────────────────────────────────────────────
        self._user_sep = _ThinDivider()
        root.addWidget(self._user_sep)

        self._user_row = _UserRow()
        self._user_row.clicked.connect(self._toggle_options)
        root.addWidget(self._user_row)

        # ── Options panel (overlay child, NOT in the layout) ───────
        # Lives as a free-floating child positioned above the user row when
        # toggled. Keeps the layout / dock height stable.
        self._options = _OptionsPanel(self)
        self._options.action.connect(self._on_profile_action)

        # ── Width animation ────────────────────────────────────────
        self._anim = QVariantAnimation(self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setDuration(ANIM_MS)
        self._anim.valueChanged.connect(self._set_width)

    # ── Hover triggers expand ─────────────────────────────────────
    def enterEvent(self, _):
        self._set_expanded(True)

    def leaveEvent(self, _):
        self._set_expanded(False)

    def _set_expanded(self, v: bool):
        if v == self._expanded:
            return
        self._expanded = v
        for it in self._items.values():
            it.setExpanded(v)
        # On collapse: hide text + options immediately so nothing renders
        # in a too-narrow panel. Show is handled in _set_width once the dock
        # reaches the threshold width.
        if not v:
            self._brand_row.set_text_visible(False)
            self._user_row.set_text_visible(False)
            if self._options_open:
                self._options.hide()
                self._options_open = False
        # Animate width
        self._anim.stop()
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(EXPANDED_W if v else COLLAPSED_W)
        self._anim.start()

    def _set_width(self, w):
        try:
            iw = int(w)
            self.setFixedWidth(iw)
            # Reveal brand/user text only once the dock is wide enough.
            threshold = COLLAPSED_W + (EXPANDED_W - COLLAPSED_W) * 0.55
            show = self._expanded and iw >= threshold
            self._brand_row.set_text_visible(show)
            self._user_row.set_text_visible(show)
        except (TypeError, ValueError):
            pass

    def _on_nav(self, key: str):
        if key == self._active or key not in self._items:
            return
        self._items[self._active].setActive(False)
        self._items[key].setActive(True)
        self._active = key
        self.tab_changed.emit(key)

    # ── Profile click → toggle options ──────────────────────────
    def _toggle_options(self):
        if not self._expanded:
            return                  # ignore taps when collapsed
        self._options_open = not self._options_open
        if self._options_open:
            # Position the panel just above the user row, full inner width.
            ur_top = self._user_row.mapTo(self, QPoint(0, 0)).y()
            inner_w = self.width() - 2 * _PAD_X
            self._options.setFixedWidth(inner_w)
            self._options.move(_PAD_X,
                               ur_top - self._options.height() - 6)
            self._options.show()
            self._options.raise_()
        else:
            self._options.hide()

    def _on_profile_action(self, key: str):
        self._options_open = False
        self._options.hide()
        self.profile_action.emit(key)

    # ── Painting (rounded glass card with shadow) ─────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        bg = QColor(J.PANEL); bg.setAlphaF(0.88)
        p.setPen(QPen(rgba(J.CYAN, 0.20) if self._expanded
                      else rgba(J.BORDER, 0.8), 1))
        p.setBrush(bg)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 18, 18)


class _ThinDivider(QWidget):
    """1px translucent cyan divider — used between sections in the dock."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(
            f"background: rgba({J.CYAN.red()},{J.CYAN.green()},{J.CYAN.blue()},0.06);"
        )
