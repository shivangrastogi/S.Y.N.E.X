"""ArcReactor — the animated core, ported from ``jv3-reactor.jsx``.

The web version stacks ~20 absolutely-positioned divs each with its own CSS
keyframe animation. Reproducing that with child QWidgets would be slow and
fragile, so this is a single custom-painted widget: one ~60 fps timer drives
an elapsed-time clock, and every ring / ripple / dot / tick is drawn from
that clock in :meth:`paintEvent`. Per-state colour changes interpolate
smoothly (the JS ``transition: 0.7s``) instead of snapping.

Everything is drawn in a 460×460 logical space and scaled to the widget, so
the reactor can live at any size.
"""
from __future__ import annotations

import math

from PyQt5.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt5.QtWidgets import QWidget

from ui.aeris_v6.tokens import J, JSTATES, ca

_REF = 460.0  # logical design size


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(
        int(_lerp(c1.red(), c2.red(), t)),
        int(_lerp(c1.green(), c2.green(), t)),
        int(_lerp(c1.blue(), c2.blue(), t)),
    )


class ArcReactor(QWidget):
    """Self-animating reactor core. Call :meth:`set_state` with one of
    IDLE / LISTENING / PROCESSING / SPEAKING."""

    def __init__(self, parent=None, size: int = 460):
        super().__init__(parent)
        self._state = "IDLE"
        self._cur_color = QColor(*J["cyan"])
        self._tgt_color = QColor(*J["cyan"])
        self._glow = JSTATES["IDLE"]["glowOp"]
        self._tgt_glow = self._glow
        # Presence dimming — an axis orthogonal to the activity state above.
        # 1.0 = fully present/lit; lower = user away/idle so the core visibly
        # rests. Eased like colour/glow so transitions are smooth.
        self._presence_dim = 1.0
        self._tgt_presence_dim = 1.0
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        self._clock = QElapsedTimer()
        self._clock.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)  # ~60 fps

    # ── state ──────────────────────────────────────────────────────
    def set_state(self, state: str):
        if state not in JSTATES or state == self._state:
            return
        self._state = state
        s = JSTATES[state]
        self._tgt_color = QColor(*J[s["key"]])
        self._tgt_glow = s["glowOp"]

    def state(self) -> str:
        return self._state

    # Presence axis: away/idle/active/focus → how lit the core sits.
    _PRESENCE_DIM = {"away": 0.30, "idle": 0.62, "active": 1.0, "focus": 1.0}

    def set_presence_state(self, state: str) -> None:
        self._tgt_presence_dim = self._PRESENCE_DIM.get(state, 1.0)

    # ── helpers ────────────────────────────────────────────────────
    def _ease_colors(self):
        # ~0.7 s ease toward target colour/glow (frame-rate independent-ish).
        t = 0.08
        self._cur_color = _lerp_color(self._cur_color, self._tgt_color, t)
        self._glow = _lerp(self._glow, self._tgt_glow, t)
        self._presence_dim = _lerp(self._presence_dim, self._tgt_presence_dim, t)

    def _ring_angle(self, period_s: float, reverse: bool = False) -> float:
        el = self._clock.elapsed() / 1000.0
        a = (el / period_s) * 360.0
        return -a if reverse else a

    # ── paint ──────────────────────────────────────────────────────
    def paintEvent(self, _ev):
        self._ease_colors()
        s = JSTATES.get(self._state, JSTATES["IDLE"])
        col = self._cur_color
        glow = self._glow
        el = self._clock.elapsed() / 1000.0

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Uniformly dim the whole core when the user is away/idle. Floor keeps
        # a faint ember so it never fully vanishes.
        if self._presence_dim < 0.999:
            p.setOpacity(max(0.12, self._presence_dim))
        scale = min(self.width(), self.height()) / _REF
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(scale, scale)
        # now origin = center, logical radius space is ±230
        R = _REF / 2.0

        # ambient glow
        grad = QRadialGradient(QPointF(0, 0), R)
        gc = QColor(col); gc.setAlphaF(glow * 0.10)
        grad.setColorAt(0.0, gc)
        grad.setColorAt(0.62, QColor(0, 0, 0, 0))
        p.setBrush(grad); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(0, 0), R, R)

        # ripples per state
        if self._state == "LISTENING":
            self._draw_ripples(p, ca("green", 0.4), n=3, base=R - 50, dur=2.5, gap=0.85, el=el)
        elif self._state == "SPEAKING":
            self._draw_ripples(p, ca("purple", 0.45), n=3, base=R - 42, dur=1.9, gap=0.65, el=el)
        elif self._state == "PROCESSING":
            self._draw_ripples(p, ca("magenta", 0.35), n=2, base=R - 55, dur=1.4, gap=0.5, el=el)

        r1, r2, r3 = s["ring"]

        # RING 1 — outer dashed + solid (same direction)
        a1 = self._ring_angle(r1)
        self._draw_ring(p, R - 18, ca(self._key(col), 0.20), 1.0, a1, dashed=True, dot=(9,))
        self._draw_ring(p, R - 28, _with_a(col, 0.16), 1.0, a1, glow_a=glow * 0.28)

        # RING 2 — middle reverse
        a2 = self._ring_angle(r2, reverse=True)
        self._draw_ring(p, R - 88, _with_a(col, 0.42), 1.5, a2, glow_a=glow * 0.45,
                        dot=(11, 7), dot_pos=("bottom", "right"))

        # RING 3 — inner fast
        a3 = self._ring_angle(r3)
        self._draw_ring(p, R - 148, _with_a(col, 0.60), 2.0, a3, glow_a=glow * 0.55,
                        dot=(13, 8), dot_pos=("top", "bottom"), glow_dot=True)

        # core zone pulse
        pulse = 0.5 + 0.5 * math.sin(2 * math.pi * el / s["pulse"])
        core_grad = QRadialGradient(QPointF(0, 0), R - 180)
        cz = QColor(col); cz.setAlphaF(glow * 0.45 * (0.7 + 0.3 * pulse))
        core_grad.setColorAt(0.0, cz)
        core_grad.setColorAt(0.7, QColor(0, 0, 0, 0))
        p.setBrush(core_grad); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(0, 0), R - 180, R - 180)

        # center disk
        disk_r = 90.0 * (1.0 + 0.04 * (pulse - 0.5) * 2)
        dg = QRadialGradient(QPointF(0, 0), disk_r)
        d0 = QColor(col); d0.setAlphaF(glow * 0.6)
        d1 = QColor(col); d1.setAlphaF(0.08)
        dg.setColorAt(0.0, d0); dg.setColorAt(0.55, d1); dg.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(dg)
        pen = QPen(_with_a(col, 0.8)); pen.setWidthF(2.0)
        p.setPen(pen)
        p.drawEllipse(QPointF(0, 0), disk_r, disk_r)

        # wireframe sphere (latitude rings, slow reverse spin)
        self._draw_sphere(p, col, el)

        # tick marks
        self._draw_ticks(p, col, R)

        # state glyph (processing spinner / speaking bars)
        self._draw_state_glyph(p, col, el)

        p.end()

    # ── primitive helpers ──────────────────────────────────────────
    @staticmethod
    def _key(_c):
        return "cyan"  # only used for the dashed outer tint fallback

    def _draw_ripples(self, p, color: QColor, n, base, dur, gap, el):
        for i in range(n):
            phase = ((el - i * gap) % dur) / dur
            if phase < 0:
                continue
            rad = base * (0.5 + 1.5 * phase)
            a = (1.0 - phase) * color.alphaF()
            pen = QPen(_with_a(color, a)); pen.setWidthF(1.2)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(0, 0), rad, rad)

    def _draw_ring(self, p, radius, color, width, angle_deg, dashed=False,
                   glow_a=0.0, dot=(), dot_pos=(), glow_dot=False):
        pen = QPen(color); pen.setWidthF(width)
        if dashed:
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([2, 4])
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(0, 0), radius, radius)

        # orbiting dots ride the ring at `angle_deg`
        positions = dot_pos or (["top"] * len(dot))
        for idx, dsz in enumerate(dot):
            base_deg = {"top": -90, "bottom": 90, "right": 0, "left": 180}.get(
                positions[idx] if idx < len(positions) else "top", -90)
            rad = math.radians(base_deg + angle_deg)
            cx, cy = radius * math.cos(rad), radius * math.sin(rad)
            solid = QColor(color); solid.setAlphaF(1.0)
            p.setBrush(solid); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), dsz / 2.0, dsz / 2.0)
            if glow_dot:
                gl = QColor(color); gl.setAlphaF(0.35)
                p.setBrush(gl)
                p.drawEllipse(QPointF(cx, cy), dsz, dsz)

    def _draw_sphere(self, p, col, el):
        p.save()
        p.rotate((-el / 22.0) * 360.0)
        size = 130.0
        for i, deg in enumerate([-48, -28, -8, 12, 32, 50]):
            scale = math.cos(math.radians(deg))
            cy = math.sin(math.radians(deg)) * (size / 2)
            w = scale * size
            pen = QPen(_with_a(col, 0.12 + i * 0.025)); pen.setWidthF(1.0)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(-w / 2, cy - (scale * size) / 2, w, scale * size))
        # core glow dot
        cg = QColor(col); cg.setAlphaF(1.0)
        p.setBrush(cg); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(0, 0), 9, 9)
        p.restore()

    def _draw_ticks(self, p, col, R):
        for a in range(0, 360, 30):
            p.save()
            p.rotate(a)
            length = 14 if a % 90 == 0 else (9 if a % 30 == 0 else 5)
            alpha = 0.55 if a % 90 == 0 else 0.18
            pen = QPen(_with_a(col, alpha)); pen.setWidthF(1.0)
            p.setPen(pen)
            p.drawLine(QPointF(0, -R + 3), QPointF(0, -R + 3 + length))
            p.restore()

    def _draw_state_glyph(self, p, col, el):
        if self._state == "PROCESSING":
            p.save()
            p.translate(0, 60)
            p.rotate((el / 0.5) * 360.0)
            pen = QPen(_with_a(col, 1.0)); pen.setWidthF(2.5)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(-12, -12, 24, 24), 90 * 16, 280 * 16)
            p.restore()
        elif self._state == "SPEAKING":
            p.save()
            p.translate(-22, 60)
            for i in range(6):
                h = 24 * (0.3 + 0.7 * abs(math.sin(2 * math.pi * (el / (0.5 + i * 0.1)))))
                bar = QColor(*J["purple"])
                p.setBrush(bar); p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(i * 7, -h / 2, 3, h), 1.5, 1.5)
            p.restore()


def _with_a(c: QColor, a: float) -> QColor:
    out = QColor(c)
    out.setAlphaF(max(0.0, min(1.0, a)))
    return out
