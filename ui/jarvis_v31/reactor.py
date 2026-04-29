"""JARVIS v3.1 reactor — 460px animated core with wireframe-sphere center.

Mirrors jv3-reactor.jsx. Differences vs the aeris reactor:
  - 460x460 (was 440)
  - PROCESSING uses magenta (was cyan)
  - Center disk holds a rotating wireframe sphere instead of mode-specific
    content; spinner / wavebars appear OUTSIDE the core disk near its bottom
  - ReactorStateText sits below with a 'STATE — descriptor' JTag

Public exports:
  ReactorRings        — the 460x460 painted reactor
  ReactorStateText    — main label + sub + JTag
  ParticleField       — drifting colored dots in the background
  StateSwitcher       — row of 4 buttons for manual state override
"""
from __future__ import annotations

import math
import random
import time

from PyQt5.QtCore import (
    QPointF, QRectF, QTimer, QVariantAnimation, Qt, pyqtSignal
)
from PyQt5.QtGui import QColor, QPainter, QPen, QRadialGradient, QTransform
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
)

from .tokens import J, JSTATES, inter, mono, rgba


# ─── Particle field background ──────────────────────────────────────── #

class ParticleField(QWidget):
    """Drifting colored dots — provides depth behind the reactor."""

    _COLORS = [J.CYAN, J.MAGENTA, J.PURPLE, J.GREEN]

    def __init__(self, count: int = 24, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._start = time.monotonic()
        # Each particle: (color, base_x_pct, base_y_pct, size, dur, phase)
        self._particles = []
        for i in range(count):
            self._particles.append((
                self._COLORS[i % 4],
                10 + (i * 37) % 80,         # x percent
                10 + (i * 53) % 80,         # y percent
                2 + (i % 3),                # size px
                4 + (i % 6),                # animation period seconds
                -(i * 0.7),                 # phase offset
            ))
        t = QTimer(self); t.timeout.connect(self.update); t.start(60)

    def paintEvent(self, _):
        if self.width() < 4 or self.height() < 4:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        t = time.monotonic() - self._start

        for color, bx, by, size, dur, phase in self._particles:
            # Float drift: small lissajous around base position
            tt = (t + phase) / dur
            ox = math.sin(tt * 2 * math.pi) * 12
            oy = math.cos(tt * 2 * math.pi * 0.7) * 12
            x = self.width()  * bx / 100 + ox
            y = self.height() * by / 100 + oy
            glow = QColor(color); glow.setAlphaF(0.55 * 0.45)
            p.setBrush(glow)
            p.drawEllipse(QPointF(x, y), size * 1.8, size * 1.8)
            core = QColor(color); core.setAlphaF(0.55)
            p.setBrush(core)
            p.drawEllipse(QPointF(x, y), size, size)


# ─── Reactor (rings + wireframe sphere + state-specific bottom content) ── #

class ReactorRings(QWidget):
    """460x460 painted reactor. Single 60-FPS QTimer drives everything."""

    SIZE = 460
    state_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._state = "IDLE"
        self._start = _now_ms()
        # Pre-bake some sphere geometry so we don't recompute per frame.
        self._sphere_lat_count = 6   # 6 latitude rings
        self._sphere_lon_count = 6   # 6 longitude great-circle arcs
        # Pre-pick blink seeds for sphere nodes (so they don't all blink in sync)
        self._sphere_node_seeds = [(i * 51.4, i * 31.7, 1.5 + i * 0.3, i * 0.2)
                                   for i in range(7)]
        t = QTimer(self); t.timeout.connect(self.update); t.start(16)

    # ── Public API ───────────────────────────────────────────────
    def set_state(self, key: str) -> None:
        if key in JSTATES and key != self._state:
            self._state = key
            self.state_changed.emit(key)

    def state(self) -> str:
        return self._state

    # ── Painting ────────────────────────────────────────────────
    def paintEvent(self, _):
        spec = JSTATES[self._state]
        col = spec.color
        t   = _now_ms() - self._start

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cx, cy = self.width() / 2, self.height() / 2
        center = QPointF(cx, cy)

        # ── Ambient radial glow ────────────────────────────────
        amb = QRadialGradient(center, self.SIZE / 2)
        amb.setColorAt(0.0, rgba(col, spec.glow_op * 0.18))
        amb.setColorAt(0.62, rgba(col, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(amb)
        p.drawEllipse(center, self.SIZE / 2, self.SIZE / 2)

        # Ripples drawn in _WireLayer (full 1080x820 grid) to reach 600px

        # ── Ring 1: outer dashed (rotating) ───────────────────
        a1 = (t / spec.ring_r1_ms) * 360 % 360
        self._draw_ring_dashed(p, center, radius=self.SIZE / 2 - 18,
                               color=rgba(col, 0.30), angle=a1, satellite=True)
        # secondary inner glow ring
        self._draw_ring_solid(p, center, radius=self.SIZE / 2 - 28,
                              color=rgba(col, 0.20), width=1,
                              glow=rgba(col, spec.glow_op * 0.28), glow_blur=12)

        # ── Ring 2: middle (counter-rotating) ────────────────
        a2 = -((t / spec.ring_r2_ms) * 360 % 360)
        self._draw_ring_solid(p, center, radius=self.SIZE / 2 - 88,
                              color=rgba(col, 0.5), width=1.8,
                              glow=rgba(col, spec.glow_op * 0.45), glow_blur=20,
                              angle=a2,
                              dots=[(180, 11, col, True),
                                    (340,  7, rgba(col, 0.6), False)])

        # ── Ring 3: inner fast ───────────────────────────────
        a3 = (t / spec.ring_r3_ms) * 360 % 360
        self._draw_ring_solid(p, center, radius=self.SIZE / 2 - 148,
                              color=rgba(col, 0.65), width=2.2,
                              glow=rgba(col, spec.glow_op * 0.55), glow_blur=26,
                              angle=a3,
                              dots=[(0, 13, col, True),
                                    (200, 8, rgba(col, 0.7), False)])

        # ── Tick marks ───────────────────────────────────────
        self._draw_ticks(p, center, col)

        # ── Core glow + center disk + wireframe sphere ───────
        pulse = 0.5 + 0.5 * math.sin((t / spec.pulse_ms) * 2 * math.pi)
        self._draw_core(p, center, col, spec, pulse, t)

    # ── Helpers ──────────────────────────────────────────────
    def _draw_ring_dashed(self, p, center, radius, color, angle, satellite=False):
        pen = QPen(color, 1)
        pen.setDashPattern([4, 4])
        p.save()
        p.translate(center); p.rotate(angle)
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), radius, radius)
        if satellite:
            sat = QColor(color); sat.setAlphaF(0.85)
            p.setPen(Qt.NoPen); p.setBrush(sat)
            p.drawEllipse(QPointF(0, -radius), 4, 4)
        p.restore()

    def _draw_ring_solid(self, p, center, radius, color, width,
                         glow=None, glow_blur=0, angle=0, dots=None):
        p.save()
        p.translate(center); p.rotate(angle)
        if glow is not None and glow_blur:
            for k in range(3, 0, -1):
                g = QColor(glow); g.setAlphaF(glow.alphaF() * (0.25 * k))
                p.setPen(QPen(g, width + k * 3))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(0, 0), radius, radius)
        p.setPen(QPen(color, width))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), radius, radius)
        if dots:
            for deg, size, dcolor, bright in dots:
                p.save(); p.rotate(deg); p.setPen(Qt.NoPen)
                if bright:
                    halo = QColor(dcolor); halo.setAlphaF(0.7)
                    p.setBrush(halo)
                    p.drawEllipse(QPointF(0, -radius), size * 1.5, size * 1.5)
                p.setBrush(dcolor)
                p.drawEllipse(QPointF(0, -radius), size / 2, size / 2)
                p.restore()
        p.restore()

    def _draw_ticks(self, p, center, col):
        p.save(); p.translate(center)
        outer = self.SIZE / 2 - 4
        for ang in range(0, 360, 30):
            length = 14 if ang % 90 == 0 else 9 if ang % 30 == 0 else 5
            alpha = 0.55 if ang % 90 == 0 else 0.20
            p.setPen(QPen(rgba(col, alpha), 1.2))
            p.save(); p.rotate(ang)
            p.drawLine(QPointF(0, -outer), QPointF(0, -outer + length))
            p.restore()
        p.restore()

    def _draw_core(self, p, center, col, spec, pulse, t):
        # Outer halo
        outer_r = 100
        g = QRadialGradient(center, outer_r)
        g.setColorAt(0.0, rgba(col, spec.glow_op * 0.55 * (0.65 + 0.35 * pulse)))
        g.setColorAt(0.62, rgba(col, 0.06))
        g.setColorAt(1.0, rgba(col, 0))
        p.setPen(Qt.NoPen); p.setBrush(g)
        p.drawEllipse(center, outer_r, outer_r)

        # Main core disk
        core_r = 90 * (0.96 + 0.04 * pulse)
        disk = QRadialGradient(center, core_r)
        disk.setColorAt(0.0, rgba(col, spec.glow_op * 0.65))
        disk.setColorAt(0.55, rgba(col, 0.10))
        disk.setColorAt(1.0, rgba(col, 0))
        p.setBrush(disk)
        p.drawEllipse(center, core_r, core_r)
        p.setPen(QPen(rgba(col, 0.85), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(center, core_r, core_r)

        # Wireframe sphere inside
        self._draw_sphere(p, center, col, t)

        # Speaking wavebars inside core bottom
        if self._state == "SPEAKING":
            self._draw_wavebars(p, QPointF(center.x(), center.y() + 60),
                                J.PURPLE, n=6, max_h=24, t=t)

    def _draw_sphere(self, p, center, col, t_ms):
        """Wireframe sphere ≈ 130px. Counter-rotates slowly (22s)."""
        size = 130
        # Slow counter-rotation around vertical axis (just pretend with line skew).
        # We approximate the 3D look with concentric ellipses (latitude bands)
        # plus rotated thin ellipses (longitude arcs).
        ang_deg = -(t_ms / 22000) * 360 % 360

        p.save(); p.translate(center); p.rotate(ang_deg)

        # Latitude rings — flatten by cos(deg) to fake spherical depth.
        latitudes = [-48, -28, -8, 12, 32, 50]
        for i, deg in enumerate(latitudes):
            scale = math.cos(math.radians(deg))
            offset_y = math.sin(math.radians(deg)) * (size / 2)
            ring_w = scale * size
            ring_h = ring_w * 0.32   # flatten
            p.setPen(QPen(rgba(col, 0.12 + i * 0.025), 1))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(0, offset_y), ring_w / 2, ring_h / 2)

        # Longitude arcs — rotated thin ellipses.
        longitudes = [0, 30, 60, 90, 120, 150]
        for deg in longitudes:
            p.save(); p.rotate(deg)
            p.setPen(QPen(rgba(col, 0.10), 1))
            # Thin ellipse standing vertical: width tapered by sin(deg) effect.
            p.drawEllipse(QPointF(0, 0), 6, size / 2)
            p.restore()

        # Sphere surface nodes — 7 dots that blink at staggered phases.
        for a_deg, b_deg, period_s, phase_s in self._sphere_node_seeds:
            ar = math.radians(a_deg); br = math.radians(b_deg)
            r = size / 2 - 6
            x = r * math.cos(ar) * math.sin(br)
            y = r * math.sin(ar)
            now_s = t_ms / 1000.0
            ph = (now_s - phase_s) * 2 * math.pi / period_s
            alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(ph))
            dot_col = QColor(col); dot_col.setAlphaF(alpha)
            glow_col = QColor(col); glow_col.setAlphaF(alpha * 0.5)
            p.setPen(Qt.NoPen)
            p.setBrush(glow_col); p.drawEllipse(QPointF(x, y), 5, 5)
            p.setBrush(dot_col); p.drawEllipse(QPointF(x, y), 2, 2)

        # Sphere core
        p.setBrush(col); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(0, 0), 9, 9)
        glow_inner = QColor(col); glow_inner.setAlphaF(0.4)
        p.setBrush(glow_inner)
        p.drawEllipse(QPointF(0, 0), 14, 14)

        p.restore()

    def _draw_spinner(self, p, center, col, t):
        """Small ring spinner used during PROCESSING."""
        ang = (t / 500) * 360 % 360
        p.save(); p.translate(center); p.rotate(ang)
        # Faint backing arc
        p.setPen(QPen(rgba(col, 0.3), 2.5, Qt.SolidLine, Qt.FlatCap))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(-12, -12, 24, 24), 0, 360 * 16)
        # Bright leading arc
        p.setPen(QPen(col, 2.5, Qt.SolidLine, Qt.FlatCap))
        p.drawArc(QRectF(-12, -12, 24, 24), 90 * 16, -90 * 16)
        p.restore()

    def _draw_wavebars(self, p, center, col, n, max_h, t):
        """Rounded vertical bars for SPEAKING."""
        bar_w = 3
        gap = 3
        total_w = n * bar_w + (n - 1) * gap
        x0 = center.x() - total_w / 2
        y0 = center.y()
        p.setPen(Qt.NoPen)
        for i in range(n):
            phase = (t / (500 + i * 100)) * 2 * math.pi + i * 0.5
            h = max_h * (0.28 + 0.72 * (0.5 + 0.5 * math.sin(phase)))
            x = x0 + i * (bar_w + gap)
            rect = QRectF(x, y0 - h / 2, bar_w, h)
            glow = QColor(col); glow.setAlphaF(0.55)
            p.setBrush(glow)
            p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 2, 2)
            p.setBrush(col)
            p.drawRoundedRect(rect, 2, 2)

    def _draw_ripples(self, p, center, t):
        """Heartbeat ripple: two rings fire close together, then silence.

        Each beat consists of ring-0 then ring-1 (220 ms apart). Both expand
        and fade over the first 42 % of the period; the rest is silent — giving
        the lub-dub pause characteristic of a heartbeat. Rings travel further
        out than the old evenly-spaced triplets.
        """
        st = self._state
        if st == "LISTENING":
            base, grow, period, color = 105, 170, 2500, J.GREEN
        elif st == "SPEAKING":
            base, grow, period, color = 95, 170, 1900, J.PURPLE
        elif st == "PROCESSING":
            base, grow, period, color = 105, 160, 1400, J.MAGENTA
        else:
            return

        beat_gap_ms = 230       # ms between the two rings of one heartbeat
        active_ms   = period * 0.42   # expansion window; rest is silent pause

        p.setBrush(Qt.NoBrush)
        for off in (0, beat_gap_ms):
            phase_ms = (t + off) % period
            if phase_ms > active_ms:
                continue                     # silent part — skip
            phase = phase_ms / active_ms     # 0 → 1 over active window
            r     = base + grow * phase
            alpha = max(0.0, 0.55 * (1.0 - phase))
            width = 1.6 - 0.5 * phase       # thinner as it expands
            p.setPen(QPen(rgba(color, alpha), width))
            p.drawEllipse(center, r, r)


# ─── Reactor state text + JTag ─────────────────────────────────────── #

_INFO = {
    "IDLE":       ("AWAITING INPUT", lambda x: "All systems nominal. Ready for your command.",                                                    None),
    "LISTENING":  ("LISTENING",      lambda x: f'"{x}"' if x else "Voice stream active…",                                                          "VOICE CAPTURE"),
    "PROCESSING": ("PROCESSING",     lambda x: (f'Parsing: "{x[:44]}…"' if len(x) > 44 else f'Parsing: "{x}"') if x else "Running inference…",     "NLU ACTIVE"),
    "SPEAKING":   ("GENERATING",     lambda x: "Streaming response to terminal…",                                                                  "TTS ACTIVE"),
}


class _JTag(QWidget):
    """Small pill: blinking dot + 'STATE — DESCRIPTOR' label.

    Mirrors window.JTag from jv3-tokens.jsx with `pulse=True`.
    """
    def __init__(self, text: str, color: QColor, parent=None):
        super().__init__(parent)
        self._text = text
        self._color = color
        self._start = time.monotonic()
        self.setFixedHeight(18)
        t = QTimer(self); t.timeout.connect(self.update); t.start(60)

    def set_data(self, text: str, color: QColor) -> None:
        self._text = text
        self._color = color
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        rect = QRectF(0, 0, self.width(), self.height())
        p.setPen(QPen(rgba(self._color, 0.30), 1))
        p.setBrush(rgba(self._color, 0.10))
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)

        # blinking dot
        ph = (time.monotonic() - self._start) * 2 * math.pi / 1.2
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(ph))
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(self._color, alpha * 0.5))
        p.drawEllipse(QPointF(8, self.height() / 2), 4, 4)
        p.setBrush(rgba(self._color, alpha))
        p.drawEllipse(QPointF(8, self.height() / 2), 2.5, 2.5)

        p.setPen(self._color)
        p.setFont(mono(9, 700))
        text_rect = QRectF(15, 0, self.width() - 18, self.height())
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self._text)
        # auto-fit width
        fm = p.fontMetrics()
        w = 18 + fm.horizontalAdvance(self._text) + 10
        if w != self.minimumWidth():
            self.setFixedWidth(w)


class ReactorStateText(QWidget):
    """Three-row caption shown below the reactor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "IDLE"
        self._last_input = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        root.setAlignment(Qt.AlignHCenter)

        # Row 1: dot + main label
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0); row.setSpacing(10)
        row.setAlignment(Qt.AlignHCenter)
        self._dot = _BlinkDot(J.CYAN)
        self._dot.setVisible(False)
        row.addWidget(self._dot)
        self._main = QLabel("AWAITING INPUT")
        self._main.setFont(mono(22, 700))
        self._main.setAlignment(Qt.AlignCenter)
        row.addWidget(self._main)
        root.addLayout(row)

        # Row 2: sub
        self._sub = QLabel("All systems nominal. Ready for your command.")
        self._sub.setFont(mono(11, 400))
        self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setStyleSheet(f"color: {J.TEXT_MUT.name()}; letter-spacing: 0.4px;")
        self._sub.setMaximumWidth(460)
        self._sub.setWordWrap(True)
        root.addWidget(self._sub, alignment=Qt.AlignHCenter)

        # Row 3: JTag (hidden when IDLE)
        self._jtag = _JTag("", J.CYAN)
        self._jtag.setVisible(False)
        root.addWidget(self._jtag, alignment=Qt.AlignHCenter)

        self._apply()

    # ── API ──────────────────────────────────────────────────
    def set_state(self, key: str) -> None:
        if key in JSTATES and key != self._state:
            self._state = key
            self._apply()

    def set_last_input(self, text: str) -> None:
        self._last_input = text or ""
        if self._state in ("LISTENING", "PROCESSING"):
            self._apply()

    # ── Internals ────────────────────────────────────────────
    def _apply(self) -> None:
        spec = JSTATES[self._state]
        main_text, sub_fn, descriptor = _INFO[self._state]

        self._dot.setVisible(self._state != "IDLE")
        self._dot.set_color(spec.color)

        self._main.setStyleSheet(
            f"color: {spec.color.name()}; letter-spacing: 4px;"
        )
        self._main.setText(main_text)
        self._sub.setText(sub_fn(self._last_input))

        if descriptor:
            self._jtag.set_data(f"{spec.label} — {descriptor}", spec.color)
            self._jtag.setVisible(True)
        else:
            self._jtag.setVisible(False)


class _BlinkDot(QWidget):
    """8x8 dot that pulses in opacity (used inline next to the state label)."""
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(10, 10)
        self._start = time.monotonic()
        t = QTimer(self); t.timeout.connect(self.update); t.start(60)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, _):
        ph = (time.monotonic() - self._start) * 2 * math.pi / 1.2
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(ph))
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(self._color, alpha * 0.6))
        p.drawEllipse(self.rect())
        p.setBrush(rgba(self._color, alpha))
        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))


# ─── State switcher (4 buttons under the reactor) ────────────────────── #

class StateSwitcher(QWidget):
    """Row of 4 manual-override buttons (IDLE / LISTENING / PROCESSING / SPEAKING)."""

    state_picked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = "IDLE"

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        row.setAlignment(Qt.AlignHCenter)

        self._buttons: dict[str, _PickButton] = {}
        for key in ("IDLE", "LISTENING", "PROCESSING", "SPEAKING"):
            b = _PickButton(key, JSTATES[key].color)
            b.set_active(key == self._active)
            b.clicked.connect(lambda _, k=key: self._on_pick(k))
            self._buttons[key] = b
            row.addWidget(b)

    def set_active(self, key: str) -> None:
        if key not in self._buttons or key == self._active:
            return
        self._buttons[self._active].set_active(False)
        self._buttons[key].set_active(True)
        self._active = key

    def _on_pick(self, key: str) -> None:
        self.set_active(key)
        self.state_picked.emit(key)


class _PickButton(QPushButton):
    def __init__(self, label: str, color: QColor, parent=None):
        super().__init__(label, parent)
        self._color = color
        self._active = False
        self.setFixedHeight(22)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(mono(8, 700))
        # Auto-width by content + padding
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(self.font())
        self.setFixedWidth(fm.horizontalAdvance(label) + 22)
        self.setFlat(True)
        self.setStyleSheet("border: none;")

    def set_active(self, on: bool) -> None:
        self._active = on
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        if self._active:
            p.setPen(QPen(rgba(self._color, 0.5), 1))
            p.setBrush(rgba(self._color, 0.14))
            text_col = self._color
        else:
            p.setPen(QPen(QColor(255, 255, 255, int(255 * 0.08)), 1))
            p.setBrush(QColor(255, 255, 255, int(255 * 0.04)))
            text_col = J.TEXT_MUT
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 7, 7)
        p.setPen(text_col)
        p.setFont(self.font())
        p.drawText(rect, Qt.AlignCenter, self.text())


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
