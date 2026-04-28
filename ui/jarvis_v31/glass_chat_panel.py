"""JARVIS v3.1 glass chat panel — 390px right rail.

Mirrors jv3-chat.jsx::GlassChatPanel. Differences vs the older aeris chat:
  - 390px (was 380), translucent panel with subtle inner edge highlight
  - Header has busy pill THINKING (magenta) or GENERATING (purple) +
    permanent LIVE (red) — both with blinking dots
  - Row of 5 suggestion chips below header — click sends as a message
  - Asymmetric bubble corners (4px on the sender side)
  - User bubble uses cyan→purple gradient tint
  - Send button is a cyan→purple gradient circle
"""
from __future__ import annotations

import math
import random
import time
from typing import Optional

from PyQt5.QtCore import (
    QPointF, QRectF, QTimer, Qt, pyqtSignal
)
from PyQt5.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPen, QPainterPath
)
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget
)

from .tokens import J, JSTATES, inter, mono, rgba


SUGGESTION_CHIPS = [
    "Open Chrome", "Check Weather", "Play Music", "System Stats", "Schedule Meeting",
]


class GlassChatPanel(QWidget):
    """Public surface:

    Signals:
        send_text(str)    — user typed (or chip clicked) and pressed Enter
        mic_clicked()     — user pressed the mic button

    Methods:
        add_message(role, text, tag=None)
        stream_message(text, tag=None, speed_ms=18)
        set_state(key)
    """

    send_text     = pyqtSignal(str)
    mic_clicked   = pyqtSignal()
    automation_chip_used = pyqtSignal()   # fired when a chip is picked, so
                                          # the dock can revert to 'chat' tab

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(390)
        self._state = "IDLE"
        self._messages: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────
        header = _Header()
        self._header = header
        root.addWidget(header)

        # ── Automation panel (suggestion chips, hidden by default) ──
        # Only shown when the dock's Automation tab is active. Uses a
        # 2-column grid so chips wrap cleanly inside the 390px panel
        # instead of overflowing horizontally as they did before.
        self._automation = _AutomationPanel(SUGGESTION_CHIPS)
        self._automation.chip_picked.connect(self._on_chip_picked)
        self._automation.setVisible(False)
        root.addWidget(self._automation)

        # ── Messages scroll area ────────────────────────────────────
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
        self._msg_w = QWidget()
        self._msg_w.setStyleSheet("background: transparent;")
        self._msg_lay = QVBoxLayout(self._msg_w)
        self._msg_lay.setContentsMargins(16, 14, 16, 14)
        self._msg_lay.setSpacing(14)
        # Typing dots + stretch live at the bottom of the message column.
        self._typing_dots = _TypingDots()
        self._typing_dots.setVisible(False)
        self._msg_lay.addWidget(self._typing_dots)
        self._msg_lay.addStretch(1)
        self._scroll.setWidget(self._msg_w)
        root.addWidget(self._scroll, stretch=1)

        # ── Input bar ───────────────────────────────────────────────
        self._input_bar = _ChatInput()
        self._input_bar.send.connect(self._on_send)
        self._input_bar.mic.connect(self.mic_clicked.emit)
        root.addWidget(self._input_bar)

        # ── Streaming bookkeeping ───────────────────────────────────
        self._stream_bubble: Optional[_MessageBubble] = None
        self._stream_timer: Optional[QTimer] = None
        self._stream_full = ""
        self._stream_idx  = 0

    # ── Public API ──────────────────────────────────────────────────
    def add_message(self, role: str, text: str,
                    tag: Optional[tuple[str, QColor]] = None) -> None:
        self._messages.append({
            "role": role, "text": text, "tag": tag,
            "time": time.strftime("%H:%M"),
        })
        bubble = _MessageBubble(role, text, tag, self._messages[-1]["time"])
        # Insert before typing-dots + stretch
        self._msg_lay.insertWidget(self._msg_lay.count() - 2, bubble)
        self._header.set_count(len(self._messages))
        QTimer.singleShot(40, self._scroll_to_bottom)

    def stream_message(self, text: str,
                       tag: Optional[tuple[str, QColor]] = None,
                       speed_ms: int = 18) -> None:
        """Append an AERIS bubble whose text appears character-by-character."""
        self._cancel_stream()
        self._typing_dots.setVisible(False)
        self._stream_full = text
        self._stream_idx = 0

        bubble = _MessageBubble("ai", "", tag, time.strftime("%H:%M"),
                                streaming=True)
        self._msg_lay.insertWidget(self._msg_lay.count() - 2, bubble)
        self._stream_bubble = bubble

        self._messages.append({
            "role": "ai", "text": text, "tag": tag,
            "time": time.strftime("%H:%M"),
        })
        self._header.set_count(len(self._messages))

        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._stream_tick)
        self._stream_timer.start(speed_ms)
        QTimer.singleShot(40, self._scroll_to_bottom)

    def set_state(self, key: str) -> None:
        if key not in JSTATES:
            return
        self._state = key
        self._header.set_state(key)
        self._input_bar.set_state(key)
        # Typing dots only while PROCESSING and no bubble streaming yet.
        self._typing_dots.setVisible(
            key == "PROCESSING" and self._stream_bubble is None
        )
        if self._typing_dots.isVisible():
            QTimer.singleShot(40, self._scroll_to_bottom)

    def set_automation_visible(self, on: bool) -> None:
        """Show/hide the suggestion-chip grid (driven by the dock's nav tab)."""
        self._automation.setVisible(on)

    def set_voice_state(self, state: str) -> None:
        """Voice engine state (STOPPED / ACTIVE / SLEEPING) → chat input bar."""
        self._input_bar.set_voice_state(state)

    def _on_chip_picked(self, label: str) -> None:
        """A suggestion chip was clicked — send it as a message and signal
        the parent so the dock can flip back to the 'chat' tab."""
        self.send_text.emit(label)
        self.automation_chip_used.emit()

    # ── Internals ───────────────────────────────────────────────────
    def _on_send(self, text: str) -> None:
        self.send_text.emit(text)

    def _scroll_to_bottom(self) -> None:
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _stream_tick(self) -> None:
        if self._stream_bubble is None:
            self._cancel_stream(); return
        self._stream_idx += 1
        self._stream_bubble.set_text(self._stream_full[: self._stream_idx])
        if self._stream_idx >= len(self._stream_full):
            self._stream_bubble.set_streaming(False)
            self._cancel_stream()

    def _cancel_stream(self) -> None:
        if self._stream_timer is not None:
            self._stream_timer.stop()
            self._stream_timer = None
        self._stream_bubble = None

    # ── Painting (translucent glass + left edge highlight) ──────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        bg = QColor(J.PANEL); bg.setAlphaF(0.75)
        p.fillRect(self.rect(), bg)
        # Left border + thin cyan inner edge highlight
        p.setPen(QPen(rgba(J.BORDER, 0.6), 1))
        p.drawLine(0, 0, 0, self.height())
        p.setPen(QPen(rgba(J.CYAN, 0.06), 1))
        p.drawLine(1, 0, 1, self.height())


# ─── Header ──────────────────────────────────────────────────────── #

class _Header(QFrame):
    """56px header with title + busy pill + LIVE pill."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setStyleSheet("background: transparent;")
        self._state = "IDLE"
        self._count = 0

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 16, 0)
        lay.setSpacing(8)

        left = QVBoxLayout(); left.setSpacing(2)
        self._title = QLabel("CONVERSATION")
        self._title.setFont(inter(11, 700))
        self._title.setStyleSheet(f"color: {J.TEXT_PRI.name()}; letter-spacing: 2px;")
        self._sub = QLabel("Session · 0 messages")
        self._sub.setFont(mono(10, 400))
        self._sub.setStyleSheet(f"color: {J.TEXT_MUT.name()};")
        left.addWidget(self._title); left.addWidget(self._sub)
        lay.addLayout(left); lay.addStretch(1)

        self._busy_pill = _Pill("THINKING", J.MAGENTA, blink=True)
        self._busy_pill.setVisible(False)
        lay.addWidget(self._busy_pill)

        self._live_pill = _Pill("LIVE", J.RED, blink=True)
        lay.addWidget(self._live_pill)

    def set_state(self, key: str) -> None:
        if key == "PROCESSING":
            self._busy_pill.set_data("THINKING", J.MAGENTA)
            self._busy_pill.setVisible(True)
        elif key == "SPEAKING":
            self._busy_pill.set_data("GENERATING", J.PURPLE)
            self._busy_pill.setVisible(True)
        else:
            self._busy_pill.setVisible(False)
        self._state = key

    def set_count(self, n: int) -> None:
        self._count = n
        self._sub.setText(f"Session · {n} messages")

    def paintEvent(self, _):
        p = QPainter(self)
        bg = QColor(J.BG); bg.setAlphaF(0.4)
        p.fillRect(self.rect(), bg)
        p.setPen(QPen(rgba(J.BORDER, 0.7), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


# ─── Pill (THINKING / GENERATING / LIVE) ──────────────────────────── #

class _Pill(QWidget):
    def __init__(self, text: str, color: QColor, blink: bool = True, parent=None):
        super().__init__(parent)
        self._text = text
        self._color = color
        self._blink = blink
        self._start = time.monotonic()
        self.setFixedHeight(20)
        if blink:
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
        # blink dot
        if self._blink:
            ph = (time.monotonic() - self._start) * 2 * math.pi / 1.2
            alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(ph))
        else:
            alpha = 1.0
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(self._color, alpha * 0.5))
        p.drawEllipse(QPointF(8, self.height() / 2), 4, 4)
        p.setBrush(rgba(self._color, alpha))
        p.drawEllipse(QPointF(8, self.height() / 2), 2.5, 2.5)
        # label
        p.setPen(self._color)
        p.setFont(mono(9, 700))
        text_rect = QRectF(15, 0, self.width() - 18, self.height())
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self._text)
        # Auto-fit
        fm = p.fontMetrics()
        w = 18 + fm.horizontalAdvance(self._text) + 10
        if w != self.width():
            self.setFixedWidth(w)


# ─── Automation panel (suggestion-chip grid) ─────────────────────── #

class _AutomationPanel(QWidget):
    """Grid of suggestion chips shown only when the Automation tab is active.

    Uses a 2-column QGridLayout so 5 chips wrap as 3 rows (2 + 2 + 1)
    instead of overflowing horizontally as the old single-row HBox did.
    A small header label clarifies what the panel is for.
    """

    chip_picked = pyqtSignal(str)

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 4)
        root.setSpacing(8)

        # Section heading
        title = QLabel("AUTOMATION · QUICK COMMANDS")
        title.setFont(mono(9, 700))
        title.setStyleSheet(f"color: {J.TEXT_MUT.name()}; letter-spacing: 1.5px;")
        root.addWidget(title)

        # Chip grid (2 columns, wraps automatically)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, label in enumerate(labels):
            chip = _SuggestionChip(label)
            chip.clicked_label.connect(self.chip_picked.emit)
            row, col = divmod(i, 2)
            grid.addWidget(chip, row, col, alignment=Qt.AlignLeft)
        # Make both columns share width evenly so chips align nicely.
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        root.addLayout(grid)

    def paintEvent(self, _):
        # Subtle bottom separator so the panel feels distinct from messages.
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Faint background tint
        bg = QColor(J.CYAN); bg.setAlphaF(0.03)
        p.fillRect(self.rect(), bg)
        # Border line at the bottom edge
        p.setPen(QPen(rgba(J.BORDER, 0.6), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


# ─── Suggestion chip ─────────────────────────────────────────────── #

class _SuggestionChip(QPushButton):
    """Rounded pill — clicking sends its label as a chat message.

    Width grows to fill its grid cell (no fixed width) so chips line up
    cleanly in the AutomationPanel's 2-column layout.
    """

    clicked_label = pyqtSignal(str)

    def __init__(self, label: str, parent=None):
        super().__init__(label, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        self.setFlat(True)
        self.setStyleSheet("border: none;")
        self.setFont(mono(11, 400))
        self._hov = False
        # Minimum width = text + padding so the chip never collapses below
        # its content; the grid will stretch beyond this when there's room.
        from PyQt5.QtGui import QFontMetrics
        fm = QFontMetrics(self.font())
        self.setMinimumWidth(fm.horizontalAdvance(label) + 24)
        self.clicked.connect(lambda: self.clicked_label.emit(self.text()))

    def enterEvent(self, _): self._hov = True; self.update()
    def leaveEvent(self, _): self._hov = False; self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        if self._hov:
            p.setPen(QPen(rgba(J.CYAN, 0.4), 1))
            p.setBrush(rgba(J.CYAN, 0.14))
            text_col = J.TEXT_PRI
        else:
            p.setPen(QPen(rgba(J.CYAN, 0.20), 1))
            p.setBrush(rgba(J.CYAN, 0.07))
            text_col = J.TEXT_SEC
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        p.setPen(text_col); p.setFont(self.font())
        p.drawText(rect, Qt.AlignCenter, self.text())


# ─── Message bubble ──────────────────────────────────────────────── #

class _MessageBubble(QWidget):
    """Sender row + asymmetric-corner bubble + (when present) tag pill."""

    def __init__(self, role: str, text: str,
                 tag: Optional[tuple[str, QColor]],
                 time_label: str, streaming: bool = False, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._role = role
        is_ai = role == "ai"

        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(5)

        # Sender row
        sender = QWidget()
        s_lay = QHBoxLayout(sender)
        s_lay.setContentsMargins(0, 0, 0, 0); s_lay.setSpacing(6)
        if is_ai:
            self._sender_dot = _SmallDot(J.CYAN, blink=streaming)
            s_lay.addWidget(self._sender_dot)
        else:
            self._sender_dot = None
        name = QLabel("A.E.R.I.S" if is_ai else "YOU")
        name.setFont(mono(9, 700))
        name.setStyleSheet(
            f"color: {J.CYAN.name() if is_ai else J.TEXT_SEC.name()};"
            f"letter-spacing: 1px;"
        )
        s_lay.addWidget(name)
        t_lbl = QLabel(time_label); t_lbl.setFont(mono(8, 400))
        t_lbl.setStyleSheet(f"color: {J.TEXT_MUT.name()};")
        s_lay.addWidget(t_lbl)
        s_lay.addStretch(1)
        if not is_ai:
            s_lay.setDirection(QHBoxLayout.RightToLeft)
        v.addWidget(sender)

        # Bubble
        self._body = _BubbleBody(is_ai, text, streaming=streaming)
        bubble_row = QHBoxLayout()
        bubble_row.setContentsMargins(0, 0, 0, 0)
        if is_ai:
            bubble_row.addWidget(self._body); bubble_row.addStretch(1)
        else:
            bubble_row.addStretch(1); bubble_row.addWidget(self._body)
        v.addLayout(bubble_row)

        # Tag pill (only if tag and not streaming)
        if tag and not streaming:
            self._add_tag(v, is_ai, tag)

    def _add_tag(self, v, is_ai, tag):
        tag_text, tag_color = tag
        pill = _Pill(tag_text, tag_color, blink=False)
        row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0)
        if is_ai:
            row.addWidget(pill); row.addStretch(1)
        else:
            row.addStretch(1); row.addWidget(pill)
        v.addLayout(row)

    # Streaming hooks (used by GlassChatPanel.stream_message)
    def set_text(self, text: str) -> None:
        self._body.set_text(text)

    def set_streaming(self, on: bool) -> None:
        self._body.set_streaming(on)
        if self._sender_dot is not None:
            self._sender_dot.set_blink(on)


class _BubbleBody(QWidget):
    """Bubble background (asymmetric corners) + text label inside."""

    def __init__(self, is_ai: bool, text: str, streaming: bool = False, parent=None):
        super().__init__(parent)
        self._is_ai = is_ai
        self._streaming = streaming
        self._text = text
        self._cursor_on = True   # must be set before _render() is called

        self._label = QLabel(self._render())
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setFont(mono(12, 400))
        self._label.setStyleSheet(f"color: {J.TEXT_PRI.name()}; line-height: 1.7;")
        self._label.setMaximumWidth(305)
        lay = QVBoxLayout(self); lay.setContentsMargins(14, 10, 14, 10)
        lay.addWidget(self._label)
        self.setMaximumWidth(335)

        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        if streaming:
            self._cursor_timer.start(280)

    def set_text(self, text: str) -> None:
        self._text = text
        self._label.setText(self._render())

    def set_streaming(self, on: bool) -> None:
        self._streaming = on
        if on:
            if not self._cursor_timer.isActive():
                self._cursor_timer.start(280)
        else:
            self._cursor_timer.stop()
        self._label.setText(self._render())

    def _blink_cursor(self):
        self._cursor_on = not self._cursor_on
        self._label.setText(self._render())

    def _render(self) -> str:
        body = (self._text or "").replace("&", "&amp;") \
                                  .replace("<", "&lt;") \
                                  .replace("\n", "<br>")
        if self._streaming:
            cursor = "▌" if self._cursor_on else "&nbsp;"
            return f'{body}<span style="color:{J.CYAN.name()}">{cursor}</span>'
        return body

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Asymmetric corner radii: jsx uses '4px 14px 14px 14px' for AI and
        # '14px 4px 14px 14px' for user. We emulate via QPainterPath.
        rect = QRectF(0, 0, self.width() - 1, self.height() - 1)
        path = _asymmetric_round_rect(
            rect,
            tl=(4 if self._is_ai else 14),
            tr=(14 if self._is_ai else 4),
            br=14, bl=14,
        )
        if self._is_ai:
            p.setPen(QPen(rgba(J.BORDER, 0.8), 1))
            bg = QColor(J.PANEL); bg.setAlphaF(0.85)
            p.setBrush(bg)
        else:
            p.setPen(QPen(rgba(J.CYAN, 0.25), 1))
            grad = QLinearGradient(0, 0, self.width(), self.height())
            grad.setColorAt(0.0, rgba(J.CYAN, 0.10))
            grad.setColorAt(1.0, rgba(J.PURPLE, 0.06))
            p.setBrush(QBrush(grad))
        p.drawPath(path)


def _asymmetric_round_rect(rect: QRectF, tl, tr, br, bl) -> QPainterPath:
    """Build a rounded-rect path with per-corner radii."""
    path = QPainterPath()
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    path.moveTo(x + tl, y)
    path.lineTo(x + w - tr, y)
    path.quadTo(x + w, y, x + w, y + tr)
    path.lineTo(x + w, y + h - br)
    path.quadTo(x + w, y + h, x + w - br, y + h)
    path.lineTo(x + bl, y + h)
    path.quadTo(x, y + h, x, y + h - bl)
    path.lineTo(x, y + tl)
    path.quadTo(x, y, x + tl, y)
    return path


class _SmallDot(QWidget):
    def __init__(self, color: QColor, blink: bool = False, parent=None):
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
            self._timer.stop(); self.update()

    def paintEvent(self, _):
        if self._blink:
            ph = (time.monotonic() - self._start) * 2 * math.pi / 0.7
            alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(ph))
        else:
            alpha = 1.0
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(self._color, alpha * 0.5))
        p.drawEllipse(self.rect())
        p.setBrush(rgba(self._color, alpha))
        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))


# ─── Typing dots (PROCESSING indicator) ──────────────────────────── #

class _TypingDots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(5)
        # sender row
        row = QHBoxLayout(); row.setSpacing(6)
        row.addWidget(_SmallDot(J.CYAN, blink=True))
        name = QLabel("A.E.R.I.S")
        name.setFont(mono(9, 700))
        name.setStyleSheet(f"color: {J.CYAN.name()}; letter-spacing: 1px;")
        row.addWidget(name); row.addStretch(1)
        v.addLayout(row)
        # bubble
        bubble_row = QHBoxLayout(); bubble_row.setContentsMargins(0, 0, 0, 0)
        bubble_row.addWidget(_DotsBubble()); bubble_row.addStretch(1)
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
        # asymmetric bubble
        rect = QRectF(0, 0, self.width() - 1, self.height() - 1)
        path = _asymmetric_round_rect(rect, tl=4, tr=14, br=14, bl=14)
        p.setPen(QPen(rgba(J.BORDER, 0.8), 1))
        bg = QColor(J.PANEL); bg.setAlphaF(0.85)
        p.setBrush(bg)
        p.drawPath(path)
        # 3 dots, staggered
        cy = self.height() / 2
        for i in range(3):
            cx = 18 + i * 14
            ph = (time.monotonic() - self._start - i * 0.3) * 2 * math.pi / 0.9
            alpha = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(ph))
            p.setPen(Qt.NoPen)
            p.setBrush(rgba(J.CYAN, alpha * 0.5))
            p.drawEllipse(QPointF(cx, cy), 5, 5)
            p.setBrush(rgba(J.CYAN, alpha))
            p.drawEllipse(QPointF(cx, cy), 3, 3)


# ─── Listening waveform ──────────────────────────────────────────── #

class _ListeningWave(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self._start = time.monotonic()
        self._bars = [
            (random.uniform(0.4, 0.9),
             random.uniform(0, 2 * math.pi),
             random.uniform(6, 18))
            for _ in range(20)
        ]
        t = QTimer(self); t.timeout.connect(self.update); t.start(60)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(rgba(J.GREEN, 0.25), 1))
        p.setBrush(rgba(J.GREEN, 0.07))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)
        p.setPen(J.GREEN)
        p.setFont(mono(9, 700))
        p.drawText(QRectF(16, 0, 80, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, "LISTENING")
        t = time.monotonic() - self._start
        x0 = 100; bar_w = 3; gap = 5
        cy = self.height() / 2
        p.setPen(Qt.NoPen)
        col = QColor(J.GREEN); col.setAlphaF(0.85)
        for i, (speed, phase, max_h) in enumerate(self._bars):
            local = math.sin(t * (2 + speed * 4) + phase)
            h = 5 + (max_h - 5) * (0.5 + 0.5 * local)
            x = x0 + i * (bar_w + gap)
            if x + bar_w > self.width() - 12:
                break
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x, cy - h / 2, bar_w, h), 1.5, 1.5)


# ─── Sleep mode pill ─────────────────────────────────────────────── #

class _SleepPill(QWidget):
    """Animated banner shown inside the input area when voice is sleeping."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self._start = time.monotonic()
        t = QTimer(self); t.timeout.connect(self.update); t.start(60)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        p.setPen(QPen(rgba(J.PURPLE, 0.40), 1))
        p.setBrush(rgba(J.PURPLE, 0.10))
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 11, 11)
        # Slow-blink dot
        ph = (time.monotonic() - self._start) * 2 * math.pi / 2.5
        alpha = 0.35 + 0.35 * (0.5 + 0.5 * math.sin(ph))
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(J.PURPLE, alpha * 0.5))
        p.drawEllipse(QPointF(11, self.height() / 2), 4, 4)
        p.setBrush(rgba(J.PURPLE, alpha))
        p.drawEllipse(QPointF(11, self.height() / 2), 2.5, 2.5)
        p.setPen(rgba(J.PURPLE, 0.90))
        p.setFont(mono(9, 700))
        p.drawText(QRectF(20, 0, self.width() - 24, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft,
                   "SLEEP MODE · mic on · say 'wake up' to resume")


# ─── Chat input bar ──────────────────────────────────────────────── #

class _ChatInput(QWidget):
    """Glass input bar with continuous-voice support.

    Voice state (STOPPED / ACTIVE / SLEEPING) is independent from the system
    state (IDLE / PROCESSING / SPEAKING). The text field stays editable while
    voice is active so the user can type AND speak freely.
    """

    send = pyqtSignal(str)
    mic  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(86)
        self._sys_state   = "IDLE"
        self._voice_state = "STOPPED"

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(6)

        # Sleep mode banner (shown when voice is SLEEPING)
        self._sleep_pill = _SleepPill()
        self._sleep_pill.setVisible(False)
        root.addWidget(self._sleep_pill)

        # Listening waveform (shown when voice is ACTIVE)
        self._wave = _ListeningWave()
        self._wave.setVisible(False)
        root.addWidget(self._wave)

        # Input row
        self._input_row = _InputRow()
        self._field = self._input_row.field
        self._field.returnPressed.connect(self._emit_send)
        self._input_row.mic_clicked.connect(self.mic.emit)
        self._input_row.send_clicked.connect(self._emit_send)
        root.addWidget(self._input_row)

        # Hints row
        hints = QHBoxLayout(); hints.setSpacing(14); hints.setContentsMargins(4, 0, 0, 0)
        for h in ("↵ send", "⌥ mic", "Hinglish OK"):
            lbl = QLabel(h); lbl.setFont(mono(9, 400))
            lbl.setStyleSheet(f"color: {J.TEXT_MUT.name()};")
            hints.addWidget(lbl)
        hints.addStretch(1)
        root.addLayout(hints)

    def set_state(self, key: str) -> None:
        """System processing state — controls placeholder and field lock."""
        self._sys_state = key
        self._input_row.set_sys_state(key)
        placeholder = {
            "LISTENING":  "Listening…",
            "PROCESSING": "A.E.R.I.S thinking…",
            "SPEAKING":   "A.E.R.I.S responding…",
        }.get(key, "Ask anything…")
        self._field.setPlaceholderText(placeholder)
        # Lock typing only while brain is processing/responding — not during voice
        self._field.setDisabled(key in ("PROCESSING", "SPEAKING"))
        # Wave for legacy one-shot mode (voice_state == STOPPED but LISTENING state)
        if self._voice_state == "STOPPED":
            self._wave.setVisible(key == "LISTENING")

    def set_voice_state(self, state: str) -> None:
        """Voice engine state: STOPPED / ACTIVE / SLEEPING."""
        self._voice_state = state
        self._input_row.set_voice_state(state)
        self._wave.setVisible(state == "ACTIVE")
        self._sleep_pill.setVisible(state == "SLEEPING")

    def _emit_send(self):
        t = self._field.text().strip()
        if not t:
            return
        self._field.clear()
        self.send.emit(t)


class _InputRow(QWidget):
    mic_clicked  = pyqtSignal()
    send_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self._sys_state = "IDLE"

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 5, 5, 5); lay.setSpacing(8)

        self.field = QLineEdit()
        self.field.setPlaceholderText("Ask anything…")
        self.field.setFont(mono(13, 400))
        self.field.setStyleSheet(
            f"QLineEdit {{ background: transparent; border: none; "
            f"color: {J.TEXT_PRI.name()}; }}"
            f"QLineEdit::placeholder {{ color: {J.TEXT_MUT.name()}; }}"
        )
        lay.addWidget(self.field, 1)

        self._mic = _RoundIconButton("mic")
        self._mic.clicked.connect(self.mic_clicked.emit)
        lay.addWidget(self._mic)

        self._send = _RoundIconButton("send")
        self._send.clicked.connect(self.send_clicked.emit)
        lay.addWidget(self._send)

    def set_sys_state(self, key: str) -> None:
        """System state — only affects the input-row border color."""
        self._sys_state = key
        self.update()

    def set_voice_state(self, state: str) -> None:
        """Voice engine state — forwarded directly to the mic button."""
        self._mic.set_voice_state(state)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width() - 1, self.height() - 1)
        busy = self._sys_state in ("PROCESSING", "SPEAKING")
        p.setPen(QPen(rgba(J.CYAN, 0.12 if busy else 0.38), 1))
        bg = QColor(J.BG); bg.setAlphaF(0.9)
        p.setBrush(bg)
        p.drawRoundedRect(rect, 16, 16)


class _RoundIconButton(QPushButton):
    """Mic or send button.

    The mic button has three visual modes driven by the continuous voice engine:
      STOPPED  — normal mic icon (cyan)
      ACTIVE   — "END" label (red)   — click to stop voice entirely
      SLEEPING — "END" label (purple, dimmed) — click to stop voice entirely
    """

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self._kind        = kind
        self._voice_state = "STOPPED"   # relevant only for kind == "mic"
        self.setFixedSize(36, 36)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("border: none;")

    def set_voice_state(self, state: str) -> None:
        self._voice_state = state
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)

        if self._kind == "mic":
            vs = self._voice_state
            cx, cy = self.width() / 2, self.height() / 2

            if vs == "ACTIVE":
                # Red "END" — voice is listening, click stops it
                p.setPen(QPen(rgba(J.RED, 0.70), 1))
                p.setBrush(rgba(J.RED, 0.18))
                p.drawEllipse(rect)
                p.setPen(J.RED)
                p.setFont(inter(8, 800))
                p.drawText(QRectF(0, 0, self.width(), self.height()),
                           Qt.AlignCenter, "END")

            elif vs == "SLEEPING":
                # Purple "END" — voice sleeping, click still stops it
                p.setPen(QPen(rgba(J.PURPLE, 0.55), 1))
                p.setBrush(rgba(J.PURPLE, 0.15))
                p.drawEllipse(rect)
                p.setPen(rgba(J.PURPLE, 0.85))
                p.setFont(inter(8, 800))
                p.drawText(QRectF(0, 0, self.width(), self.height()),
                           Qt.AlignCenter, "END")

            else:
                # Normal mic icon (STOPPED)
                p.setPen(QPen(rgba(J.CYAN, 0.45), 1))
                p.setBrush(rgba(J.CYAN, 0.12))
                p.drawEllipse(rect)
                p.setBrush(J.CYAN); p.setPen(Qt.NoPen)
                p.drawRoundedRect(QRectF(cx - 3, cy - 9, 6, 12), 3, 3)
                pen = QPen(J.CYAN, 1.5); pen.setCapStyle(Qt.RoundCap)
                p.setPen(pen); p.setBrush(Qt.NoBrush)
                p.drawArc(QRectF(cx - 7, cy - 6, 14, 16), 200 * 16, 140 * 16)
                p.drawLine(QPointF(cx, cy + 7), QPointF(cx, cy + 10))
                p.drawLine(QPointF(cx - 4, cy + 10), QPointF(cx + 4, cy + 10))

        else:  # send: cyan→purple gradient circle with arrow
            grad = QLinearGradient(0, 0, self.width(), self.height())
            grad.setColorAt(0.0, J.CYAN)
            grad.setColorAt(1.0, J.PURPLE)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawEllipse(rect)
            cx, cy = self.width() / 2, self.height() / 2
            pen = QPen(J.BG, 2); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
            p.drawLine(QPointF(cx + 1, cy - 4), QPointF(cx + 5, cy))
            p.drawLine(QPointF(cx + 1, cy + 4), QPointF(cx + 5, cy))
