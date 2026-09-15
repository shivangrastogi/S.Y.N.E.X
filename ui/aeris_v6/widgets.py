"""Shared primitives — icons + atoms (JTag, Pill, StatTile, Card, …).

Ports the small reusable pieces scattered across ``jv3-tokens.jsx``,
``jv3-dock.jsx`` and ``jv5-page-shell.jsx``. Icons are redrawn with QPainter
primitives in a 16×16 space (rather than parsing the SVG path strings) so
they stay crisp at any size and need no asset files.
"""
from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from ui.aeris_v6.tokens import (
    J, W_BOLD, W_MEDIUM, W_SEMIBOLD, ca, col, font_mono, font_ui, rgba_str,
)


# ── icon painter ───────────────────────────────────────────────────────
def paint_icon(p: QPainter, name: str, rect: QRectF, color: QColor, stroke: float = 1.4):
    """Draw a named glyph inside ``rect`` (16×16 design space)."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    p.translate(rect.x(), rect.y())
    s = rect.width() / 16.0
    p.scale(s, s)
    pen = QPen(color)
    pen.setWidthF(stroke)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    def line(x1, y1, x2, y2):
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    if name == "home":
        path = QPainterPath(QPointF(2, 7))
        path.lineTo(8, 2); path.lineTo(14, 7); path.lineTo(14, 14)
        path.lineTo(10, 14); path.lineTo(10, 9); path.lineTo(6, 9)
        path.lineTo(6, 14); path.lineTo(2, 14); path.closeSubpath()
        p.drawPath(path)
    elif name == "chat":
        p.drawRoundedRect(QRectF(2, 3, 12, 8), 1, 1)
        line(5, 11, 2.5, 13.5)
    elif name == "auto":
        line(8, 2, 8, 5); line(8, 11, 8, 14); line(2, 8, 5, 8); line(11, 8, 14, 8)
        p.drawEllipse(QPointF(8, 8), 3, 3)
    elif name == "brain":
        p.drawEllipse(QPointF(8, 7), 4, 5)
        line(6, 12, 6, 14); line(10, 12, 10, 14); line(5, 7, 11, 7)
    elif name == "memory":
        p.drawRoundedRect(QRectF(3, 4, 10, 8), 1.5, 1.5)
        for x in (6, 10):
            line(x, 4, x, 2.5); line(x, 12, x, 13.5)
        line(3, 8, 13, 8)
    elif name == "system":
        p.drawRoundedRect(QRectF(2, 3, 12, 9), 1.5, 1.5)
        line(5, 14, 11, 14); line(8, 12, 8, 14)
    elif name == "settings":
        p.drawEllipse(QPointF(8, 8), 2.5, 2.5)
        line(8, 2, 8, 3.5); line(8, 12.5, 8, 14); line(2, 8, 3.5, 8); line(12.5, 8, 14, 8)
        line(3.6, 3.6, 4.6, 4.6); line(11.4, 11.4, 12.4, 12.4)
        line(11.4, 3.6, 10.4, 4.6); line(3.6, 11.4, 4.6, 10.4)
    elif name == "search":
        p.drawEllipse(QPointF(7, 7), 4, 4)
        line(10, 10, 14, 14)
    elif name == "mic":
        p.drawRoundedRect(QRectF(6, 2, 4, 7), 2, 2)
        path = QPainterPath(); path.arcMoveTo(QRectF(4, 4, 8, 8), 200)
        path.arcTo(QRectF(4, 4, 8, 8), 200, 140)
        p.drawPath(path)
        line(8, 12, 8, 14); line(6, 14, 10, 14)
    elif name == "send":
        path = QPainterPath(QPointF(2, 8)); path.lineTo(14, 2)
        path.lineTo(9, 14); path.lineTo(7.5, 9); path.closeSubpath()
        p.drawPath(path)
    elif name == "close":
        line(4, 4, 12, 12); line(12, 4, 4, 12)
    elif name == "minimize":
        line(4, 11, 12, 11)
    elif name == "maximize":
        p.drawRect(QRectF(4, 4, 8, 8))
    else:
        p.drawEllipse(QPointF(8, 8), 4, 4)
    p.restore()


class IconWidget(QWidget):
    """A fixed-size widget that paints a named icon in a settable colour."""

    def __init__(self, name: str, size: int = 18, color: QColor = None, parent=None):
        super().__init__(parent)
        self._name = name
        self._color = color or col("textMut")
        self.setFixedSize(size, size)

    def set_color(self, c: QColor):
        self._color = c
        self.update()

    def set_name(self, name: str):
        self._name = name
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        paint_icon(p, self._name, QRectF(0, 0, self.width(), self.height()), self._color)
        p.end()


# ── atoms ────────────────────────────────────────────────────────────────
class StatusDot(QWidget):
    """A glowing dot; optionally blinking."""

    def __init__(self, color: QColor, size: int = 6, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(size + 6, size + 6)
        self._size = size

    def set_color(self, c: QColor):
        self._color = c
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx, cy = self.width() / 2, self.height() / 2
        glow = QColor(self._color); glow.setAlphaF(0.4)
        p.setPen(Qt.NoPen); p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), self._size, self._size)
        p.setBrush(self._color)
        p.drawEllipse(QPointF(cx, cy), self._size / 2, self._size / 2)
        p.end()


def JTag(text: str, color_key: str = "cyan") -> QWidget:
    """Pill tag: dot + mono uppercase label, tinted by ``color_key``."""
    w = QFrame()
    c = col(color_key)
    w.setStyleSheet(
        f"background:{rgba_str(color_key, 0.1)};"
        f"border:1px solid {rgba_str(color_key, 0.3)};border-radius:6px;"
    )
    lay = QHBoxLayout(w); lay.setContentsMargins(6, 2, 8, 2); lay.setSpacing(5)
    lay.addWidget(StatusDot(c, size=5))
    lbl = QLabel(text)
    lbl.setFont(font_mono(8, W_BOLD, 0.8))
    lbl.setStyleSheet(f"color:{rgba_str(color_key, 1.0)};background:transparent;border:0;")
    lay.addWidget(lbl)
    return w


def JLabel(text: str, color_key: str = "textMut", size: int = 9, spacing: float = 1.8) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setFont(font_ui(size, W_BOLD, spacing))
    lbl.setStyleSheet(f"color:{rgba_str(color_key, 1.0)};background:transparent;")
    return lbl


def hline(color_key: str = "border", alpha: float = 0.6) -> QFrame:
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{rgba_str(color_key, alpha)};border:0;")
    return f


def vline(height: int = 14, color_key: str = "border", alpha: float = 0.8) -> QFrame:
    f = QFrame()
    f.setFixedSize(1, height)
    f.setStyleSheet(f"background:{rgba_str(color_key, alpha)};border:0;")
    return f


class Card(QFrame):
    """Glassy panel container used across the pages (PageCard)."""

    def __init__(self, parent=None, pad: int = 16, accent: str = None):
        super().__init__(parent)
        border = rgba_str(accent, 0.25) if accent else rgba_str("border", 0.7)
        self.setStyleSheet(
            f"QFrame{{background:{rgba_str('panel', 0.55)};"
            f"border:1px solid {border};border-radius:14px;}}"
        )
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(pad, pad, pad, pad)
        self._lay.setSpacing(10)

    def body(self) -> QVBoxLayout:
        return self._lay


class StatTile(Card):
    """A labelled metric tile (value + caption + optional accent)."""

    def __init__(self, caption: str, value: str = "—", accent: str = "cyan", parent=None):
        super().__init__(parent, pad=14)
        self.setMinimumHeight(78)
        self._value = QLabel(value)
        self._value.setFont(font_mono(22, W_BOLD))
        self._value.setStyleSheet(f"color:{rgba_str(accent, 1.0)};background:transparent;")
        cap = JLabel(caption, "textMut", 9, 1.4)
        self.body().addWidget(self._value)
        self.body().addWidget(cap)
        self.body().addStretch(1)

    def set_value(self, v: str):
        self._value.setText(v)
