"""JARVIS v3.1 title bar — 40px frameless drag bar.

Mirrors jv3-app31.jsx::TitleBar:
  Left:   ●  A.E.R.I.S   JARVIS v3.1   |   › Shivang's Machine
  Center: state pill (color shifts: cyan/green/magenta/purple)
  Right:  HH:MM:SS   9 nodes · all nominal   ● ● ●
"""
from __future__ import annotations

import math
import time

from PyQt5.QtCore import QPointF, QRectF, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from .animation_bus import get_bus
from .tokens import J, JSTATES, inter, mono, rgba


class TitleBar(QWidget):
    """40px draggable title bar with window-control signals."""

    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()
    close_clicked    = pyqtSignal()
    drag_start       = pyqtSignal(object)
    drag_move        = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 48px gives ~12px breathing room above + below the 22px state pill
        # so the bar doesn't feel glued to the very top of the screen.
        self.setFixedHeight(48)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._drag = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 18, 6)
        lay.setSpacing(10)

        # ── Left: brand ─────────────────────────────────────────────
        self._logo_dot = _GlowDot(J.CYAN, glow_op=0.55)
        lay.addWidget(self._logo_dot)

        brand = QLabel("A.E.R.I.S")
        brand.setFont(inter(13, 700))
        brand.setStyleSheet(f"color: {J.TEXT_PRI.name()}; letter-spacing: 2px;")
        lay.addWidget(brand)

        sub = QLabel("JARVIS v3.1")
        sub.setFont(inter(10, 500))
        sub.setStyleSheet(f"color: {J.TEXT_MUT.name()}; letter-spacing: 0.5px;")
        lay.addWidget(sub)

        # vertical divider
        sep = QWidget(); sep.setFixedSize(1, 14)
        sep.setStyleSheet(
            f"background: rgba({J.BORDER.red()},{J.BORDER.green()},{J.BORDER.blue()},0.8);"
        )
        lay.addWidget(sep)

        machine = QLabel("› Shivang's Machine")
        machine.setFont(inter(10, 400))
        machine.setStyleSheet(f"color: {J.TEXT_MUT.name()};")
        lay.addWidget(machine)

        lay.addStretch(1)

        # ── Center: state pill ─────────────────────────────────────
        self.pill = _StatePill()
        lay.addWidget(self.pill)
        lay.addStretch(1)

        # ── Right: clock + node count + traffic lights ─────────────
        self.clock = QLabel("--:--:--")
        self.clock.setFont(mono(12, 700))
        self.clock.setStyleSheet(f"color: {J.TEXT_SEC.name()};")
        lay.addWidget(self.clock)

        self.nodes = QLabel("9 nodes · all nominal")
        self.nodes.setFont(mono(10, 400))
        self.nodes.setStyleSheet(f"color: {J.TEXT_MUT.name()};")
        lay.addWidget(self.nodes)

        # Order: minimize → maximize → close (per user spec).
        # macOS does close-min-max from the LEFT; we follow user request.
        for kind, color in (("min", J.AMBER), ("max", J.GREEN), ("close", J.RED)):
            btn = _TrafficLight(color, kind)
            if kind == "close":  btn.clicked.connect(self.close_clicked.emit)
            elif kind == "min":  btn.clicked.connect(self.minimize_clicked.emit)
            else:                btn.clicked.connect(self.maximize_clicked.emit)
            lay.addWidget(btn)

        # ── Clock tick ─────────────────────────────────────────────
        t = QTimer(self); t.timeout.connect(self._tick); t.start(1000)
        self._tick()

    # ── Painting (translucent dark bar with bottom border) ─────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        # Slight translucency over window bg.
        bg = QColor(J.BG); bg.setAlphaF(0.96)
        p.fillRect(self.rect(), bg)
        p.setPen(QPen(rgba(J.BORDER, 0.7), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

    # ── Clock + (optional) live node count ─────────────────────────
    def _tick(self):
        from datetime import datetime
        self.clock.setText(datetime.now().strftime("%H:%M:%S"))

    def set_node_status(self, text: str) -> None:
        self.nodes.setText(text)

    # ── Drag-to-move (frameless windows) ──────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos()
            self.drag_start.emit(self._drag)

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.drag_move.emit(e.globalPos())

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.maximize_clicked.emit()


# ─── Helpers ─────────────────────────────────────────────────────── #

class _GlowDot(QWidget):
    """Small filled disk with a soft halo, used for the brand mark."""
    def __init__(self, color: QColor, glow_op: float = 0.4, parent=None):
        super().__init__(parent)
        self._color = color
        self._glow = glow_op
        self.setFixedSize(14, 14)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        # Halo
        glow = QColor(self._color); glow.setAlphaF(self._glow)
        p.setBrush(glow)
        p.drawEllipse(self.rect())
        # Core
        p.setBrush(self._color)
        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))


class _TrafficLight(QPushButton):
    """16x16 colored dot mimicking macOS window controls.

    On hover the circle brightens (full alpha + outer glow ring). No glyphs.
    """
    SIZE = 16

    def __init__(self, color: QColor, kind: str, parent=None):
        super().__init__(parent)
        self._color = color
        self._kind = kind
        self._hover = False
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("border: none;")
        self.setToolTip({"min": "Minimize", "max": "Maximize", "close": "Close"}.get(kind, ""))

    def enterEvent(self, _): self._hover = True; self.update()
    def leaveEvent(self, _): self._hover = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        if self._hover:
            # Outer glow ring
            glow = QColor(self._color); glow.setAlphaF(0.35)
            p.setPen(QPen(glow, 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(self.rect().adjusted(0, 0, -1, -1))
            # Bright filled dot
            p.setPen(Qt.NoPen)
            p.setBrush(self._color)
        else:
            # Slightly dimmed when idle
            base = QColor(self._color); base.setAlphaF(0.75)
            p.setPen(Qt.NoPen)
            p.setBrush(base)

        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))


class _StatePill(QWidget):
    """Center pill: 'STANDBY · IDLE' or 'ONLINE · <STATE>' with blinking dot.

    Color shifts smoothly when the state changes (the underlying QColor swap
    is instant; perceived smoothness comes from the JS easing on state
    transitions which we don't replicate — would require interpolating colors).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "IDLE"
        self.setFixedHeight(22)
        self.setMinimumWidth(140)
        self._bus = get_bus()
        self._bus.tick_slow.connect(self.update)

    def set_state(self, key: str) -> None:
        if key in JSTATES and key != self._state:
            self._state = key
            self.update()

    def state(self) -> str:
        return self._state

    def paintEvent(self, _):
        spec = JSTATES[self._state]
        col = spec.color
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Pill bg
        rect = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(rgba(col, 0.42), 1))
        p.setBrush(rgba(col, 0.10))
        p.drawRoundedRect(rect, 11, 11)

        # Blinking dot (period ~1.5s)
        phase = self._bus.now_ms / 1000.0 * 2 * math.pi / 1.5
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(phase))
        p.setPen(Qt.NoPen)
        glow = QColor(col); glow.setAlphaF(alpha * 0.5)
        p.setBrush(glow)
        p.drawEllipse(QPointF(11, self.height() / 2), 5, 5)
        dot = QColor(col); dot.setAlphaF(alpha)
        p.setBrush(dot)
        p.drawEllipse(QPointF(11, self.height() / 2), 3, 3)

        # Label — 'STANDBY · IDLE' for IDLE else 'ONLINE · <LABEL>'
        label = "STANDBY · IDLE" if self._state == "IDLE" else f"ONLINE · {spec.label}"
        p.setPen(col)
        p.setFont(mono(10, 700))
        p.drawText(QRectF(20, 0, self.width() - 24, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, label)

        # Auto-fit width to text + padding
        fm = p.fontMetrics()
        need = 24 + fm.horizontalAdvance(label) + 14
        if need != self.minimumWidth():
            self.setMinimumWidth(need)
            self.setFixedWidth(need)
