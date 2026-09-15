"""Live STT transcript pane — small PyQt5 window streaming speech events.

Subscribes to ``core.transcript_bus`` so every published event lands
in the panel. Colour-codes by role (final/partial/reply/system).

Designed to live alongside the main AERIS window. Stays open until
explicitly closed; subscribers are removed on close so the bus doesn't
keep accumulating dead refs.

Public API:
    open_transcript_pane()  — show the pane (no-op if already visible)
    hide_transcript_pane()
    is_transcript_visible() -> bool
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)


_PANE_INSTANCE = None    # type: ignore  (QDialog ref)
_LOCK = threading.RLock()


def is_transcript_visible() -> bool:
    with _LOCK:
        if _PANE_INSTANCE is None:
            return False
        try:
            return bool(_PANE_INSTANCE.isVisible())
        except Exception:
            return False


def hide_transcript_pane() -> bool:
    global _PANE_INSTANCE
    with _LOCK:
        if _PANE_INSTANCE is None:
            return False
        try:
            _PANE_INSTANCE.close()
        except Exception:
            pass
        _PANE_INSTANCE = None
        return True


def open_transcript_pane(parent=None) -> bool:
    global _PANE_INSTANCE
    try:
        from PyQt5.QtWidgets import (
            QApplication, QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout,
        )
        from PyQt5.QtCore import Qt, QTimer
        from PyQt5.QtGui import QFont, QTextCursor
    except Exception as e:
        log.info("[transcript_pane] PyQt5 unavailable: %s", e)
        return False

    if QApplication.instance() is None:
        log.info("[transcript_pane] no QApplication — refusing off-main spawn.")
        return False

    with _LOCK:
        if _PANE_INSTANCE is not None and _PANE_INSTANCE.isVisible():
            return True

        dlg = QDialog(parent)
        dlg.setWindowTitle("AERIS — Live Transcript")
        dlg.resize(520, 360)
        root = QVBoxLayout(dlg)

        text_view = QTextEdit()
        text_view.setReadOnly(True)
        text_view.setFont(QFont("Consolas", 10))
        text_view.setStyleSheet(
            "QTextEdit { background-color: #0d1117; color: #e6edf3; "
            "border: 1px solid #30363d; }"
        )
        root.addWidget(text_view)

        # Pending-event queue (worker callbacks fire from background threads;
        # we drain on a Qt timer so the QTextEdit is mutated on the GUI thread).
        pending: list[dict] = []
        pending_lock = threading.Lock()

        def _on_event(evt: dict) -> None:
            with pending_lock:
                pending.append(evt)

        def _drain():
            with pending_lock:
                batch = list(pending)
                pending.clear()
            if not batch:
                return
            cur = text_view.textCursor()
            cur.movePosition(QTextCursor.End)
            for evt in batch:
                role = (evt.get("role") or "final").lower()
                text = (evt.get("text") or "").rstrip()
                when = time.strftime("%H:%M:%S", time.localtime(evt.get("ts") or time.time()))
                color = {
                    "final":   "#ffffff",
                    "partial": "#8b949e",
                    "reply":   "#7ee787",
                    "system":  "#f0b500",
                }.get(role, "#e6edf3")
                line = (f'<span style="color:#586069">[{when}]</span> '
                        f'<span style="color:{color}"><b>{role:7s}</b> {_escape(text)}</span><br>')
                cur.insertHtml(line)
            text_view.setTextCursor(cur)
            text_view.ensureCursorVisible()

        timer = QTimer(dlg)
        timer.timeout.connect(_drain)
        timer.start(200)

        try:
            from core.transcript_bus import get_bus
            bus = get_bus()
            # Backfill with recent history.
            for evt in bus.recent(20):
                with pending_lock:
                    pending.append(evt)
            bus.add_listener(_on_event)
        except Exception as e:
            log.info("[transcript_pane] bus wiring failed: %s", e)

        # Footer buttons.
        btns = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        close_btn = QPushButton("Close")
        btns.addStretch(1)
        btns.addWidget(clear_btn)
        btns.addWidget(close_btn)
        root.addLayout(btns)

        def _clear():
            text_view.clear()
            try:
                from core.transcript_bus import get_bus
                get_bus().clear()
            except Exception:
                pass

        clear_btn.clicked.connect(_clear)
        close_btn.clicked.connect(dlg.accept)

        def _on_close(_e):
            try:
                from core.transcript_bus import get_bus
                get_bus().remove_listener(_on_event)
            except Exception:
                pass
            timer.stop()
            try:
                _e.accept()
            except Exception:
                pass
        dlg.closeEvent = _on_close   # type: ignore

        dlg.show()
        _PANE_INSTANCE = dlg
        log.info("[transcript_pane] shown.")
        return True


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))
