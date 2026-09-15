"""Bottom system logs panel — collapsible feed with color-coded type tags.

Mirrors aeris-logs.jsx:
  - 40px collapsed (header only) ↔ 180px expanded (header + 140px scroll)
  - Header: blinking green dot + 'SYSTEM LOGS' + count badge
            collapsed mode also shows the latest log preview inline
            chevron rotates 180° when expanded
  - Log line: HH:MM:SS time + colored type tag + text
              fresh-fade-in for newly added rows
  - Auto-scrolls to newest entry on add
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import (
    QEasingCurve, QPointF, QRectF, QTimer, QVariantAnimation, Qt, pyqtSignal
)
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget
)

from .theme import C, mono, rgba


# ─── Log type definitions ─────────────────────────────────────────────── #

@dataclass(frozen=True)
class _LogTypeSpec:
    label: str
    color: QColor


LOG_TYPES: dict[str, _LogTypeSpec] = {
    "SYS": _LogTypeSpec("SYS", C.TEXT_MUT),
    "NLU": _LogTypeSpec("NLU", C.CYAN),
    "ACT": _LogTypeSpec("ACT", C.GREEN),
    "MIC": _LogTypeSpec("MIC", C.GREEN),
    "TTS": _LogTypeSpec("TTS", C.PURPLE),
    "ERR": _LogTypeSpec("ERR", C.RED),
    "MEM": _LogTypeSpec("MEM", C.AMBER),
}


@dataclass
class LogEntry:
    type: str
    text: str
    time: str
    highlight: bool = False


COLLAPSED_HEIGHT = 40
EXPANDED_HEIGHT  = 180
ANIM_MS          = 300


# ─── Single log line ──────────────────────────────────────────────────── #

class _LogLine(QWidget):
    """Single row: time | type tag | text. Fresh rows fade-in on first paint."""

    def __init__(self, entry: LogEntry, fresh: bool = False, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._fresh = fresh
        self._fade = 0.0 if fresh else 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Auto-fit height to content (one line, ~18px).
        self.setFixedHeight(18)

        if fresh:
            self._fade_anim = QVariantAnimation(self)
            self._fade_anim.setStartValue(0.0)
            self._fade_anim.setEndValue(1.0)
            self._fade_anim.setDuration(250)
            self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._fade_anim.valueChanged.connect(self._on_fade)
            self._fade_anim.start()

    def _on_fade(self, v):
        try:
            self._fade = float(v)
        except (TypeError, ValueError):
            self._fade = 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setOpacity(self._fade)

        spec = LOG_TYPES.get(self.entry.type, LOG_TYPES["SYS"])

        # ── time column ─────────────────────────────────────────────
        p.setPen(C.TEXT_MUT)
        p.setFont(mono(9, 400))
        time_w = 56
        p.drawText(QRectF(0, 0, time_w, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self.entry.time)

        # ── type tag (small colored chip) ───────────────────────────
        tag_x = time_w + 8
        tag_w = 32
        tag_rect = QRectF(tag_x, (self.height() - 14) / 2, tag_w, 14)
        p.setPen(QPen(rgba(spec.color, 0.25), 1))
        p.setBrush(rgba(spec.color, 0.12))
        p.drawRoundedRect(tag_rect, 3, 3)
        p.setPen(spec.color)
        p.setFont(mono(8, 700))
        p.drawText(tag_rect, Qt.AlignCenter, spec.label)

        # ── text ────────────────────────────────────────────────────
        text_x = tag_x + tag_w + 10
        text_color = spec.color if self.entry.highlight else C.TEXT_SEC
        p.setPen(text_color)
        p.setFont(mono(9, 400))
        elide_rect = QRectF(text_x, 0, self.width() - text_x - 4, self.height())

        # Manually elide if text doesn't fit (Qt's elidedText needs QFontMetrics).
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(p.font())
        elided = fm.elidedText(self.entry.text, Qt.ElideRight, int(elide_rect.width()))
        p.drawText(elide_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)


# ─── Header (clickable) ───────────────────────────────────────────────── #

class _LogsHeader(QWidget):
    """40px header: blinking dot + label + count badge + (preview) + chevron."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(COLLAPSED_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self._expanded = False
        self._count = 0
        self._preview = ""
        self._dot_start = time.monotonic()

        # Repaint at ~16fps for the blink dot.
        t = QTimer(self); t.timeout.connect(self.update); t.start(60)

    def set_expanded(self, v: bool) -> None:
        self._expanded = v
        self.update()

    def set_count(self, n: int) -> None:
        self._count = n
        self.update()

    def set_preview(self, text: str) -> None:
        self._preview = text
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # ── blinking green dot ──────────────────────────────────────
        phase = (time.monotonic() - self._dot_start) * 2 * math.pi / 1.5
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(phase))
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(C.GREEN, alpha * 0.5))
        p.drawEllipse(QPointF(20, self.height() / 2), 5, 5)
        p.setBrush(rgba(C.GREEN, alpha))
        p.drawEllipse(QPointF(20, self.height() / 2), 3, 3)

        # ── 'SYSTEM LOGS' label ─────────────────────────────────────
        p.setPen(C.TEXT_SEC)
        p.setFont(mono(10, 700))
        label_x = 32
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(p.font())
        label_w = fm.horizontalAdvance("SYSTEM LOGS")
        p.drawText(QRectF(label_x, 0, label_w + 4, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, "SYSTEM LOGS")

        # ── count badge (small cyan chip) ──────────────────────────
        badge_x = label_x + label_w + 12
        badge_text = str(self._count)
        p.setFont(mono(8, 700))
        fm2 = QFontMetrics(p.font())
        badge_w = fm2.horizontalAdvance(badge_text) + 12
        badge_rect = QRectF(badge_x, (self.height() - 14) / 2, badge_w, 14)
        p.setPen(QPen(rgba(C.CYAN, 0.25), 1))
        p.setBrush(rgba(C.CYAN, 0.10))
        p.drawRoundedRect(badge_rect, 3, 3)
        p.setPen(C.CYAN)
        p.drawText(badge_rect, Qt.AlignCenter, badge_text)

        # ── chevron (right side) ────────────────────────────────────
        chev_size = 12
        chev_x = self.width() - chev_size - 16
        chev_y = self.height() / 2
        p.save()
        p.translate(chev_x + chev_size / 2, chev_y)
        p.rotate(180 if self._expanded else 0)
        p.setPen(QPen(C.TEXT_MUT, 1.5))
        p.drawLine(QPointF(-5, -2.5), QPointF(0, 2.5))
        p.drawLine(QPointF(0, 2.5), QPointF(5, -2.5))
        p.restore()

        # ── preview (only when collapsed) ──────────────────────────
        if not self._expanded and self._preview:
            preview_x = badge_x + badge_w + 14
            preview_w = chev_x - preview_x - 8
            if preview_w > 60:
                p.setPen(C.TEXT_MUT)
                p.setFont(mono(9, 400))
                fm3 = QFontMetrics(p.font())
                elided = fm3.elidedText(self._preview, Qt.ElideRight, int(preview_w))
                p.drawText(QRectF(preview_x, 0, preview_w, self.height()),
                           Qt.AlignVCenter | Qt.AlignLeft, elided)

        # ── bottom border (only when expanded) ─────────────────────
        if self._expanded:
            p.setPen(QPen(C.BORDER, 1))
            p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


# ─── Logs panel root ─────────────────────────────────────────────────── #

class SystemLogsPanel(QWidget):
    """Bottom collapsible logs feed.

    Public API:
        add_log(type, text, highlight=False)
        clear()
        set_expanded(bool) / toggle()
        expanded_changed = pyqtSignal(bool)
    """

    expanded_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self.setFixedHeight(COLLAPSED_HEIGHT)
        self.setAttribute(Qt.WA_StyledBackground, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = _LogsHeader()
        self._header.clicked.connect(self.toggle)
        root.addWidget(self._header)

        # Scroll area for log lines
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 4px; }"
            f"QScrollBar::handle:vertical {{ background: rgba(0,212,255,0.2);"
            f" border-radius: 2px; }}"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; }"
        )
        self._scroll.setVisible(False)

        self._lines_container = QWidget()
        self._lines_container.setStyleSheet("background: transparent;")
        self._lines_layout = QVBoxLayout(self._lines_container)
        self._lines_layout.setContentsMargins(16, 6, 16, 6)
        self._lines_layout.setSpacing(0)
        self._lines_layout.addStretch(1)
        self._scroll.setWidget(self._lines_container)
        root.addWidget(self._scroll)

        # Bookkeeping
        self._entries: list[LogEntry] = []
        self._line_widgets: list[_LogLine] = []

        # Height animation
        self._anim = QVariantAnimation(self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.setDuration(ANIM_MS)
        self._anim.valueChanged.connect(self._set_height)

    # ── Public API ────────────────────────────────────────────────────
    def add_log(self, log_type: str, text: str, highlight: bool = False) -> None:
        if log_type not in LOG_TYPES:
            log_type = "SYS"
        entry = LogEntry(
            type=log_type,
            text=text,
            time=time.strftime("%H:%M:%S"),
            highlight=highlight,
        )
        self._entries.append(entry)
        line = _LogLine(entry, fresh=True)
        self._line_widgets.append(line)
        # Insert before stretch
        self._lines_layout.insertWidget(self._lines_layout.count() - 1, line)
        self._header.set_count(len(self._entries))
        self._header.set_preview(text)
        if self._expanded:
            QTimer.singleShot(50, self._scroll_to_bottom)

    def clear(self) -> None:
        for w in self._line_widgets:
            w.deleteLater()
        self._line_widgets.clear()
        self._entries.clear()
        self._header.set_count(0)
        self._header.set_preview("")

    def set_expanded(self, v: bool) -> None:
        if v == self._expanded:
            return
        self._expanded = v
        self._header.set_expanded(v)
        self._scroll.setVisible(v)

        start = self.height()
        end = EXPANDED_HEIGHT if v else COLLAPSED_HEIGHT
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

        if v:
            QTimer.singleShot(80, self._scroll_to_bottom)
        self.expanded_changed.emit(v)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    # ── Helpers ──────────────────────────────────────────────────────
    def _set_height(self, h):
        try:
            self.setFixedHeight(int(h))
        except (TypeError, ValueError):
            pass

    def _scroll_to_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── Painting (top border + card-tinted bg) ───────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        # Card-coloured background with a hint of alpha (matches jsx 'cc' = 80%).
        bg = QColor(C.CARD); bg.setAlphaF(0.8)
        p.fillRect(self.rect(), bg)
        p.setPen(QPen(C.BORDER, 1))
        p.drawLine(0, 0, self.width(), 0)
