"""Custom 40px title bar with drag, status pill, time, and window controls."""
from __future__ import annotations

import math
import time
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPointF, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from .theme import C, STATES, rgba, inter, mono


class _StatusPill(QWidget):
    """Colored pill showing ONLINE • <STATE> with a blinking dot."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "IDLE"
        self._blink_phase = 0.0
        self.setFixedHeight(22)
        self.setMinimumWidth(160)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)
        self._start = time.monotonic()

    def set_state(self, key: str):
        if key in STATES:
            self._state = key
            self.update()

    def _tick(self):
        self._blink_phase = (time.monotonic() - self._start) * 2 * math.pi / 1.5
        self.update()

    def paintEvent(self, _):
        spec = STATES[self._state]
        col = spec.color
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)

        # bg + border
        p.setPen(QPen(rgba(col, 0.45), 1))
        p.setBrush(rgba(col, 0.12))
        p.drawRoundedRect(rect, 12, 12)

        # blinking dot
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(self._blink_phase))
        dot_col = QColor(col); dot_col.setAlphaF(alpha)
        p.setPen(Qt.NoPen)
        # glow
        glow = QColor(col); glow.setAlphaF(alpha * 0.5)
        p.setBrush(glow)
        p.drawEllipse(QPointF(12, self.height() / 2), 5, 5)
        p.setBrush(dot_col)
        p.drawEllipse(QPointF(12, self.height() / 2), 3, 3)

        # label
        label = "STANDBY • IDLE" if self._state == "IDLE" else f"ONLINE • {spec.label}"
        p.setPen(col)
        p.setFont(mono(9, 700))
        fm_rect = QRectF(22, 0, self.width() - 30, self.height())
        p.drawText(fm_rect, Qt.AlignVCenter | Qt.AlignLeft, label)

        # auto-size
        fm = p.fontMetrics()
        need = 22 + fm.horizontalAdvance(label) + 12
        if need != self.minimumWidth():
            self.setMinimumWidth(need)


class _WindowButton(QPushButton):
    """Minimize / maximize / close button — coloured dot style."""
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(12, 12)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("border: none;")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))


class TitleBar(QWidget):
    """40px draggable title bar. Emits signals for window controls."""

    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()
    close_clicked    = pyqtSignal()
    sidebar_toggled  = pyqtSignal()
    drag_move        = pyqtSignal(object)   # QPoint delta
    drag_start       = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setAutoFillBackground(False)
        self._drag_origin = None

        # Layout
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 20, 0)
        lay.setSpacing(10)

        # Menu / sidebar toggle — three painted lines (matches jsx exactly).
        self.menu_btn = _HamburgerButton()
        self.menu_btn.clicked.connect(self.sidebar_toggled.emit)
        lay.addWidget(self.menu_btn)

        # Logo dot
        self._logo_dot = _LogoDot()
        lay.addWidget(self._logo_dot)

        # Brand
        brand = QLabel("A.E.R.I.S")
        brand.setFont(inter(13, 700))
        brand.setStyleSheet(f"color: {C.TEXT_PRI.name()}; letter-spacing: 2px;")
        lay.addWidget(brand)

        version = QLabel("v3.1 • Semantic Core")
        version.setFont(inter(10, 500))
        version.setStyleSheet(f"color: {C.TEXT_MUT.name()}; letter-spacing: 0.5px;")
        lay.addWidget(version)

        lay.addStretch(1)

        # Status pill
        self.pill = _StatusPill()
        lay.addWidget(self.pill)

        lay.addStretch(1)

        # Clock
        self.clock_label = QLabel("--:--:--")
        self.clock_label.setFont(mono(12, 700))
        self.clock_label.setStyleSheet(f"color: {C.TEXT_SEC.name()}; letter-spacing: 1px;")
        lay.addWidget(self.clock_label)

        self.sys_label = QLabel("CPU --%   RAM --G   BAT --%")
        self.sys_label.setFont(mono(10, 400))
        self.sys_label.setStyleSheet(f"color: {C.TEXT_MUT.name()};")
        lay.addWidget(self.sys_label)

        # Window buttons
        min_btn = _WindowButton(C.AMBER);  min_btn.clicked.connect(self.minimize_clicked.emit)
        max_btn = _WindowButton(C.GREEN);  max_btn.clicked.connect(self.maximize_clicked.emit)
        close_btn = _WindowButton(C.RED);  close_btn.clicked.connect(self.close_clicked.emit)
        for b in (min_btn, max_btn, close_btn):
            lay.addWidget(b)

        # Clock + system stats tick.
        # Clock updates every second; stats every 2 seconds (psutil is cheap
        # but not free, and CPU/RAM don't change perceptibly more often).
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._update_sys_stats)
        self._stats_timer.start(2000)
        self._update_sys_stats()

    # ── Painting ─────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.fillRect(self.rect(), C.PANEL)
        # bottom border
        p.setPen(QPen(C.BORDER, 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

    # ── Clock ────────────────────────────────────────────────────────
    def _update_clock(self):
        from datetime import datetime
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    # ── Live system stats (CPU / RAM / battery) ─────────────────────
    def _update_sys_stats(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            ram_gb = psutil.virtual_memory().used / (1024 ** 3)
            bat = psutil.sensors_battery()
            bat_str = f"BAT {int(bat.percent)}%" if bat else "BAT --"
            self.sys_label.setText(
                f"CPU {int(cpu)}%   RAM {ram_gb:.1f}G   {bat_str}"
            )
        except Exception:
            # psutil missing or sensor unavailable — leave the placeholder.
            pass

    # ── Drag to move window ──────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_origin = e.globalPos()
            self.drag_start.emit(self._drag_origin)

    def mouseMoveEvent(self, e):
        if self._drag_origin is not None:
            self.drag_move.emit(e.globalPos())

    def mouseReleaseEvent(self, e):
        self._drag_origin = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.maximize_clicked.emit()


class _LogoDot(QWidget):
    """Small glowing cyan dot."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        glow = QColor(C.CYAN); glow.setAlphaF(0.35)
        p.setBrush(glow)
        p.drawEllipse(self.rect())
        p.setBrush(C.CYAN)
        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))


def _style_flat_text(btn: QPushButton, color: QColor):
    btn.setStyleSheet(btn.styleSheet() + f"QPushButton {{ color: {color.name()}; }}")


class _HamburgerButton(QPushButton):
    """28x28 button rendering 3 horizontal lines (sidebar toggle).

    Mirrors the inline svg from aeris-app.jsx: three lines at y=1/6/11,
    1.5px stroke, rounded caps, in TEXT_MUT.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False
        self.setStyleSheet("QPushButton { border: none; }")

    def enterEvent(self, _):
        self._hover = True
        self.update()

    def leaveEvent(self, _):
        self._hover = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Subtle hover bg (matches jsx hover behaviour).
        if self._hover:
            bg = QColor(255, 255, 255); bg.setAlphaF(0.04)
            p.setPen(Qt.NoPen); p.setBrush(bg)
            p.drawRoundedRect(self.rect(), 6, 6)
        # Three horizontal lines centered in a 16x12 box, like the jsx svg.
        pen = QPen(C.TEXT_MUT, 1.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        x0 = (self.width() - 16) / 2
        y0 = (self.height() - 12) / 2
        for dy in (1, 6, 11):
            p.drawLine(QPointF(x0, y0 + dy), QPointF(x0 + 16, y0 + dy))
