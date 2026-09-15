"""ConversationStage — the left half of the chat view.

Composes the ArcReactor with a state-text block (``ReactorStateText`` from
``jv3-reactor.jsx``) and a row of "memory chips". Paints the faint dot/line
grid + a soft radial vignette behind the reactor so the core feels embedded
in a HUD, matching the JS ``ChatView`` background treatment.
"""
from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.aeris_v6.reactor import ArcReactor
from ui.aeris_v6.tokens import (
    J, W_BOLD, ca, col, font_mono, rgba_str, JSTATES,
)
from ui.aeris_v6.widgets import StatusDot

_STATE_TEXT = {
    "IDLE":       ("AWAITING INPUT", "All systems nominal. Ready for your command."),
    "LISTENING":  ("LISTENING", "Voice stream active…"),
    "PROCESSING": ("PROCESSING", "Running inference…"),
    "SPEAKING":   ("GENERATING", "Streaming response to terminal…"),
}


class _Chip(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "background:rgba(255,255,255,0.03);"
            "border:1px solid rgba(255,255,255,0.08);border-radius:12px;"
        )
        lay = QHBoxLayout(self); lay.setContentsMargins(10, 4, 10, 4); lay.setSpacing(6)
        lay.addWidget(StatusDot(col("purple"), size=4))
        lbl = QLabel(text); lbl.setFont(font_mono(8))
        lbl.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        lay.addWidget(lbl)


class ConversationStage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "IDLE"
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addStretch(2)

        # reactor centred
        reactor_row = QHBoxLayout()
        reactor_row.addStretch(1)
        self.reactor = ArcReactor(size=420)
        reactor_row.addWidget(self.reactor)
        reactor_row.addStretch(1)
        root.addLayout(reactor_row)

        # state text
        self._main = QLabel("AWAITING INPUT"); self._main.setAlignment(Qt.AlignCenter)
        self._main.setFont(font_mono(20, W_BOLD, 4))
        self._main.setStyleSheet(f"color:{rgba_str('cyan',1)};background:transparent;")
        root.addSpacing(14)
        root.addWidget(self._main)
        self._sub = QLabel(_STATE_TEXT["IDLE"][1]); self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setFont(font_mono(10))
        self._sub.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        root.addSpacing(6)
        root.addWidget(self._sub)

        root.addStretch(2)

        # memory chips
        chips = QHBoxLayout(); chips.setSpacing(8); chips.addStretch(1)
        for c in ("Last: system check", "4 automations", "Context restored"):
            chips.addWidget(_Chip(c))
        chips.addStretch(1)
        root.addLayout(chips)
        root.addSpacing(16)

    def set_presence_state(self, state: str):
        """Forward the fused presence state to the reactor (dim when away)."""
        self.reactor.set_presence_state(state)

    def set_state(self, state: str, last_input: str = ""):
        self._state = state
        self.reactor.set_state(state)
        main, sub = _STATE_TEXT.get(state, _STATE_TEXT["IDLE"])
        if state == "PROCESSING" and last_input:
            sub = f'Parsing: "{last_input[:44]}{"…" if len(last_input) > 44 else ""}"'
        elif state == "LISTENING" and last_input:
            sub = f'"{last_input}"'
        c = JSTATES.get(state, JSTATES["IDLE"])["key"]
        self._main.setText(main)
        self._main.setStyleSheet(f"color:{rgba_str(c,1)};background:transparent;")
        self._sub.setText(sub)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # dot/line grid
        pen = QPen(ca("cyan", 0.04)); pen.setWidthF(1.0)
        p.setPen(pen)
        step = 48
        for x in range(0, self.width(), step):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            p.drawLine(0, y, self.width(), y)
        # radial vignette toward the reactor
        grad = QRadialGradient(QPointF(self.width() / 2, self.height() * 0.42),
                               self.width() * 0.5)
        g = ca(JSTATES.get(self._state, JSTATES["IDLE"])["key"], 0.05)
        grad.setColorAt(0.0, g)
        grad.setColorAt(0.7, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), grad)
        p.end()
