"""ArcReactor — animated centerpiece. State-driven ring speeds + colors.

Renders:
  - radial glow
  - dashed outer ring (rotating)
  - solid outer ring (rotating, with satellite dot)
  - middle ring (counter-rotating, two dots)
  - inner fast ring (rotating, two dots)
  - pulsing core disk with state label
  - tick marks around the perimeter
  - ripple rings for LISTENING / SPEAKING / ERROR states
"""
from __future__ import annotations

import math
import time
from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal, pyqtProperty
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QRadialGradient, QFont, QPainterPath
from PyQt5.QtWidgets import QWidget

from .theme import C, STATES, rgba, mono


class ArcReactor(QWidget):
    """440×440 animated reactor. Driven by a single 60 FPS QTimer."""

    state_changed = pyqtSignal(str)

    SIZE = 440

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self._state_key = "IDLE"
        self._start_ms = _now_ms()
        # ripple phase markers — tuples of (start_ms, kind)
        self._ripples: list[tuple[int, str]] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)  # ~60 FPS

    # ── Public API ────────────────────────────────────────────────────
    def set_state(self, key: str):
        if key not in STATES:
            return
        if key != self._state_key:
            self._state_key = key
            self.state_changed.emit(key)

    def state(self) -> str:
        return self._state_key

    # ── Painting ──────────────────────────────────────────────────────
    def paintEvent(self, ev):
        spec = STATES[self._state_key]
        col = spec.color
        t = _now_ms() - self._start_ms

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx, cy = self.width() / 2, self.height() / 2
        center = QPointF(cx, cy)

        # ── Ambient radial glow ───────────────────────────────────────
        ambient = QRadialGradient(center, self.SIZE / 2)
        ambient.setColorAt(0.0, rgba(col, spec.glow_op * 0.18))
        ambient.setColorAt(0.65, rgba(col, 0.0))
        p.setPen(Qt.NoPen)
        p.setBrush(ambient)
        p.drawEllipse(center, self.SIZE / 2, self.SIZE / 2)

        # ── State ripples ─────────────────────────────────────────────
        self._draw_ripples(p, center, t)

        # ── Ring 1 outer dashed (rotating) ────────────────────────────
        r1_angle = (t / spec.ring_r1_ms) * 360 % 360
        self._draw_ring_dashed(p, center, radius=self.SIZE / 2 - 24,
                               color=rgba(col, 0.35), angle=r1_angle,
                               satellite=True)

        # Inner static glow ring
        self._draw_ring_solid(p, center, radius=self.SIZE / 2 - 34,
                              color=rgba(col, 0.22), width=1,
                              glow=rgba(col, spec.glow_op * 0.35), glow_blur=14)

        # ── Ring 2 middle (counter-rotating) ──────────────────────────
        r2_angle = -((t / spec.ring_r2_ms) * 360 % 360)
        self._draw_ring_solid(p, center, radius=self.SIZE / 2 - 82,
                              color=rgba(col, 0.5), width=2,
                              glow=rgba(col, spec.glow_op * 0.45), glow_blur=20,
                              angle=r2_angle,
                              dots=[(180, 12, col, True), (340, 7, rgba(col, 0.55), False)])

        # ── Ring 3 inner fast ─────────────────────────────────────────
        r3_angle = (t / spec.ring_r3_ms) * 360 % 360
        self._draw_ring_solid(p, center, radius=self.SIZE / 2 - 142,
                              color=rgba(col, 0.7), width=2.5,
                              glow=rgba(col, spec.glow_op * 0.55), glow_blur=28,
                              angle=r3_angle,
                              dots=[(0, 14, col, True), (200, 8, rgba(col, 0.7), False)])

        # ── Tick marks ────────────────────────────────────────────────
        self._draw_ticks(p, center, col)

        # ── Core pulse and disk ───────────────────────────────────────
        pulse = 0.5 + 0.5 * math.sin((t / spec.pulse_ms) * 2 * math.pi)
        self._draw_core(p, center, col, spec, pulse)

        p.end()

    # ── Drawing helpers ───────────────────────────────────────────────
    def _draw_ring_dashed(self, p, center, radius, color, angle, satellite=False):
        pen = QPen(color, 1.5)
        pen.setDashPattern([4, 4])
        p.save()
        p.translate(center)
        p.rotate(angle)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), radius, radius)
        if satellite:
            dot = QColor(color); dot.setAlphaF(0.9)
            p.setPen(Qt.NoPen)
            p.setBrush(dot)
            p.drawEllipse(QPointF(0, -radius), 5, 5)
        p.restore()

    def _draw_ring_solid(self, p, center, radius, color, width,
                         glow=None, glow_blur=0, angle=0, dots=None):
        p.save()
        p.translate(center)
        p.rotate(angle)
        if glow is not None and glow_blur:
            # Simulated glow: draw 3 progressively wider faded strokes
            for k in range(3, 0, -1):
                g = QColor(glow); g.setAlphaF(glow.alphaF() * (0.25 * k))
                gpen = QPen(g, width + k * 3)
                p.setPen(gpen); p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(0, 0), radius, radius)
        p.setPen(QPen(color, width))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), radius, radius)
        if dots:
            for (deg, size, dcolor, bright) in dots:
                p.save()
                p.rotate(deg)
                p.setPen(Qt.NoPen)
                if bright:
                    # white inner + colored halo
                    halo = QColor(dcolor); halo.setAlphaF(0.7)
                    p.setBrush(halo)
                    p.drawEllipse(QPointF(0, -radius), size * 1.5, size * 1.5)
                p.setBrush(dcolor)
                p.drawEllipse(QPointF(0, -radius), size / 2, size / 2)
                p.restore()
        p.restore()

    def _draw_ticks(self, p, center, col):
        p.save()
        p.translate(center)
        outer = self.SIZE / 2 - 6
        for angle in range(0, 360, 30):
            length = 14 if angle % 90 == 0 else 9
            alpha = 0.55 if angle % 90 == 0 else 0.25
            pen = QPen(rgba(col, alpha), 1.2)
            p.setPen(pen)
            p.save()
            p.rotate(angle)
            p.drawLine(QPointF(0, -outer), QPointF(0, -outer + length))
            p.restore()
        p.restore()

    def _draw_core(self, p, center, col, spec, pulse):
        # outer glow halo
        outer_r = 90
        g = QRadialGradient(center, outer_r)
        g.setColorAt(0.0, rgba(col, spec.glow_op * 0.55 * (0.65 + 0.35 * pulse)))
        g.setColorAt(0.65, rgba(col, 0.08))
        g.setColorAt(1.0, rgba(col, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(center, outer_r, outer_r)

        # core disk
        core_r = 52 * (0.96 + 0.04 * pulse)
        disk = QRadialGradient(center, core_r)
        disk.setColorAt(0.0, rgba(col, spec.glow_op * 0.85))
        disk.setColorAt(0.6, rgba(col, 0.12))
        disk.setColorAt(1.0, rgba(col, 0))
        p.setBrush(disk)
        p.drawEllipse(center, core_r, core_r)

        p.setPen(QPen(rgba(col, 0.9), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(center, core_r, core_r)

        # inner state-specific content
        st = self._state_key
        if st == "PROCESSING":
            self._draw_spinner(p, center, col)
        elif st == "SPEAKING":
            self._draw_wavebars(p, center, C.PURPLE, n=6, max_h=28)
        elif st == "LISTENING":
            self._draw_wavebars(p, center, C.GREEN, n=5, max_h=22)
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawEllipse(center, 9, 9)

        # label
        p.setPen(col)
        p.setFont(mono(9, 700))
        rect = QRectF(center.x() - 60, center.y() + 24, 120, 14)
        p.drawText(rect, Qt.AlignCenter, st)

    def _draw_spinner(self, p, center, col):
        t = _now_ms() - self._start_ms
        angle = (t / 550) * 360 % 360
        p.save()
        p.translate(center)
        p.rotate(angle)
        pen = QPen(rgba(col, 0.3), 2.5, Qt.SolidLine, Qt.FlatCap)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(-14, -14, 28, 28), 0, 360 * 16)
        pen2 = QPen(col, 2.5, Qt.SolidLine, Qt.FlatCap)
        p.setPen(pen2)
        p.drawArc(QRectF(-14, -14, 28, 28), 90 * 16, -90 * 16)
        p.restore()

    def _draw_wavebars(self, p, center, col, n, max_h):
        t = _now_ms() - self._start_ms
        gap = 3
        bar_w = 4
        total_w = n * bar_w + (n - 1) * gap
        x0 = center.x() - total_w / 2
        y0 = center.y()
        p.setPen(Qt.NoPen)
        for i in range(n):
            phase = (t / (500 + i * 100)) * 2 * math.pi + i * 0.5
            h = max_h * (0.28 + 0.72 * (0.5 + 0.5 * math.sin(phase)))
            x = x0 + i * (bar_w + gap)
            rect = QRectF(x, y0 - h / 2, bar_w, h)
            # glow
            glow = QColor(col); glow.setAlphaF(0.55)
            p.setBrush(glow)
            p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 2, 2)
            p.setBrush(col)
            p.drawRoundedRect(rect, 2, 2)

    def _draw_ripples(self, p, center, t):
        st = self._state_key
        if st not in ("LISTENING", "SPEAKING", "ERROR"):
            return
        if st == "LISTENING":
            color = C.GREEN; period = 2400; rings = 3; base_r = 85; grow = 140
        elif st == "SPEAKING":
            color = C.PURPLE; period = 1800; rings = 3; base_r = 95; grow = 140
        else:
            color = C.RED; period = 1200; rings = 2; base_r = 90; grow = 130
        for i in range(rings):
            phase = ((t + i * period / rings) % period) / period
            r = base_r + grow * phase
            alpha = max(0.0, 0.55 * (1 - phase))
            pen = QPen(rgba(color, alpha), 1.2)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawEllipse(center, r, r)


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
