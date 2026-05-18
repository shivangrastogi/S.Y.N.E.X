"""JARVIS v3.1 bottom logs bar — 38px collapsed ↔ 158px expanded.

Mirrors jv3-app31.jsx::LogsBar. Same 7 type chips as the older aeris logs
panel (SYS/NLU/ACT/MIC/TTS/ERR/MEM) but smaller font sizes (8.5px text,
7.5px chip). Shows a permanent right-side status string in the header
('All modules nominal · JARVIS v3.1 ready') instead of just the latest
log preview.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

from PyQt5.QtCore import (
    QEasingCurve, QPointF, QRectF, QTimer, QVariantAnimation, Qt, pyqtSignal
)
from PyQt5.QtGui import QColor, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
)

from .animation_bus import get_bus
from .tokens import J, mono, rgba


# ─── Type spec ───────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class _LT:
    label: str
    color: QColor


LOG_TYPES: dict[str, _LT] = {
    "SYS": _LT("SYS", J.TEXT_MUT),
    "NLU": _LT("NLU", J.CYAN),
    "ACT": _LT("ACT", J.GREEN),
    "MIC": _LT("MIC", J.GREEN),
    "TTS": _LT("TTS", J.PURPLE),
    "ERR": _LT("ERR", J.RED),
    "MEM": _LT("MEM", J.AMBER),
}


@dataclass
class LogEntry:
    type: str
    text: str
    time: str
    highlight: bool = False


COLLAPSED_HEIGHT = 38
EXPANDED_HEIGHT  = 158
ANIM_MS          = 300


# ─── Single row ──────────────────────────────────────────────────────── #

class _LogLine(QWidget):
    def __init__(self, entry: LogEntry, fresh: bool = False, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._fade = 0.0 if fresh else 1.0
        self.setFixedHeight(16)
        if fresh:
            a = QVariantAnimation(self)
            a.setStartValue(0.0); a.setEndValue(1.0)
            a.setDuration(250); a.setEasingCurve(QEasingCurve.OutCubic)
            a.valueChanged.connect(self._on_fade)
            a.start()
            self._anim = a

    def _on_fade(self, v):
        try: self._fade = float(v)
        except (TypeError, ValueError): self._fade = 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setOpacity(self._fade)
        spec = LOG_TYPES.get(self.entry.type, LOG_TYPES["SYS"])

        # Time
        p.setPen(J.TEXT_MUT)
        p.setFont(mono(8, 400))
        time_w = 52
        p.drawText(QRectF(0, 0, time_w, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self.entry.time)

        # Type chip
        tag_x = time_w + 6
        tag_w = 26
        tag_rect = QRectF(tag_x, (self.height() - 12) / 2, tag_w, 12)
        p.setPen(QPen(rgba(spec.color, 0.20), 1))
        p.setBrush(rgba(spec.color, 0.12))
        p.drawRoundedRect(tag_rect, 2, 2)
        p.setPen(spec.color)
        p.setFont(mono(7, 700))
        p.drawText(tag_rect, Qt.AlignCenter, spec.label)

        # Text
        text_x = tag_x + tag_w + 8
        p.setPen(spec.color if self.entry.highlight else J.TEXT_SEC)
        p.setFont(mono(8, 400))
        rect = QRectF(text_x, 0, self.width() - text_x - 4, self.height())
        fm = QFontMetrics(p.font())
        elided = fm.elidedText(self.entry.text, Qt.ElideRight, int(rect.width()))
        p.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, elided)


# ─── Header ──────────────────────────────────────────────────────────── #

class _Header(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(COLLAPSED_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self._expanded = False
        self._count = 0
        self._preview = ""
        self._status = "All modules nominal · JARVIS v3.1 ready"
        self._bus = get_bus()
        self._bus.tick_slow.connect(self.update)

    def set_expanded(self, v): self._expanded = v; self.update()
    def set_count(self, n):    self._count = n;    self.update()
    def set_preview(self, t):  self._preview = t;  self.update()
    def set_status(self, t):   self._status = t;   self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Blinking green dot
        phase = self._bus.now_ms / 1000.0 * 2 * math.pi / 1.5
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(phase))
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(J.GREEN, alpha * 0.5))
        p.drawEllipse(QPointF(20, self.height() / 2), 4, 4)
        p.setBrush(rgba(J.GREEN, alpha))
        p.drawEllipse(QPointF(20, self.height() / 2), 2.5, 2.5)

        # Label
        p.setPen(J.TEXT_SEC)
        p.setFont(mono(9, 700))
        label = "SYSTEM LOGS"
        fm = QFontMetrics(p.font())
        label_w = fm.horizontalAdvance(label)
        p.drawText(QRectF(30, 0, label_w + 4, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, label)

        # Count chip
        chip_x = 30 + label_w + 10
        p.setFont(mono(8, 700))
        fm2 = QFontMetrics(p.font())
        count_text = str(self._count)
        chip_w = fm2.horizontalAdvance(count_text) + 10
        chip_rect = QRectF(chip_x, (self.height() - 12) / 2, chip_w, 12)
        p.setPen(QPen(rgba(J.CYAN, 0.20), 1))
        p.setBrush(rgba(J.CYAN, 0.10))
        p.drawRoundedRect(chip_rect, 2, 2)
        p.setPen(J.CYAN)
        p.drawText(chip_rect, Qt.AlignCenter, count_text)

        # Right side: chevron + (expanded ? status : preview)
        chev_x = self.width() - 24
        chev_y = self.height() / 2
        p.save()
        p.translate(chev_x + 5, chev_y)
        p.rotate(180 if self._expanded else 0)
        p.setPen(QPen(J.TEXT_MUT, 1.4))
        p.drawLine(QPointF(-4, -2), QPointF(0, 2))
        p.drawLine(QPointF(0, 2), QPointF(4, -2))
        p.restore()

        right_text = self._status if self._expanded else (self._preview or self._status)
        if right_text:
            preview_max_x = chev_x - 10
            preview_min_x = chip_x + chip_w + 16
            avail = preview_max_x - preview_min_x
            if avail > 60:
                p.setPen(J.TEXT_MUT)
                p.setFont(mono(8, 400))
                fm3 = QFontMetrics(p.font())
                elided = fm3.elidedText(right_text, Qt.ElideRight, int(avail))
                p.drawText(QRectF(preview_min_x, 0, avail, self.height()),
                           Qt.AlignVCenter | Qt.AlignRight, elided)


# ─── Public widget ───────────────────────────────────────────────────── #

class LogsBar(QWidget):
    expanded_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self.setFixedHeight(COLLAPSED_HEIGHT)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = _Header()
        self._header.clicked.connect(self.toggle)
        root.addWidget(self._header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 4px; }"
            "QScrollBar::handle:vertical { background: rgba(0,212,255,0.20);"
            " border-radius: 2px; }"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
        )
        self._scroll.setVisible(False)

        self._lines_w = QWidget()
        self._lines_w.setStyleSheet("background: transparent;")
        self._lines_lay = QVBoxLayout(self._lines_w)
        self._lines_lay.setContentsMargins(16, 4, 16, 4)
        self._lines_lay.setSpacing(0)
        self._lines_lay.addStretch(1)
        self._scroll.setWidget(self._lines_w)
        root.addWidget(self._scroll)

        self._entries: list[LogEntry] = []
        self._line_widgets: list[_LogLine] = []

        self._anim = QVariantAnimation(self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setDuration(ANIM_MS)
        self._anim.valueChanged.connect(self._set_height)

    # ── API ─────────────────────────────────────────────────────────
    def add_log(self, log_type: str, text: str, highlight: bool = False) -> None:
        if log_type not in LOG_TYPES:
            log_type = "SYS"
        entry = LogEntry(log_type, text, time.strftime("%H:%M:%S"), highlight)
        self._entries.append(entry)
        line = _LogLine(entry, fresh=True)
        self._line_widgets.append(line)
        self._lines_lay.insertWidget(self._lines_lay.count() - 1, line)
        self._header.set_count(len(self._entries))
        self._header.set_preview(text)
        if self._expanded:
            QTimer.singleShot(40, self._scroll_to_bottom)

    def clear(self) -> None:
        for w in self._line_widgets: w.deleteLater()
        self._line_widgets.clear()
        self._entries.clear()
        self._header.set_count(0)
        self._header.set_preview("")

    def set_status(self, text: str) -> None:
        self._header.set_status(text)

    def set_expanded(self, v: bool) -> None:
        if v == self._expanded: return
        self._expanded = v
        self._header.set_expanded(v)
        self._scroll.setVisible(v)
        start = self.height()
        end = EXPANDED_HEIGHT if v else COLLAPSED_HEIGHT
        self._anim.stop()
        self._anim.setStartValue(start); self._anim.setEndValue(end)
        self._anim.start()
        if v:
            QTimer.singleShot(80, self._scroll_to_bottom)
        self.expanded_changed.emit(v)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    # ── Helpers ─────────────────────────────────────────────────────
    def _set_height(self, h):
        try: self.setFixedHeight(int(h))
        except (TypeError, ValueError): pass

    def _scroll_to_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def paintEvent(self, _):
        p = QPainter(self)
        bg = QColor(8, 12, 22); bg.setAlphaF(0.92)
        p.fillRect(self.rect(), bg)
        p.setPen(QPen(rgba(J.BORDER, 0.6), 1))
        p.drawLine(0, 0, self.width(), 0)
