"""JARVIS v3.1 wiring system — 4 corner stat cards + PCB traces to reactor.

Mirrors jv3-wiring.jsx. The defining feature of this design.

Geometry (1080x820 center area, reactor centered at 540,390):
  CPU (cyan,    top-left,  card at 188,156) — wire L-bends 540,390→540,278→332,278→332,190
  RAM (purple,  top-right, card at 748,156)
  BAT (magenta, btm-left,  card at 188,506)
  NET (green,   btm-right, card at 748,506)

Junction dots at the bend corners. Animated packet dashes along each path
flow at a state-driven speed (faster when PROCESSING / LISTENING).

Each NodeBox4: icon + label + live value + sub + 8-bar sparkline. On hover
it scales up 6% and slides out a detail card with NOMINAL badge.

Perf notes (Nov 2026 refactor):
  - _WireLayer drops from 60 FPS to 30 FPS via the shared AnimationBus.
    Slow wire-packet motion is visually identical at 30 FPS.
  - Wire polyline QPainterPath objects pre-built once in __init__; no
    longer reconstructed inside drawPolyline / drawPacket every frame.
  - _NodeBox blink dot uses AnimationBus.tick_slow (~15 FPS), removing
    4 private 60 ms QTimers from the GUI thread.
  - psutil polling moved to a background SystemMonitor QThread so the
    GUI thread no longer blocks on cpu_percent / net_io_counters every
    2.8 s.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from PyQt5.QtCore import (
    QEasingCurve, QObject, QPointF, QRectF, QThread, QTimer,
    QVariantAnimation, Qt, pyqtSignal, pyqtSlot
)
from PyQt5.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath, QPen
)
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .animation_bus import get_bus
from .tokens import J, JSTATES, inter, mono, rgba


# Reactor center in the 1080x820 design grid. The MainWindow positions the
# WiringSystem so this center coincides with the reactor's painted center.
REACTOR_CX = 540
REACTOR_CY = 390


@dataclass(frozen=True)
class _NodeDef:
    id: str
    label: str
    value: str
    sub: str
    detail: str
    color: QColor
    left: int   # card top-left X within the 1080x820 grid
    top:  int   # card top-left Y within the 1080x820 grid


_NODES = [
    # Left-side cards shifted from x=188 to x=164 so their RIGHT edge stays
    # at x=332 (matches the wire bend coordinates). Right-side cards stay
    # at x=748 (the wire enters their LEFT edge unchanged).
    _NodeDef("cpu", "CPU",     "12%",      "Intel i9-13900K",
             "8P+16E cores · 125W TDP · Boost 5.8GHz",
             J.CYAN,    164, 156),
    _NodeDef("ram", "RAM",     "4.2 GB",   "16 GB DDR5-6000",
             "Dual channel · XMP 6000MHz · 32-36-36-76",
             J.PURPLE,  748, 156),
    _NodeDef("bat", "BATTERY", "87%",      "6h 20m remain",
             "68Wh · 45W fast charge · 2.1W idle drain",
             J.MAGENTA, 164, 506),
    _NodeDef("net", "NETWORK", "1.4 MB/s", "WiFi 6 · Online",
             "Intel AX210 · -42dBm · 867Mbps link",
             J.GREEN,   748, 506),
]


# Each wire is (id, list_of_points, color). Cards are 144 wide and ~108 tall;
# wires terminate at the centered top/bottom edge of each card so the L-bends
# look symmetric.
def _wires():
    """Build the 4 PCB traces. Each is a polyline (waypoints)."""
    return [
        # CPU: reactor center → up to y=278 → left to x=332 → up to y=190
        ("cpu", [(540, 390), (540, 278), (332, 278), (332, 190)], J.CYAN),
        # RAM: center → up → right → up
        ("ram", [(540, 390), (540, 278), (748, 278), (748, 190)], J.PURPLE),
        # BAT: center → down → left → down
        ("bat", [(540, 390), (540, 502), (332, 502), (332, 540)], J.MAGENTA),
        # NET: center → down → right → down
        ("net", [(540, 390), (540, 502), (748, 502), (748, 540)], J.GREEN),
    ]


# Junction dots at every bend corner (deduplicated).
def _junctions():
    return [
        (540, 278, J.CYAN),
        (332, 278, J.CYAN),
        (748, 278, J.PURPLE),
        (540, 502, J.MAGENTA),
        (332, 502, J.MAGENTA),
        (748, 502, J.GREEN),
    ]


# Card icons — small QPainterPath glyphs per node.
def _draw_node_icon(p: QPainter, node_id: str, color: QColor) -> None:
    pen = QPen(color, 1.2)
    pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen); p.setBrush(Qt.NoBrush)

    if node_id == "cpu":
        p.drawRoundedRect(QRectF(4, 4, 10, 10), 1.2, 1.2)
        for x in (7, 11):
            p.drawLine(QPointF(x, 4), QPointF(x, 2))
            p.drawLine(QPointF(x, 14), QPointF(x, 16))
        for y in (7, 11):
            p.drawLine(QPointF(4, y), QPointF(2, y))
            p.drawLine(QPointF(14, y), QPointF(16, y))
        p.drawEllipse(QPointF(9, 9), 2, 2)

    elif node_id == "ram":
        p.drawRoundedRect(QRectF(2, 5, 14, 8), 1.2, 1.2)
        for x in (5, 9, 13):
            p.drawLine(QPointF(x, 5), QPointF(x, 3))
            p.drawLine(QPointF(x, 13), QPointF(x, 15))
        p.drawLine(QPointF(5, 9), QPointF(13, 9))

    elif node_id == "bat":
        p.drawRoundedRect(QRectF(2, 5, 12, 8), 1.5, 1.5)
        # battery terminal nub
        p.setBrush(color)
        p.drawRoundedRect(QRectF(14, 7.5, 2, 3), 1, 1)
        # interior fill (75% charge look)
        fill = QColor(color); fill.setAlphaF(0.75)
        p.setBrush(fill); p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(4, 7, 6, 4), 0.5, 0.5)

    elif node_id == "net":
        p.drawEllipse(QPointF(9, 9), 6.5, 6.5)
        p.drawLine(QPointF(2, 9), QPointF(16, 9))
        # vertical "longitude" arcs
        path = QPainterPath()
        path.moveTo(9, 2)
        path.cubicTo(6, 4.8, 6, 13.2, 9, 16)
        p.drawPath(path)
        path2 = QPainterPath()
        path2.moveTo(9, 2)
        path2.cubicTo(12, 4.8, 12, 13.2, 9, 16)
        p.drawPath(path2)


# ─── Single corner card ────────────────────────────────────────────── #

class _NodeBox(QWidget):
    """A 144px-wide stat card with hover scale + slide-out detail."""

    def __init__(self, node: _NodeDef, parent=None):
        super().__init__(parent)
        self.node = node
        self._hov = False
        self._value_text = node.value
        self._bars = [0.45, 0.62, 0.38, 0.75, 0.58, 0.82, 0.49, 0.70]

        # Card width 168 (was 144) so '13.4 GB' / '0.0 MB/s' fit cleanly
        # without elide at 18pt value font. The wires terminate at the OLD
        # 144-wide right edge (x=332 / x=748); keeping the same `left` means
        # the wire visibly enters the card body — fine since it goes through
        # the card's edge area, not through the value text.
        self.setFixedWidth(168)
        # Card body 100 + margin 4 + detail card 120  ≈ 224
        self.setMinimumHeight(224)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_StyledBackground, False)

        # Detail-card slide animation (max-height 0 → 120, 300ms)
        self._detail_h = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

        # Pre-bake the card background QColor (was rebuilt every paint).
        self._bg_idle = QColor(13, 21, 37); self._bg_idle.setAlphaF(0.88)
        self._bg_hov  = QColor(13, 21, 37); self._bg_hov.setAlphaF(0.98)
        self._bg_detail = QColor(10, 15, 28); self._bg_detail.setAlphaF(0.95)

        # AnimationBus drives the blink dot — no private QTimer.
        self._bus = get_bus()
        self._bus.tick_slow.connect(self.update)

    # ── API ─────────────────────────────────────────────────────
    def set_value(self, v: str) -> None:
        self._value_text = v
        self.update()

    # ── Hover ───────────────────────────────────────────────────
    def enterEvent(self, _):
        self._hov = True
        self._anim.stop()
        self._anim.setStartValue(self._detail_h)
        self._anim.setEndValue(120.0)
        self._anim.start()
        self.update()

    def leaveEvent(self, _):
        self._hov = False
        self._anim.stop()
        self._anim.setStartValue(self._detail_h)
        self._anim.setEndValue(0.0)
        self._anim.start()
        self.update()

    def _on_anim(self, v):
        try: self._detail_h = float(v)
        except (TypeError, ValueError): self._detail_h = 0.0
        self.update()

    # ── Painting ───────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        col = self.node.color

        # ── Card body (with hover scale) ──────────────────────────
        scale = 1.06 if self._hov else 1.0
        # Apply transform around the card's center
        card_rect_unscaled = QRectF(0, 0, self.width(), 100)
        cx = card_rect_unscaled.center().x()
        cy = card_rect_unscaled.center().y()
        p.save()
        p.translate(cx, cy)
        p.scale(scale, scale)
        p.translate(-cx, -cy)

        # Background — pre-baked QColor (was rebuilt per frame).
        if self._hov:
            p.setPen(QPen(rgba(col, 0.65), 1))
            p.setBrush(self._bg_hov)
        else:
            p.setPen(QPen(rgba(col, 0.30), 1))
            p.setBrush(self._bg_idle)
        body = QRectF(0, 0, self.width() - 1, 100 - 1)
        p.drawRoundedRect(body, 12, 12)

        # Top accent bar (subtle gradient line)
        accent_y = 0.5
        accent_grad = QLinearGradient(20, accent_y, self.width() - 20, accent_y)
        accent_grad.setColorAt(0.0, rgba(col, 0))
        accent_grad.setColorAt(0.5, rgba(col, 0.8 if self._hov else 0.3))
        accent_grad.setColorAt(1.0, rgba(col, 0))
        p.setPen(QPen(accent_grad, 1.5))
        p.drawLine(QPointF(20, accent_y), QPointF(self.width() - 20, accent_y))

        # Header row: icon + label   |   blink dot
        # icon
        p.save()
        p.translate(12, 8)
        _draw_node_icon(p, self.node.id, col)
        p.restore()
        # label
        p.setPen(col); p.setFont(mono(8, 700))
        p.drawText(QRectF(36, 8, self.width() - 60, 14),
                   Qt.AlignVCenter | Qt.AlignLeft, self.node.label)
        # blink dot — phase derived from the shared bus time
        ph = self._bus.now_ms / 1000.0 * 2 * math.pi / 2.0
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(ph))
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(col, alpha * 0.5))
        p.drawEllipse(QPointF(self.width() - 16, 15), 5, 5)
        p.setBrush(rgba(col, alpha))
        p.drawEllipse(QPointF(self.width() - 16, 15), 2.5, 2.5)

        # Value — 18pt fits '13.4 GB' / '0.0 MB/s' in 168px width with room
        # to spare. Bumping width without shrinking the font wasn't enough
        # because mono 20pt char width is ~14-15px on Windows.
        p.setPen(col)
        p.setFont(mono(18, 700))
        p.drawText(QRectF(12, 28, self.width() - 24, 26),
                   Qt.AlignVCenter | Qt.AlignLeft, self._value_text)

        # Sub label
        p.setPen(J.TEXT_MUT)
        p.setFont(mono(8, 400))
        sub_rect = QRectF(12, 56, self.width() - 24, 12)
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(p.font())
        elided = fm.elidedText(self.node.sub, Qt.ElideRight, int(sub_rect.width()))
        p.drawText(sub_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

        # Sparkline (8 bars)
        bars_y = 72
        bars_h = 22
        bar_total_w = self.width() - 24
        bar_count = len(self._bars)
        gap = 2
        bar_w = (bar_total_w - gap * (bar_count - 1)) / bar_count
        for i, h_pct in enumerate(self._bars):
            actual = h_pct if self._hov else h_pct * 0.7
            bar_h = max(2, bars_h * actual)
            x = 12 + i * (bar_w + gap)
            y = bars_y + (bars_h - bar_h)
            grad = QLinearGradient(0, y, 0, y + bar_h)
            grad.setColorAt(0.0, col)
            grad.setColorAt(1.0, rgba(col, 0.25))
            opacity = (0.8 if self._hov else 0.45) + (i / bar_count) * (0.2 if self._hov else 0.25)
            grad_brush_color_clone = QColor(col)  # not used directly
            p.setPen(Qt.NoPen)
            p.setOpacity(opacity)
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 1.5, 1.5)
            p.setOpacity(1.0)

        p.restore()  # end of card-scale block

        # ── Detail card (slides down on hover) ────────────────────
        if self._detail_h > 0.5:
            dy = 104          # 100 (card) + 4 gap
            dh = self._detail_h
            opacity = min(1.0, dh / 120.0)
            p.setOpacity(opacity)
            detail_rect = QRectF(0, dy, self.width() - 1, dh)
            p.setPen(QPen(rgba(col, 0.30), 1))
            p.setBrush(self._bg_detail)
            p.drawRoundedRect(detail_rect, 10, 10)

            # Detail text — height is dh-38 so the NOMINAL badge at the
            # bottom never overlaps the text even when the card is fully open.
            p.setPen(J.TEXT_MUT)
            p.setFont(mono(8, 400))
            p.drawText(QRectF(12, dy + 8, self.width() - 24, dh - 38),
                       Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap,
                       self.node.detail)
            # NOMINAL pill row (only fully visible when expanded)
            if dh > 70:
                p.setPen(Qt.NoPen)
                p.setBrush(rgba(J.GREEN, 0.7))
                p.drawEllipse(QPointF(14, dy + dh - 14), 3, 3)
                p.setBrush(J.GREEN)
                p.drawEllipse(QPointF(14, dy + dh - 14), 1.5, 1.5)
                p.setPen(J.GREEN)
                p.setFont(mono(7, 700))
                p.drawText(QRectF(22, dy + dh - 22, self.width() - 32, 14),
                           Qt.AlignVCenter | Qt.AlignLeft, "NOMINAL")
                # trailing fade line
                line_grad = QLinearGradient(60, dy + dh - 14, self.width() - 16, dy + dh - 14)
                line_grad.setColorAt(0.0, rgba(col, 0.3))
                line_grad.setColorAt(1.0, rgba(col, 0))
                p.setPen(QPen(line_grad, 1))
                p.drawLine(QPointF(60, dy + dh - 14),
                           QPointF(self.width() - 16, dy + dh - 14))
            p.setOpacity(1.0)


# ─── Wiring layer (SVG-style traces drawn in QPainter) ─────────────── #

class _WireLayer(QWidget):
    """Transparent overlay covering the whole 1080x820 grid.

    Draws the 4 PCB traces, junctions, and a faint cyan dashed origin ring
    around the reactor. Animates 'wire-flow' packet dashes whose speed
    depends on the AI state.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._state = "IDLE"
        self._state_start_ms = 0.0   # ms since bus init when current state began
        # Pre-build wires + junctions
        self._wires = _wires()
        self._junctions = _junctions()
        # Pre-compute each wire's total length so we can place packets along it.
        self._wire_lengths = {wid: _polyline_length(pts)
                              for wid, pts, _ in self._wires}
        # Pre-build a QPainterPath for the FULL polyline of every wire.
        # The old code rebuilt this path on every base-glow + mid-stroke
        # draw (2 × per wire × 30+ FPS = ~240 path builds/sec). Now built
        # exactly once.
        self._wire_paths = {wid: self._build_polyline(pts)
                            for wid, pts, _ in self._wires}
        # Pre-bake per-wire pens for the base + mid strokes.
        self._wire_pens = {}
        for wid, _pts, col in self._wires:
            self._wire_pens[wid] = (
                QPen(rgba(col, 0.12), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
                QPen(rgba(col, 0.32), 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin),
            )
        # AnimationBus tick_fast = 30 FPS. Was 16ms (60 FPS) — visually
        # identical for the slow wire flow, half the paint cost.
        self._bus = get_bus()
        self._bus.tick_fast.connect(self.update)

    def set_state(self, key: str) -> None:
        if key in JSTATES and key != self._state:
            self._state = key
            # Reset start so ripples always begin at center on state change.
            # Time origin is the shared AnimationBus, so ripple birth times
            # remain comparable to bus.now_ms in paintEvent.
            self._state_start_ms = self._bus.now_ms

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        t = self._bus.now_ms / 1000.0   # seconds since bus init

        # Wire packet period — faster during PROCESSING / LISTENING.
        period = {"PROCESSING": 0.9, "LISTENING": 1.4,
                  "SPEAKING": 1.2, "IDLE": 2.2}.get(self._state, 2.2)

        # Each wire — base glow + brighter mid + 2 traveling packets.
        for wid, pts, col in self._wires:
            length = self._wire_lengths[wid]
            base_pen, mid_pen = self._wire_pens[wid]
            wire_path = self._wire_paths[wid]

            # Base glow layer (pre-built path + pre-built pen)
            p.setPen(base_pen)
            p.drawPath(wire_path)

            # Brighter mid layer
            p.setPen(mid_pen)
            p.drawPath(wire_path)

            # Packet 1
            phase = (t / period) % 1.0
            self._draw_packet(p, pts, length, phase, col,
                              packet_len=length * 0.10, alpha=0.9, width=2.5)
            # Packet 2 (slower, offset by 0.55)
            period2 = period * 1.7
            phase2 = ((t / period2) + 0.55) % 1.0
            self._draw_packet(p, pts, length, phase2, col,
                              packet_len=length * 0.05, alpha=0.5, width=1.8)

        # Junction dots — soft halo + bright dot, blink at staggered phases.
        for i, (jx, jy, jcol) in enumerate(self._junctions):
            ph = (t * 2 * math.pi / (1.8 + i * 0.25)) - i * 0.15
            alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(ph))
            p.setPen(Qt.NoPen)
            halo = QColor(jcol); halo.setAlphaF(0.10)
            p.setBrush(halo)
            p.drawEllipse(QPointF(jx, jy), 7.5, 7.5)
            dot = QColor(jcol); dot.setAlphaF(alpha * 0.75)
            p.setBrush(dot)
            p.drawEllipse(QPointF(jx, jy), 4, 4)

        # Origin pulse ring (faint dashed circle around reactor)
        pen = QPen(rgba(J.CYAN, 0.07), 1)
        pen.setDashPattern([3, 8])
        p.setPen(pen); p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(REACTOR_CX, REACTOR_CY), 238, 238)

        # Heartbeat ripples — drawn here so they can reach 600px radius
        self._draw_ripples(p, QPointF(REACTOR_CX, REACTOR_CY), t)

    @staticmethod
    def _build_polyline(pts: list) -> QPainterPath:
        """Build a QPainterPath from (x,y) waypoints (called once at init)."""
        path = QPainterPath()
        if len(pts) < 2:
            return path
        path.moveTo(*pts[0])
        for x, y in pts[1:]:
            path.lineTo(x, y)
        return path

    def _draw_packet(self, p, pts, total_length, phase, col,
                     packet_len, alpha, width):
        """Draw a small bright sub-segment along the polyline at parameter `phase`."""
        if total_length <= 0:
            return
        head = phase * (total_length + packet_len)
        tail = head - packet_len
        if tail < 0:
            tail = 0
        if head > total_length:
            head = total_length
        if head <= tail:
            return

        # Walk pts and emit segments overlapping [tail, head] in arc-length space.
        traveled = 0.0
        segments = []
        for i in range(len(pts) - 1):
            x0, y0 = pts[i]
            x1, y1 = pts[i + 1]
            seg_len = math.hypot(x1 - x0, y1 - y0)
            seg_start = traveled
            seg_end = traveled + seg_len
            if seg_end < tail:
                traveled = seg_end
                continue
            if seg_start > head:
                break
            # Overlap
            a_local = max(tail, seg_start) - seg_start
            b_local = min(head, seg_end) - seg_start
            if seg_len <= 0:
                traveled = seg_end
                continue
            ax = x0 + (x1 - x0) * (a_local / seg_len)
            ay = y0 + (y1 - y0) * (a_local / seg_len)
            bx = x0 + (x1 - x0) * (b_local / seg_len)
            by = y0 + (y1 - y0) * (b_local / seg_len)
            segments.append(((ax, ay), (bx, by)))
            traveled = seg_end

        if not segments:
            return

        path = QPainterPath()
        path.moveTo(*segments[0][0])
        for (sx, sy), (ex, ey) in segments:
            path.moveTo(sx, sy)
            path.lineTo(ex, ey)

        # Glow underlay
        p.setPen(QPen(rgba(col, alpha * 0.4), width + 4, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        # Core
        p.setPen(QPen(rgba(col, alpha), width, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)

    def _draw_ripples(self, p: QPainter, center: QPointF, t: float) -> None:
        """3 evenly-spaced rings + heartbeat companion, all born at the center.

        Each ring is assigned a 'birth time' relative to when the state was
        activated (_state_start_ms). Before a ring is born it is invisible, so
        on a state switch the first ring always starts at the center and flows
        outward like a water ripple — no ring pops in mid-expansion.

        Periods are deliberately slow (5-7 s) so the motion feels calm.
        `t` is seconds since _start (time.monotonic() delta).
        """
        st = self._state
        if st == "LISTENING":
            base, grow, period_ms, rings, color = 90, 490, 6500, 3, J.GREEN
        elif st == "SPEAKING":
            base, grow, period_ms, rings, color = 80, 490, 5000, 3, J.PURPLE
        elif st == "PROCESSING":
            base, grow, period_ms, rings, color = 90, 490, 4000, 2, J.MAGENTA
        else:
            return

        # _state_start_ms is captured in bus.now_ms units (set in set_state)
        t_ms = self._bus.now_ms
        elapsed_ms = t_ms - self._state_start_ms   # time in this state

        # Birth times: ring i is born at i * (period / rings) after state start.
        # Heartbeat companion born 250 ms after ring-0.
        birth_times = [i * period_ms / rings for i in range(rings)]
        birth_times.append(250.0)   # heartbeat echo after ring-0

        p.setBrush(Qt.NoBrush)
        for idx, born_at in enumerate(birth_times):
            if elapsed_ms < born_at:
                continue            # not yet born — skip cleanly
            # Age of this ring (wraps after first full period)
            age = elapsed_ms - born_at
            phase = (age % period_ms) / period_ms   # 0 → 1 linear
            r     = base + grow * phase
            alpha = max(0.0, 0.45 * (1.0 - phase))
            if idx == len(birth_times) - 1:
                alpha *= 0.60       # heartbeat echo slightly dimmer
            p.setPen(QPen(rgba(color, alpha), 1.2))
            p.drawEllipse(center, r, r)


def _polyline_length(pts: list) -> float:
    total = 0.0
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]; x1, y1 = pts[i + 1]
        total += math.hypot(x1 - x0, y1 - y0)
    return total


# ─── Wiring system root ─────────────────────────────────────────────── #

class _SystemMonitorWorker(QObject):
    """Polls psutil on a background QThread and emits the result.

    psutil's cpu_percent / virtual_memory / net_io_counters / sensors_battery
    are all blocking syscalls. Previously WiringSystem ran them on a 2.8 s
    QTimer that lived on the GUI thread, so every poll spiked GUI latency.
    Now they run here on a dedicated thread; only the resulting dict is
    queued back to the GUI thread via the `stats` signal.
    """

    stats = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._timer: QTimer | None = None
        self._prev_net_b: int | None = None

    @pyqtSlot()
    def start(self) -> None:
        # Timer must be created on the worker thread (not in __init__ on
        # the GUI thread), so build it lazily inside this slot.
        if self._timer is not None:
            return
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(2800)
        # Prime cpu_percent so the first reading is meaningful (cpu_percent
        # with interval=None compares against the LAST call).
        try:
            import psutil
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

    @pyqtSlot()
    def _poll(self) -> None:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            ram_gb = psutil.virtual_memory().used / (1024 ** 3)
            net = psutil.net_io_counters()
            now_b = (net.bytes_sent + net.bytes_recv)
            if self._prev_net_b is None:
                rate_mbps = 0.0
            else:
                rate_mbps = max(0.0, (now_b - self._prev_net_b) / 2.8 / (1024 * 1024))
            self._prev_net_b = now_b
            bat_obj = psutil.sensors_battery()
            bat_pct = int(bat_obj.percent) if bat_obj else 87
            self.stats.emit({
                "cpu": f"{int(cpu)}%",
                "ram": f"{ram_gb:.1f} GB",
                "bat": f"{bat_pct}%",
                "net": f"{rate_mbps:.1f} MB/s",
            })
        except Exception:
            # psutil failure or unsupported platform — fall back to a
            # gentle random walk so the cards still feel alive.
            self.stats.emit({
                "cpu": f"{random.randint(8, 28)}%",
                "ram": f"{4.0 + random.random() * 0.4:.1f} GB",
                "net": f"{random.random() * 3:.1f} MB/s",
            })


class WiringSystem(QWidget):
    """Composite: wire layer underneath + 4 absolutely-positioned NodeBoxes.

    Lays out at fixed 1080x820 (the design grid). Caller positions this
    widget so REACTOR_CX/REACTOR_CY align with the reactor's painted center.
    """

    GRID_W = 1080
    GRID_H = 820

    _start_monitor = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.GRID_W, self.GRID_H)
        self.setAttribute(Qt.WA_StyledBackground, False)

        # Wire layer fills the whole grid
        self._wire_layer = _WireLayer(self)
        self._wire_layer.setGeometry(0, 0, self.GRID_W, self.GRID_H)
        self._wire_layer.lower()

        # Place 4 node cards at exact design coordinates
        self._nodes: dict[str, _NodeBox] = {}
        for nd in _NODES:
            box = _NodeBox(nd, self)
            box.move(nd.left, nd.top)
            self._nodes[nd.id] = box

        # ── System stats on a background thread ─────────────────────
        # psutil calls are blocking — keep them off the GUI thread.
        self._mon_thread = QThread(self)
        self._mon_worker = _SystemMonitorWorker()
        self._mon_worker.moveToThread(self._mon_thread)
        self._start_monitor.connect(self._mon_worker.start)
        self._mon_worker.stats.connect(self._apply_stats)
        self._mon_thread.start()
        self._start_monitor.emit()

    # ── API ─────────────────────────────────────────────────────────
    def set_state(self, key: str) -> None:
        self._wire_layer.set_state(key)

    def set_value(self, node_id: str, value: str) -> None:
        if node_id in self._nodes:
            self._nodes[node_id].set_value(value)

    @pyqtSlot(dict)
    def _apply_stats(self, data: dict) -> None:
        """Called on GUI thread when SystemMonitor pushes new psutil values."""
        for key, value in data.items():
            self.set_value(key, value)

    def closeEvent(self, e):
        # Shut the monitor thread down cleanly so it doesn't outlive the widget.
        if self._mon_thread is not None:
            self._mon_thread.quit()
            self._mon_thread.wait(1000)
        super().closeEvent(e)
