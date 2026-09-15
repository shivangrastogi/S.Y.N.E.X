"""MissionControlChatPanel — the right-hand conversation surface.

Ports ``jv4-chat.jsx``: AI replies render as 3-part mission cards (status band
+ content + meta footer with a confidence bar), user messages are minimal
right-aligned bubbles, plus a thinking indicator, smart-suggestion chips and
the input bar with mic + send. Streaming is supported by mutating the last AI
card's text in place.

Signals:
    send(str) — user submitted text
    mic()     — mic button pressed
"""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from ui.aeris_v6.tokens import (
    J, W_BOLD, W_MEDIUM, W_SEMIBOLD, ca, col, font_mono, font_ui, rgba_str,
)
from ui.aeris_v6.widgets import IconWidget, StatusDot

_ACT_STYLES = {
    "executed":             ("EXECUTED", "green"),
    "knowledge":            ("KNOWLEDGE", "cyan"),
    "knowledge_retrieved":  ("RETRIEVED", "cyan"),
    "chat_fallback":        ("CONVERSATION", "purple"),
    "slot_filling":         ("CLARIFYING", "amber"),
    "clarifying":           ("CLARIFYING", "amber"),
    "clarification_needed": ("CLARIFYING", "amber"),
    "rejected":             ("UNCLEAR", "amber"),
    "error":                ("ERROR", "red"),
}


def _act_style(act: str):
    return _ACT_STYLES.get(act, ((act or "PROCESSED").upper(), "cyan"))


class _ConfBar(QWidget):
    def __init__(self, conf: float, accent: str, parent=None):
        super().__init__(parent)
        self._conf = max(0.0, min(100.0, conf))
        self._accent = accent
        self.setFixedSize(36, 4)

    def paintEvent(self, _ev):
        from PyQt5.QtGui import QPainter
        from PyQt5.QtCore import QRectF
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawRoundedRect(QRectF(0, 0, 36, 4), 2, 2)
        w = 36 * self._conf / 100.0
        p.setBrush(col(self._accent))
        p.drawRoundedRect(QRectF(0, 0, w, 4), 2, 2)
        p.end()


class AIMissionCard(QFrame):
    """3-part AI reply card with a bright left accent stripe."""

    def __init__(self, text: str, meta: dict, time_str: str, parent=None):
        super().__init__(parent)
        self._meta = meta or {}
        act = self._meta.get("act") or self._meta.get("action") or "executed"
        label, accent = _act_style(act)
        self._accent = accent
        self.setStyleSheet(
            f"AIMissionCard{{background:{rgba_str('panel', 0.85)};"
            f"border:1px solid {rgba_str('border', 0.8)};border-radius:8px;}}"
        )
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        # status band
        band = QFrame()
        band.setStyleSheet(
            f"background:{rgba_str(accent, 0.07)};"
            f"border-bottom:1px solid rgba(255,255,255,0.04);"
            f"border-top-left-radius:8px;border-top-right-radius:8px;"
        )
        bl = QHBoxLayout(band); bl.setContentsMargins(14, 6, 14, 6); bl.setSpacing(8)
        bl.addWidget(StatusDot(col(accent), size=5))
        slbl = QLabel(label); slbl.setFont(font_mono(8, W_BOLD, 2))
        slbl.setStyleSheet(f"color:{rgba_str(accent,1)};background:transparent;")
        bl.addWidget(slbl); bl.addStretch(1)
        ms = self._meta.get("ms") if self._meta.get("ms") is not None else self._meta.get("latency_ms")
        if ms is not None:
            mlbl = QLabel(f"{int(ms)}ms"); mlbl.setFont(font_mono(8))
            mlbl.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
            bl.addWidget(mlbl)
        outer.addWidget(band)

        # content
        body = QFrame(); bd = QHBoxLayout(body); bd.setContentsMargins(14, 11, 14, 11)
        self._content = QLabel(text)
        self._content.setWordWrap(True)
        self._content.setFont(font_mono(11))
        self._content.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;line-height:1.6;")
        self._content.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bd.addWidget(self._content)
        outer.addWidget(body)

        # meta footer
        conf = self._meta.get("conf")
        if conf is None:
            conf = self._meta.get("confidence")
        intent = self._meta.get("intent", "general")
        if conf is not None:
            foot = QFrame()
            foot.setStyleSheet(
                "background:rgba(0,0,0,0.15);border-top:1px solid rgba(255,255,255,0.03);"
                "border-bottom-left-radius:8px;border-bottom-right-radius:8px;"
            )
            fl = QHBoxLayout(foot); fl.setContentsMargins(14, 5, 14, 6); fl.setSpacing(5)
            il = QLabel(f"intent: {intent}"); il.setFont(font_mono(8))
            il.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
            fl.addWidget(il); fl.addStretch(1)
            fl.addWidget(_ConfBar(float(conf), accent))
            cl = QLabel(f"{conf:.0f}%" if isinstance(conf, (int, float)) else str(conf))
            cl.setFont(font_mono(8, W_BOLD))
            cl.setStyleSheet(f"color:{rgba_str(accent,1)};background:transparent;")
            fl.addWidget(cl)
            outer.addWidget(foot)

    def set_text(self, text: str):
        self._content.setText(text)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        from PyQt5.QtGui import QPainter
        from PyQt5.QtCore import QRectF
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen); p.setBrush(col(self._accent))
        p.drawRoundedRect(QRectF(0, 0, 3, self.height()), 1.5, 1.5)
        p.end()


class UserMessage(QFrame):
    def __init__(self, text: str, time_str: str, parent=None):
        super().__init__(parent)
        bubble = QFrame()
        bubble.setStyleSheet(
            f"background:{rgba_str('cyan', 0.06)};"
            f"border:1px solid {rgba_str('cyan', 0.22)};"
            f"border-radius:14px;border-bottom-right-radius:4px;"
        )
        bl = QHBoxLayout(bubble); bl.setContentsMargins(14, 9, 14, 9)
        lbl = QLabel(text); lbl.setWordWrap(True); lbl.setFont(font_mono(11))
        lbl.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
        bl.addWidget(lbl)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        lay.addWidget(bubble)


class ThinkingIndicator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"ThinkingIndicator{{background:{rgba_str('panel', 0.85)};"
            f"border:1px solid {rgba_str('border', 0.8)};"
            f"border-left:3px solid {rgba_str('magenta',1)};border-radius:8px;}}"
        )
        lay = QHBoxLayout(self); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(5)
        self._dots = [StatusDot(col("magenta"), size=5) for _ in range(3)]
        for d in self._dots:
            lay.addWidget(d)
        t = QLabel("thinking…"); t.setFont(font_mono(9))
        t.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        lay.addSpacing(6); lay.addWidget(t); lay.addStretch(1)


class _SuggestChip(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFont(font_mono(9))
        self.setFlat(True)
        self.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.025);"
            "border:1px solid rgba(255,255,255,0.08);border-radius:13px;"
            f"color:{rgba_str('textSec',1)};padding:4px 10px;}}"
            f"QPushButton:hover{{background:{rgba_str('cyan',0.08)};"
            f"border:1px solid {rgba_str('cyan',0.3)};color:{rgba_str('cyan',1)};}}"
        )


class _RoundIconButton(QPushButton):
    def __init__(self, icon_name: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)
        self._icon = IconWidget(icon_name, 14, col("textSec"), self)
        self._icon.move(9, 9)
        self.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.04);"
            "border:1px solid rgba(255,255,255,0.1);border-radius:16px;}"
            f"QPushButton:hover{{border:1px solid {rgba_str('cyan',0.4)};}}"
        )


class ChatInputBar(QWidget):
    send = pyqtSignal(str)
    mic = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._busy = False
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 10, 14, 14); lay.setSpacing(8)

        # suggestions
        self._sugg_row = QHBoxLayout(); self._sugg_row.setSpacing(6)
        for s in ("What did I do today?", "System health check", "Resume last task"):
            chip = _SuggestChip(s)
            chip.clicked.connect(lambda _, t=s: self.send.emit(t))
            self._sugg_row.addWidget(chip)
        self._sugg_row.addStretch(1)
        lay.addLayout(self._sugg_row)

        # input row
        self._bar = QFrame()
        self._bar.setStyleSheet(
            f"QFrame{{background:{rgba_str((8,12,22), 0.95)};"
            f"border:1px solid {rgba_str('cyan', 0.3)};border-radius:14px;}}"
        )
        bl = QHBoxLayout(self._bar); bl.setContentsMargins(14, 6, 6, 6); bl.setSpacing(7)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask anything…")
        self._input.setFont(font_mono(11))
        self._input.setStyleSheet(
            f"QLineEdit{{background:transparent;border:0;color:{rgba_str('textPri',1)};}}"
        )
        self._input.returnPressed.connect(self._submit)
        bl.addWidget(self._input, 1)
        self._mic_btn = _RoundIconButton("mic")
        self._mic_btn.clicked.connect(self.mic)
        bl.addWidget(self._mic_btn)
        self._send_btn = _RoundIconButton("send")
        self._send_btn.clicked.connect(self._submit)
        bl.addWidget(self._send_btn)
        lay.addWidget(self._bar)

        # hints
        hint_row = QHBoxLayout(); hint_row.setSpacing(14)
        for h in ("↵ send", "Ctrl+M mic", "Hinglish supported"):
            hl = QLabel(h); hl.setFont(font_mono(8))
            hl.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
            hint_row.addWidget(hl)
        hint_row.addStretch(1)
        lay.addLayout(hint_row)

    def _submit(self):
        if self._busy:
            return
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.send.emit(text)

    def set_busy(self, busy: bool, listening: bool = False):
        self._busy = busy
        self._input.setDisabled(busy or listening)
        if listening:
            self._input.setPlaceholderText("Listening…")
            self._mic_btn.setStyleSheet(
                f"QPushButton{{background:{rgba_str('green',0.2)};"
                f"border:1px solid {rgba_str('green',0.6)};border-radius:16px;}}"
            )
        else:
            self._input.setPlaceholderText("A.E.R.I.S responding…" if busy else "Ask anything…")
            self._mic_btn.setStyleSheet(
                "QPushButton{background:rgba(255,255,255,0.04);"
                "border:1px solid rgba(255,255,255,0.1);border-radius:16px;}"
                f"QPushButton:hover{{border:1px solid {rgba_str('cyan',0.4)};}}"
            )
        if not busy and not listening:
            self._input.setFocus()

    def focus_input(self):
        self._input.setFocus()


class MissionControlChatPanel(QFrame):
    send = pyqtSignal(str)
    mic = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(390)
        self.setStyleSheet(
            f"MissionControlChatPanel{{background:{rgba_str('panel', 0.65)};"
            f"border-left:1px solid {rgba_str('border', 0.7)};}}"
        )
        self._count = 0
        self._stream_card = None
        self._thinking = None

        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # header
        header = QFrame(); header.setFixedHeight(56)
        header.setStyleSheet(
            f"QFrame{{background:{rgba_str((8,12,22), 0.55)};"
            f"border-bottom:1px solid {rgba_str('border', 0.6)};}}"
        )
        hl = QHBoxLayout(header); hl.setContentsMargins(18, 0, 18, 0)
        htext = QVBoxLayout(); htext.setSpacing(3)
        t1 = QLabel("MISSION CONTROL"); t1.setFont(font_mono(10, W_BOLD, 2.5))
        t1.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
        self._sub = QLabel("Session · 0 messages · encrypted"); self._sub.setFont(font_mono(8))
        self._sub.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        htext.addWidget(t1); htext.addWidget(self._sub)
        hl.addLayout(htext); hl.addStretch(1)
        live = QFrame()
        live.setStyleSheet(
            f"background:{rgba_str('red',0.1)};border:1px solid {rgba_str('red',0.3)};border-radius:6px;"
        )
        ll = QHBoxLayout(live); ll.setContentsMargins(7, 2, 7, 2); ll.setSpacing(5)
        ll.addWidget(StatusDot(col("red"), size=4))
        livelbl = QLabel("LIVE"); livelbl.setFont(font_mono(7, W_BOLD, 1.2))
        livelbl.setStyleSheet(f"color:{rgba_str('red',1)};background:transparent;")
        ll.addWidget(livelbl)
        hl.addWidget(live)
        root.addWidget(header)

        # messages scroll
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("background:transparent;")
        self._msg_host = QWidget()
        self._msg_host.setStyleSheet("background:transparent;")
        self._msgs = QVBoxLayout(self._msg_host)
        self._msgs.setContentsMargins(14, 16, 14, 16); self._msgs.setSpacing(14)
        self._msgs.addStretch(1)
        self._scroll.setWidget(self._msg_host)
        root.addWidget(self._scroll, 1)

        # input
        self._input_bar = ChatInputBar()
        self._input_bar.send.connect(self.send)
        self._input_bar.mic.connect(self.mic)
        root.addWidget(self._input_bar)

    # ── message API ────────────────────────────────────────────────
    def _insert(self, widget: QWidget, align_right=False):
        # insert before the trailing stretch
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0)
        if align_right:
            row.addStretch(1); row.addWidget(widget)
        else:
            row.addWidget(widget); row.addStretch(1)
        container = QWidget(); container.setStyleSheet("background:transparent;")
        container.setLayout(row)
        self._msgs.insertWidget(self._msgs.count() - 1, container)
        self._count += 1
        self._sub.setText(f"Session · {self._count} messages · encrypted")
        QTimer.singleShot(20, self._scroll_to_bottom)

    def add_user(self, text: str, time_str: str = ""):
        self._insert(UserMessage(text, time_str), align_right=True)

    def add_ai(self, text: str, meta: dict, time_str: str = "") -> AIMissionCard:
        card = AIMissionCard(text, meta, time_str)
        self._insert(card)
        return card

    def begin_stream(self, meta: dict) -> AIMissionCard:
        self.clear_thinking()
        self._stream_card = self.add_ai("", meta)
        return self._stream_card

    def update_stream(self, text: str):
        if self._stream_card:
            self._stream_card.set_text(text + " ▌")
            self._scroll_to_bottom()

    def end_stream(self, final_text: str):
        if self._stream_card:
            self._stream_card.set_text(final_text)
            self._stream_card = None

    def show_thinking(self):
        if self._thinking is None:
            self._thinking = ThinkingIndicator()
            self._insert(self._thinking)

    def clear_thinking(self):
        if self._thinking is not None:
            w = self._thinking.parentWidget()
            self._thinking.setParent(None); self._thinking.deleteLater()
            if w:
                w.setParent(None); w.deleteLater()
            self._thinking = None

    def set_busy(self, busy, listening=False):
        self._input_bar.set_busy(busy, listening)

    def focus_input(self):
        self._input_bar.focus_input()

    def _scroll_to_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
