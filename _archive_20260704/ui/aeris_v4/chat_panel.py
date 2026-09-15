"""Right chat panel — messages, mic button, input bar."""
from __future__ import annotations

import math
import random
import time
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPointF, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QSizePolicy
)

from .theme import C, rgba, inter, mono


class ChatPanel(QWidget):
    send_text = pyqtSignal(str)
    mic_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(380)
        self._state = "IDLE"
        self._messages: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QFrame(); header.setFixedHeight(56)
        hlay = QHBoxLayout(header); hlay.setContentsMargins(20, 0, 16, 0); hlay.setSpacing(8)
        hleft = QVBoxLayout(); hleft.setSpacing(2)
        t1 = QLabel("CONVERSATION"); t1.setFont(inter(11, 700))
        t1.setStyleSheet(f"color: {C.TEXT_PRI.name()}; letter-spacing: 2px;")
        self._subtitle = QLabel("Session • 0 messages"); self._subtitle.setFont(mono(10, 400))
        self._subtitle.setStyleSheet(f"color: {C.TEXT_MUT.name()};")
        hleft.addWidget(t1); hleft.addWidget(self._subtitle)
        hlay.addLayout(hleft); hlay.addStretch(1)

        # Busy pill (THINKING/SPEAKING) — only visible when state is busy.
        self._busy_pill = _Pill("THINKING", C.CYAN, blink=True)
        self._busy_pill.setVisible(False)
        hlay.addWidget(self._busy_pill)

        self._state_pill = _Pill("LIVE", C.RED, blink=True)
        hlay.addWidget(self._state_pill)

        header.setStyleSheet("background: transparent;")
        header_wrap = _BorderedFrame(bottom=True); hw_l = QVBoxLayout(header_wrap); hw_l.setContentsMargins(0,0,0,0)
        hw_l.addWidget(header)
        root.addWidget(header_wrap)

        # Messages scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.verticalScrollBar().setStyleSheet(_SCROLLBAR_CSS)

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(16, 16, 16, 16)
        self._msg_layout.setSpacing(16)
        # Processing indicator sits at the bottom of the message list and is
        # shown/hidden via set_state(). Lives BEFORE the stretch so the
        # 'sender row + bubble' read in document order.
        self._processing_indicator = _ProcessingDots()
        self._processing_indicator.setVisible(False)
        self._msg_layout.addWidget(self._processing_indicator)
        self._msg_layout.addStretch(1)
        self._scroll.setWidget(self._msg_container)
        root.addWidget(self._scroll, 1)

        # Streaming state: which bubble is currently streaming (if any).
        self._streaming_bubble: _MessageBubble | None = None
        self._stream_timer: QTimer | None = None
        self._stream_buffer = ""
        self._stream_full   = ""
        self._stream_idx    = 0

        # Input bar
        self._input_bar = _InputBar()
        self._input_bar.send.connect(self._handle_send)
        self._input_bar.mic.connect(self.mic_clicked.emit)
        root.addWidget(self._input_bar)

        # Seed messages
        self.add_message("aeris", "AERIS systems online. Semantic core v3.1 initialized.",
                         tag=("sys_boot • 100ms", C.GREEN))
        self.add_message("aeris", "Kya seva kar sakta hoon aapki, sir?")

    # ── Public API ────────────────────────────────────────────────────
    def add_message(self, role: str, text: str, tag: tuple[str, QColor] | None = None):
        self._messages.append({"role": role, "text": text, "tag": tag,
                               "time": time.strftime("%H:%M:%S")})
        bubble = _MessageBubble(role, text, tag, self._messages[-1]["time"])
        # insert before stretch
        idx = self._msg_layout.count() - 1
        self._msg_layout.insertWidget(idx, bubble)
        self._subtitle.setText(f"Session • {len(self._messages)} messages")
        QTimer.singleShot(50, self._scroll_to_bottom)

    def set_state(self, key: str):
        self._state = key
        self._input_bar.set_state(key)
        # Header busy pill — only shown for PROCESSING / SPEAKING.
        if key == "PROCESSING":
            self._busy_pill.set_data("THINKING", C.CYAN)
            self._busy_pill.setVisible(True)
        elif key == "SPEAKING":
            self._busy_pill.set_data("SPEAKING", C.PURPLE)
            self._busy_pill.setVisible(True)
        else:
            self._busy_pill.setVisible(False)
        # Processing dots — only while PROCESSING and no streaming bubble yet.
        self._processing_indicator.setVisible(
            key == "PROCESSING" and self._streaming_bubble is None
        )
        if self._processing_indicator.isVisible():
            QTimer.singleShot(50, self._scroll_to_bottom)

    # ── Streaming API (typewriter into a single AERIS bubble) ────────
    def stream_message(self, text: str, tag: tuple[str, QColor] | None = None,
                       speed_ms: int = 18):
        """Add an AERIS bubble whose text appears character-by-character.

        Caller can chain another stream_message after the previous finishes;
        we cancel any in-flight stream when a new one starts.
        """
        self._cancel_stream()
        self._processing_indicator.setVisible(False)
        self._stream_full = text
        self._stream_idx = 0
        self._stream_buffer = ""

        bubble = _MessageBubble("aeris", "", tag, time.strftime("%H:%M:%S"),
                                streaming=True)
        idx = self._msg_layout.count() - 2  # before processing dots + stretch
        self._msg_layout.insertWidget(idx, bubble)
        self._streaming_bubble = bubble
        self._messages.append({"role": "aeris", "text": text, "tag": tag,
                               "time": time.strftime("%H:%M:%S")})
        self._subtitle.setText(f"Session • {len(self._messages)} messages")

        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._stream_tick)
        self._stream_timer.start(speed_ms)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _stream_tick(self):
        if self._streaming_bubble is None:
            self._cancel_stream(); return
        self._stream_idx += 1
        self._stream_buffer = self._stream_full[: self._stream_idx]
        self._streaming_bubble.set_text(self._stream_buffer)
        if self._stream_idx >= len(self._stream_full):
            self._streaming_bubble.set_streaming(False)
            self._cancel_stream()

    def _cancel_stream(self):
        if self._stream_timer is not None:
            self._stream_timer.stop()
            self._stream_timer = None
        self._streaming_bubble = None

    # ── Helpers ───────────────────────────────────────────────────────
    def _scroll_to_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _handle_send(self, text: str):
        self.add_message("user", text)
        self.send_text.emit(text)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), C.PANEL)
        p.setPen(QPen(C.BORDER, 1))
        p.drawLine(0, 0, 0, self.height())


class _BorderedFrame(QFrame):
    def __init__(self, bottom=False, parent=None):
        super().__init__(parent)
        self._bottom = bottom
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, _):
        p = QPainter(self)
        if self._bottom:
            p.setPen(QPen(C.BORDER, 1))
            p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class _Pill(QWidget):
    def __init__(self, text: str, color: QColor, blink: bool = False, parent=None):
        super().__init__(parent)
        self._text = text; self._color = color; self._blink = blink
        self._phase = 0.0
        self._start = time.monotonic()
        self.setFixedHeight(20)
        self.setMinimumWidth(56)
        if blink:
            t = QTimer(self); t.timeout.connect(self._tick); t.start(60)

    def _tick(self):
        self._phase = (time.monotonic() - self._start) * 2 * math.pi / 1.2
        self.update()

    def set_data(self, text: str, color: QColor) -> None:
        self._text = text
        self._color = color
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(rgba(self._color, 0.4), 1))
        p.setBrush(rgba(self._color, 0.12))
        p.drawRoundedRect(r, 9, 9)
        alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(self._phase)) if self._blink else 1.0
        dot = QColor(self._color); dot.setAlphaF(alpha)
        p.setPen(Qt.NoPen); p.setBrush(dot)
        p.drawEllipse(QPointF(10, self.height() / 2), 3, 3)
        p.setPen(self._color); p.setFont(mono(9, 700))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(self._text)
        p.drawText(QRectF(18, 0, self.width() - 22, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self._text)
        need = 22 + tw + 10
        if need != self.minimumWidth():
            self.setMinimumWidth(need); self.setFixedWidth(need)


class _MessageBubble(QWidget):
    def __init__(self, role: str, text: str, tag, time_label: str,
                 streaming: bool = False, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        is_aeris = role == "aeris"

        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(5)
        v.setAlignment(Qt.AlignLeft if is_aeris else Qt.AlignRight)

        # sender row
        sender_row = QHBoxLayout(); sender_row.setSpacing(6)
        if is_aeris:
            self._sender_dot = _SmallDot(C.CYAN, blink=streaming)
            sender_row.addWidget(self._sender_dot)
        else:
            self._sender_dot = None
        name = QLabel("A.E.R.I.S" if is_aeris else "YOU")
        name.setFont(mono(10, 700))
        name.setStyleSheet(f"color: {C.CYAN.name() if is_aeris else C.TEXT_SEC.name()}; letter-spacing: 1px;")
        sender_row.addWidget(name)
        t_label = QLabel(time_label); t_label.setFont(mono(9, 400))
        t_label.setStyleSheet(f"color: {C.TEXT_MUT.name()};")
        sender_row.addWidget(t_label)
        sender_row.addStretch(1)
        # Right-align whole block for user
        if not is_aeris:
            sender_row.setDirection(QHBoxLayout.RightToLeft)
        v.addLayout(sender_row)

        # bubble
        self._body = _BubbleBody(is_aeris, text, streaming=streaming)
        bubble_row = QHBoxLayout(); bubble_row.setContentsMargins(0, 0, 0, 0)
        if is_aeris:
            bubble_row.addWidget(self._body); bubble_row.addStretch(1)
        else:
            bubble_row.addStretch(1); bubble_row.addWidget(self._body)
        v.addLayout(bubble_row)

        # tag pill (hidden while streaming so it doesn't appear before done)
        self._pill_row = None
        if tag and not streaming:
            self._add_tag_pill(v, is_aeris, tag)

    def _add_tag_pill(self, v, is_aeris, tag):
        tag_text, tag_color = tag
        pill = _Pill(tag_text, tag_color, blink=False)
        self._pill_row = QHBoxLayout(); self._pill_row.setContentsMargins(0, 0, 0, 0)
        if is_aeris:
            self._pill_row.addWidget(pill); self._pill_row.addStretch(1)
        else:
            self._pill_row.addStretch(1); self._pill_row.addWidget(pill)
        v.addLayout(self._pill_row)

    # ── Streaming hooks (used by ChatPanel.stream_message) ───────────
    def set_text(self, text: str) -> None:
        self._body.set_text(text)

    def set_streaming(self, on: bool) -> None:
        self._body.set_streaming(on)
        if self._sender_dot is not None:
            self._sender_dot.set_blink(on)


class _BubbleBody(QWidget):
    def __init__(self, is_aeris: bool, text: str, streaming: bool = False, parent=None):
        super().__init__(parent)
        self._is_aeris = is_aeris
        self._streaming = streaming
        self._text = text

        self._label = QLabel(self._render())
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setFont(mono(12, 400))
        self._label.setStyleSheet(f"color: {C.TEXT_PRI.name()}; line-height: 1.6;")
        self._label.setMaximumWidth(300)
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 10, 14, 10)
        lay.addWidget(self._label)
        self.setMaximumWidth(330)

        # While streaming, blink the cursor by repainting label html every ~280ms.
        self._cursor_on = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        if streaming:
            self._cursor_timer.start(280)

    # ── Public API ───────────────────────────────────────────────────
    def set_text(self, text: str) -> None:
        self._text = text
        self._label.setText(self._render())

    def set_streaming(self, on: bool) -> None:
        self._streaming = on
        if on:
            self._cursor_on = True
            if not self._cursor_timer.isActive():
                self._cursor_timer.start(280)
        else:
            self._cursor_timer.stop()
        self._label.setText(self._render())

    def _blink_cursor(self):
        self._cursor_on = not self._cursor_on
        self._label.setText(self._render())

    def _render(self) -> str:
        # Escape just enough that user input doesn't break the html.
        body = (self._text or "").replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")
        if self._streaming:
            cursor = "▌" if self._cursor_on else "&nbsp;"
            return f'{body}<span style="color:{C.CYAN.name()}">{cursor}</span>'
        return body

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        if self._is_aeris:
            p.setPen(QPen(C.BORDER, 1))
            p.setBrush(rgba(C.CARD, 0.9))
        else:
            p.setPen(QPen(rgba(C.CYAN, 0.28), 1))
            p.setBrush(rgba(C.CYAN, 0.08))
        p.drawRoundedRect(r, 14, 14)


class _SmallDot(QWidget):
    """8x8 dot. Optional blink animation (used for streaming sender dot)."""
    def __init__(self, color, blink: bool = False, parent=None):
        super().__init__(parent)
        self._color = color
        self._blink = blink
        self._start = time.monotonic()
        self.setFixedSize(8, 8)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        if blink:
            self._timer.start(60)

    def set_blink(self, on: bool) -> None:
        self._blink = on
        if on:
            if not self._timer.isActive():
                self._timer.start(60)
        else:
            self._timer.stop()
            self.update()

    def paintEvent(self, _):
        if self._blink:
            phase = (time.monotonic() - self._start) * 2 * math.pi / 0.7
            alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(phase))
        else:
            alpha = 1.0
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        glow = QColor(self._color); glow.setAlphaF(alpha * 0.5)
        p.setPen(Qt.NoPen); p.setBrush(glow)
        p.drawEllipse(self.rect())
        c = QColor(self._color); c.setAlphaF(alpha)
        p.setBrush(c)
        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))


class _ProcessingDots(QWidget):
    """Three blinking dots in an AERIS-styled bubble — shown while PROCESSING.

    Mirrors the jsx 'Processing dots' indicator: a sender row + a small
    dark bubble containing 3 cyan dots that blink with staggered phase.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(5)

        # sender row (matches AERIS message header)
        row = QHBoxLayout(); row.setSpacing(6)
        row.addWidget(_SmallDot(C.CYAN, blink=True))
        name = QLabel("A.E.R.I.S")
        name.setFont(mono(10, 700))
        name.setStyleSheet(f"color: {C.CYAN.name()}; letter-spacing: 1px;")
        row.addWidget(name); row.addStretch(1)
        v.addLayout(row)

        # bubble with 3 staggered-blink dots
        bubble = _DotsBubble()
        bubble_row = QHBoxLayout(); bubble_row.setContentsMargins(0, 0, 0, 0)
        bubble_row.addWidget(bubble); bubble_row.addStretch(1)
        v.addLayout(bubble_row)


class _DotsBubble(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(74, 38)
        self._start = time.monotonic()
        t = QTimer(self); t.timeout.connect(self.update); t.start(60)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # bubble bg
        p.setPen(QPen(C.BORDER, 1))
        p.setBrush(rgba(C.CARD, 0.9))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
        # 3 dots, each phase-shifted by 333ms
        cy = self.height() / 2
        for i in range(3):
            cx = 18 + i * 14
            phase = (time.monotonic() - self._start - i * 0.33) * 2 * math.pi / 1.0
            alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(phase))
            glow = QColor(C.CYAN); glow.setAlphaF(alpha * 0.5)
            p.setPen(Qt.NoPen); p.setBrush(glow)
            p.drawEllipse(QPointF(cx, cy), 5, 5)
            c = QColor(C.CYAN); c.setAlphaF(alpha)
            p.setBrush(c)
            p.drawEllipse(QPointF(cx, cy), 3, 3)


class _ListeningWaveform(QWidget):
    """Pseudo-random green waveform shown above the input bar while listening."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        self._start = time.monotonic()
        # Pre-randomize per-bar phase + speed so we don't reseed every frame.
        self._bars = [
            (random.uniform(0.4, 0.9),     # speed factor
             random.uniform(0, 2 * math.pi),  # phase offset
             random.uniform(6, 22))           # max height
            for _ in range(18)
        ]
        t = QTimer(self); t.timeout.connect(self.update); t.start(60)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # bg pill
        p.setPen(QPen(rgba(C.GREEN, 0.25), 1))
        p.setBrush(rgba(C.GREEN, 0.07))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)

        p.setPen(C.GREEN)
        p.setFont(mono(9, 700))
        p.drawText(QRectF(10, 0, 70, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, "LISTENING")

        # bars
        t = time.monotonic() - self._start
        x0 = 88
        bar_w = 3; gap = 5
        cy = self.height() / 2
        p.setPen(Qt.NoPen)
        col = QColor(C.GREEN); col.setAlphaF(0.85)
        for i, (speed, phase, max_h) in enumerate(self._bars):
            local = math.sin(t * (2 + speed * 4) + phase)
            h = 5 + (max_h - 5) * (0.5 + 0.5 * local)
            x = x0 + i * (bar_w + gap)
            if x + bar_w > self.width() - 10:
                break
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x, cy - h / 2, bar_w, h), 1.5, 1.5)


class _InputBar(QWidget):
    send = pyqtSignal(str)
    mic  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Height varies with the waveform's visibility; use a min and let
        # the parent layout grow us when listening.
        self.setMinimumHeight(86)
        self._state = "IDLE"

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(8)

        # Listening waveform (hidden unless state == LISTENING).
        self._waveform = _ListeningWaveform()
        self._waveform.setVisible(False)
        root.addWidget(self._waveform)

        # Input row
        input_row = _InputRow()
        self._field = input_row.field
        self._field.returnPressed.connect(self._emit_send)

        input_row.mic_clicked.connect(self.mic.emit)
        input_row.send_clicked.connect(self._emit_send)
        self._input_row = input_row
        root.addWidget(input_row)

        # Hints row
        hints = QHBoxLayout(); hints.setSpacing(16)
        for h in ("↵ send", "⌥ mic", "Hinglish OK"):
            lbl = QLabel(h); lbl.setFont(mono(9, 400))
            lbl.setStyleSheet(f"color: {C.TEXT_MUT.name()};")
            hints.addWidget(lbl)
        hints.addStretch(1)
        root.addLayout(hints)

    def set_state(self, key: str):
        self._state = key
        self._input_row.set_state(key)
        placeholder = {
            "LISTENING":  "Listening…",
            "PROCESSING": "A.E.R.I.S is thinking…",
            "SPEAKING":   "A.E.R.I.S is responding…",
        }.get(key, "Message A.E.R.I.S…")
        self._field.setPlaceholderText(placeholder)
        self._field.setDisabled(key in ("LISTENING", "PROCESSING", "SPEAKING"))
        # Toggle listening waveform
        self._waveform.setVisible(key == "LISTENING")

    def _emit_send(self):
        txt = self._field.text().strip()
        if not txt:
            return
        self._field.clear()
        self.send.emit(txt)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setPen(QPen(C.BORDER, 1))
        p.drawLine(0, 0, self.width(), 0)


class _InputRow(QWidget):
    mic_clicked = pyqtSignal()
    send_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._state = "IDLE"

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 6, 6); lay.setSpacing(8)

        self.field = QLineEdit()
        self.field.setPlaceholderText("Message A.E.R.I.S…")
        self.field.setFont(mono(13, 400))
        self.field.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; border: none; color: {C.TEXT_PRI.name()};
            }}
            QLineEdit::placeholder {{ color: {C.TEXT_MUT.name()}; }}
        """)
        lay.addWidget(self.field, 1)

        self._mic = _RoundIconButton(kind="mic")
        self._mic.clicked.connect(self.mic_clicked.emit)
        lay.addWidget(self._mic)

        self._send = _RoundIconButton(kind="send")
        self._send.clicked.connect(self.send_clicked.emit)
        lay.addWidget(self._send)

    def set_state(self, key: str):
        self._state = key
        self._mic.set_active(key == "LISTENING")
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        busy = self._state in ("PROCESSING", "SPEAKING")
        p.setPen(QPen(rgba(C.CYAN, 0.15 if busy else 0.38), 1))
        p.setBrush(C.BG)
        p.drawRoundedRect(r, 14, 14)


class _RoundIconButton(QPushButton):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._active = False
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("QPushButton { border: none; }")

    def set_active(self, v: bool):
        self._active = v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(1, 1, -1, -1)
        if self._kind == "mic":
            if self._active:
                p.setPen(QPen(rgba(C.GREEN, 0.7), 1))
                p.setBrush(rgba(C.GREEN, 0.25))
            else:
                p.setPen(QPen(rgba(C.CYAN, 0.5), 1))
                p.setBrush(rgba(C.CYAN, 0.15))
            p.drawEllipse(r)
            # mic glyph (capsule + arc)
            col = C.GREEN if self._active else C.CYAN
            cx, cy = self.width()/2, self.height()/2
            p.setPen(QPen(col, 1.8))
            p.setBrush(col)
            p.drawRoundedRect(QRectF(cx-3, cy-8, 6, 12), 3, 3)
            p.setBrush(Qt.NoBrush)
            p.drawArc(QRectF(cx-7, cy-6, 14, 16), 210*16, 120*16)
            p.drawLine(QPointF(cx, cy+7), QPointF(cx, cy+10))
        else:  # send
            p.setPen(Qt.NoPen); p.setBrush(C.CYAN)
            p.drawEllipse(r)
            # arrow
            p.setPen(QPen(C.BG, 2))
            cx, cy = self.width()/2, self.height()/2
            p.drawLine(QPointF(cx-5, cy), QPointF(cx+5, cy))
            p.drawLine(QPointF(cx+1, cy-4), QPointF(cx+5, cy))
            p.drawLine(QPointF(cx+1, cy+4), QPointF(cx+5, cy))


_SCROLLBAR_CSS = """
QScrollBar:vertical { background: transparent; width: 4px; }
QScrollBar::handle:vertical { background: rgba(0,212,255,0.2); border-radius: 2px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""
