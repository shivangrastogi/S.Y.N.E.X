"""LogsBar — collapsible system-log strip at the bottom of the chat view.

Ports ``LogsBar`` from ``jv5-app.jsx``: a 32 px header (click to expand to
~158 px) showing the latest line collapsed, and a scrolling type-tagged feed
when open. Type colours match the JS ``TC`` map.
"""
from __future__ import annotations

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from ui.aeris_v6.tokens import J, W_BOLD, col, font_mono, rgba_str
from ui.aeris_v6.widgets import StatusDot

_TYPE_COLOR = {
    "SYS": "textMut", "NLU": "cyan", "ACT": "green", "MIC": "green",
    "TTS": "purple", "ERR": "red", "MEM": "amber", "BUP": "green",
}

_COLLAPSED = 32
_EXPANDED = 158


class _LogRow(QWidget):
    def __init__(self, time_str, typ, text, highlight, parent=None):
        super().__init__(parent)
        key = _TYPE_COLOR.get(typ, "textMut")
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 2, 0, 2); lay.setSpacing(8)
        t = QLabel(time_str); t.setFont(font_mono(8))
        t.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        lay.addWidget(t)
        badge = QLabel(typ); badge.setFont(font_mono(7, W_BOLD))
        badge.setStyleSheet(
            f"color:{rgba_str(key,1)};background:{rgba_str(key,0.1)};"
            f"border:1px solid {rgba_str(key,0.18)};border-radius:3px;padding:0 5px;"
        )
        lay.addWidget(badge)
        msg = QLabel(text); msg.setFont(font_mono(8))
        clr = key if highlight else "textSec"
        msg.setStyleSheet(f"color:{rgba_str(clr,1)};background:transparent;")
        lay.addWidget(msg, 1)


class LogsBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._open = False
        self._count = 0
        self.setFixedHeight(_COLLAPSED)
        self.setStyleSheet(
            f"LogsBar{{background:{rgba_str((6,10,18), 0.92)};"
            f"border-top:1px solid {rgba_str('border', 0.6)};}}"
        )
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self._header = QFrame(); self._header.setFixedHeight(_COLLAPSED)
        self._header.setCursor(Qt.PointingHandCursor)
        hl = QHBoxLayout(self._header); hl.setContentsMargins(14, 0, 14, 0); hl.setSpacing(7)
        hl.addWidget(StatusDot(col("green"), size=4))
        title = QLabel("SYSTEM LOG"); title.setFont(font_mono(8, W_BOLD, 1.8))
        title.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        hl.addWidget(title)
        self._counter = QLabel("0"); self._counter.setFont(font_mono(8))
        self._counter.setStyleSheet(f"color:{rgba_str('textMut',0.6)};background:transparent;")
        hl.addWidget(self._counter)
        hl.addStretch(1)
        self._preview = QLabel(""); self._preview.setFont(font_mono(8))
        self._preview.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        hl.addWidget(self._preview)
        root.addWidget(self._header)

        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("background:transparent;")
        self._host = QWidget(); self._host.setStyleSheet("background:transparent;")
        self._rows = QVBoxLayout(self._host)
        self._rows.setContentsMargins(14, 4, 14, 4); self._rows.setSpacing(0)
        self._rows.addStretch(1)
        self._scroll.setWidget(self._host)
        self._scroll.setVisible(False)
        root.addWidget(self._scroll, 1)

        self._anim = QPropertyAnimation(self, b"maximumHeight", self)
        self._anim.setDuration(300); self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim_min = QPropertyAnimation(self, b"minimumHeight", self)
        self._anim_min.setDuration(300); self._anim_min.setEasingCurve(QEasingCurve.OutCubic)

    def mousePressEvent(self, e):
        if self._header.geometry().contains(e.pos()):
            self.toggle()

    def toggle(self):
        self._open = not self._open
        target = _EXPANDED if self._open else _COLLAPSED
        self._scroll.setVisible(self._open)
        self._preview.setVisible(not self._open)
        for a in (self._anim, self._anim_min):
            a.stop(); a.setStartValue(self.height()); a.setEndValue(target); a.start()

    def add_log(self, typ: str, text: str, highlight: bool = False):
        import time as _t
        ts = _t.strftime("%H:%M:%S")
        self._rows.insertWidget(self._rows.count() - 1, _LogRow(ts, typ, text, highlight))
        self._count += 1
        self._counter.setText(str(self._count))
        self._preview.setText(text[:60])
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
