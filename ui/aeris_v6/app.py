"""AerisV6Window — the main frameless application window + worker wiring.

Native PyQt5 equivalent of ``JarvisV5App`` from ``jv5-app.jsx``: a frameless
window with the custom titlebar, the floating dock overlay, a page router
(chat / home / automations / brain / memory / system / settings), the
conversation stage + mission-control chat, the collapsible log bar, and the
⌘K command palette / proactive notifications / minimized orb overlays.

The brain/voice/TTS run on the same worker-thread contract as the old GUI, so
this is the real assistant — not a mock.
"""
from __future__ import annotations

import os
import sys
import time

from PyQt5.QtCore import (
    QPoint, Qt, QThread, QTimer, pyqtSignal,
)
from PyQt5.QtGui import QColor, QKeySequence, QPainter
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QShortcut, QSizeGrip,
    QStackedWidget, QVBoxLayout, QWidget,
)

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ui.aeris_v6.tokens import APP_QSS, J, JSTATES, col, rgba_str
from ui.aeris_v6.titlebar import AppTitleBar
from ui.aeris_v6.dock import FloatingDock
from ui.aeris_v6.stage import ConversationStage
from ui.aeris_v6.chat_panel import MissionControlChatPanel
from ui.aeris_v6.logs_bar import LogsBar
from ui.aeris_v6.workers import BrainWorker, SpeakWorker


class _ChatView(QWidget):
    """Left conversation stage + log bar, with the chat panel docked right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        left = QWidget()
        ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(0)
        self.stage = ConversationStage()
        ll.addWidget(self.stage, 1)
        self.logs = LogsBar()
        ll.addWidget(self.logs)
        root.addWidget(left, 1)
        self.chat = MissionControlChatPanel()
        root.addWidget(self.chat)


class AerisV6Window(QMainWindow):
    request_brain_init = pyqtSignal()
    request_brain_proc = pyqtSignal(str)
    request_speak = pyqtSignal(str)
    # Eternal-presence moments arrive on the engine's heartbeat thread; this
    # signal marshals them onto the GUI thread (queued connection).
    presence_moment = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("A.E.R.I.S — JARVIS v6")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.resize(1320, 840)
        self.setMinimumSize(1040, 680)
        self.setStyleSheet(APP_QSS)

        self._state = "IDLE"
        self._brain_ready = False
        self._stream_text = ""
        self._stream_full = ""
        self._stream_i = 0
        self._active_nav = "chat"

        self._build_ui()
        self._wire_clock()
        self._start_workers()
        self._install_presence()

    # ── UI ─────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet(f"background:{rgba_str('bg', 1.0)};")
        self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.titlebar = AppTitleBar(self)
        self.titlebar.minimizeRequested.connect(self.showMinimized)
        self.titlebar.maximizeRequested.connect(self._toggle_max)
        self.titlebar.closeRequested.connect(self.close)
        self.titlebar.cmdkRequested.connect(self._open_palette)
        root.addWidget(self.titlebar)

        body = QWidget()
        bl = QHBoxLayout(body); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(0)

        # page stack
        self.pages = QStackedWidget()
        self.chat_view = _ChatView()
        self.chat_view.chat.send.connect(self.handle_send)
        self.chat_view.chat.mic.connect(self.handle_mic)
        self.pages.addWidget(self.chat_view)         # index 0 = chat
        self._page_index = {"chat": 0}
        self._install_pages()

        bl.addWidget(self.pages, 1)
        root.addWidget(body, 1)

        # floating dock as an overlay child of the window
        self.dock = FloatingDock(self)
        self.dock.navigate.connect(self.navigate)
        self.dock.set_active("chat")
        self.dock.raise_()

        # resize grip
        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(16, 16)

        # overlays (defensive — built in task 7)
        self.palette = None
        self.notifications = None
        self._install_overlays()

        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._open_palette)
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self.handle_mic)

        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._tick_stream)

    def _install_pages(self):
        """Add the six content pages; fall back to a placeholder per page if
        the pages package isn't present yet."""
        order = ["home", "auto", "brain", "memory", "system", "settings"]
        try:
            from ui.aeris_v6.pages import build_page
        except Exception:
            build_page = None
        for key in order:
            page = None
            if build_page is not None:
                try:
                    page = build_page(key, self)
                except Exception as e:
                    self._log("ERR", f"page {key} failed: {e}")
            if page is None:
                page = self._placeholder(key)
            self._page_index[key] = self.pages.addWidget(page)

    def _placeholder(self, key: str) -> QWidget:
        from PyQt5.QtWidgets import QLabel
        w = QWidget(); w.setStyleSheet(f"background:{rgba_str('bg',1)};")
        lay = QVBoxLayout(w); lay.setAlignment(Qt.AlignCenter)
        lbl = QLabel(f"{key.upper()}\n\n(coming soon)")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color:{rgba_str('textMut',1)};font-size:18px;")
        lay.addWidget(lbl)
        return w

    def _install_overlays(self):
        try:
            from ui.aeris_v6.command_palette import CommandPalette
            self.palette = CommandPalette(self)
            self.palette.command.connect(self._run_command)
        except Exception as e:
            self._log("SYS", f"palette unavailable: {e}")
        try:
            from ui.aeris_v6.notifications import NotificationLayer
            self.notifications = NotificationLayer(self)
        except Exception as e:
            self._log("SYS", f"notifications unavailable: {e}")

    # ── layout upkeep ──────────────────────────────────────────────
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # dock: vertically centered on the left, below the titlebar
        dh = min(self.dock.sizeHint().height(), self.height() - 120)
        self.dock.move(12, 40 + (self.height() - 40 - self.dock.height()) // 2)
        self._grip.move(self.width() - 18, self.height() - 18)
        if self.palette is not None:
            self.palette.setGeometry(0, 0, self.width(), self.height())
        if self.notifications is not None:
            self.notifications.reposition()

    # ── clock ──────────────────────────────────────────────────────
    def _wire_clock(self):
        self._clock = QTimer(self)
        self._clock.timeout.connect(
            lambda: self.titlebar.set_clock(time.strftime("%H:%M:%S")))
        self._clock.start(1000)
        self.titlebar.set_clock(time.strftime("%H:%M:%S"))

    # ── workers ────────────────────────────────────────────────────
    def _start_workers(self):
        self.brain_thread = QThread(self)
        self.brain = BrainWorker()
        self.brain.moveToThread(self.brain_thread)
        self.brain.load_progress.connect(self._on_brain_progress)
        self.brain.ready.connect(self._on_brain_ready)
        self.brain.responded.connect(self._on_brain_responded)
        self.brain.error.connect(lambda m: self._log("ERR", m))
        self.request_brain_init.connect(self.brain.initialize)
        self.request_brain_proc.connect(self.brain.process)
        self.brain_thread.start()

        self.speak_thread = QThread(self)
        self.speaker = SpeakWorker()
        self.speaker.moveToThread(self.speak_thread)
        self.speaker.error.connect(lambda m: self._log("ERR", m))
        self.request_speak.connect(self.speaker.speak)
        self.speak_thread.started.connect(self.speaker.initialize)
        self.speak_thread.start()

        self._log("SYS", "Booting neural core…")
        self.request_brain_init.emit()

    # ── eternal live presence ──────────────────────────────────────
    def _install_presence(self):
        """Wire the always-on ambient-presence engine into the GUI.

        Moments fire on the engine's heartbeat thread, so the listener only
        re-emits them as a queued Qt signal; all GUI work happens in
        ``_on_presence_moment`` on the main thread.
        """
        self._presence = None
        # Queued by default for cross-thread signals → safe to touch widgets.
        self.presence_moment.connect(self._on_presence_moment, Qt.QueuedConnection)
        try:
            from core.eternal_presence import install as _install_presence
            self._presence = _install_presence(
                on_moment=lambda m: self.presence_moment.emit(m))
            self._log("SYS", "Eternal presence online · ambient mode")
        except Exception as e:
            self._log("SYS", f"presence unavailable: {e}")
        # Presence-gated gestures: arm only while the user is here (3a).
        try:
            from core.gesture_gate import install_gesture_gating
            if install_gesture_gating():
                self._log("SYS", "Gesture gate online · presence-armed")
        except Exception as e:
            self._log("SYS", f"gesture gate unavailable: {e}")

        # Poll the fused presence state at a calm cadence for the titlebar pill.
        self._presence_timer = QTimer(self)
        self._presence_timer.timeout.connect(self._refresh_presence_pill)
        self._presence_timer.start(5000)
        self._refresh_presence_pill()

    def _refresh_presence_pill(self):
        if not getattr(self, "_presence", None):
            return
        try:
            ctx = self._presence.context()
            state = ctx.state if ctx else self._presence.state()
            detail = ""
            if ctx and state in ("active", "focus") and ctx.active_for_s >= 60:
                detail = f"{int(ctx.active_for_s // 60)}m"
            self.titlebar.set_presence(state, detail)
            self.chat_view.stage.set_presence_state(state)
        except Exception:
            pass

    def _on_presence_moment(self, moment):
        """Surface a proactive moment: log + toast + (maybe) speak/chat."""
        kind = getattr(moment, "kind", "")
        text = getattr(moment, "text", "")
        prio = getattr(moment, "priority", 1)
        self._log("PRZ", f"{kind}: {text}", prio >= 2)
        if self.notifications is not None:
            try:
                self.notifications.push(
                    "A.E.R.I.S", text,
                    kind=("warn" if prio >= 2 else "info"))
            except Exception:
                pass
        # Greetings / welcome-backs read naturally as a chat line too.
        if kind in ("greeting", "welcome_back"):
            try:
                self.chat_view.chat.add_ai(
                    text, {"intent": f"presence_{kind}", "conf": 100,
                           "act": "proactive", "ms": 0})
            except Exception:
                pass
        # Speak the meaningful ones; farewell (priority 0) stays silent.
        if prio >= 1 and self._brain_ready and text:
            self.request_speak.emit(text)

    def _on_brain_progress(self, log_type, msg, pct):
        self._log(log_type or "SYS", f"{msg}  ({pct}%)")

    def _on_brain_ready(self):
        self._brain_ready = True
        self._log("SYS", "Neural core online · awaiting instructions", True)
        self.chat_view.chat.add_ai(
            "Online, Shivang. Neural core synced — ready when you are.",
            {"intent": "sys_boot", "conf": 99.9, "act": "executed", "ms": 100})
        self._show_daily_digest()

    def _show_daily_digest(self):
        """Once per boot: surface yesterday's presence digest as a chat line."""
        try:
            from datetime import date, timedelta
            from core.presence_journal import get_journal
            line = get_journal().digest_line(date.today() - timedelta(days=1))
            if line:
                self.chat_view.chat.add_ai(
                    line, {"intent": "presence_digest", "conf": 100,
                           "act": "proactive", "ms": 0})
                self._log("PRZ", "daily digest surfaced")
        except Exception:
            pass

    def _on_brain_responded(self, reply: str, meta: dict):
        self.chat_view.chat.clear_thinking()
        self.set_state("SPEAKING")
        self._log("NLU", f"Intent: {meta.get('intent')} · "
                  f"{meta.get('confidence', 0):.0f}% · {meta.get('action')}", True)
        self._stream_card = self.chat_view.chat.begin_stream(meta)
        self._stream_full = reply
        self._stream_i = 0
        self._stream_timer.start(16)
        if reply:
            self.request_speak.emit(reply)

    def _tick_stream(self):
        self._stream_i += 1
        self.chat_view.chat.update_stream(self._stream_full[:self._stream_i])
        if self._stream_i >= len(self._stream_full):
            self._stream_timer.stop()
            self.chat_view.chat.end_stream(self._stream_full)
            self.set_state("IDLE")
            self._log("ACT", "Response delivered · system nominal")

    # ── interaction ────────────────────────────────────────────────
    def handle_send(self, text: str):
        text = (text or "").strip()
        if not text:
            return
        if self._active_nav != "chat":
            self.navigate("chat")
        self.chat_view.chat.add_user(text)
        self._log("NLU", f'Input: "{text[:48]}{"…" if len(text) > 48 else ""}"', True)
        if not self._brain_ready:
            self.chat_view.chat.add_ai(
                "Neural core abhi boot ho raha hai — ek second…",
                {"intent": "sys", "conf": 0, "act": "slot_filling", "ms": 0})
            return
        self.set_state("PROCESSING")
        self.chat_view.chat.show_thinking()
        self.request_brain_proc.emit(text)

    def handle_mic(self):
        # Voice is optional; flip a visual listening state. Real STT can be
        # wired via VoiceWorker the same way the brain is.
        if self._state == "LISTENING":
            self.set_state("IDLE")
            self._log("MIC", "Voice capture stopped")
        else:
            self.set_state("LISTENING")
            self._log("MIC", "Voice capture armed (press Ctrl+M to stop)", True)

    def navigate(self, key: str):
        self._active_nav = key
        self.dock.set_active(key)
        self.pages.setCurrentIndex(self._page_index.get(key, 0))

    def set_state(self, state: str):
        self._state = state
        self.titlebar.set_state(state)
        self.chat_view.stage.set_state(state)
        busy = state in ("PROCESSING", "SPEAKING")
        self.chat_view.chat.set_busy(busy, listening=(state == "LISTENING"))

    # ── overlays ───────────────────────────────────────────────────
    def _open_palette(self):
        if self.palette is not None:
            self.palette.setGeometry(0, 0, self.width(), self.height())
            self.palette.open()

    def _run_command(self, action: dict):
        if not action:
            return
        kind = action.get("type")
        if kind == "nav":
            self.navigate(action.get("to", "chat"))
        elif kind == "ask":
            self.navigate("chat"); self.handle_send(action.get("text", ""))
        elif kind == "mic":
            self.handle_mic()

    # ── misc ───────────────────────────────────────────────────────
    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _log(self, typ: str, text: str, highlight: bool = False):
        try:
            self.chat_view.logs.add_log(typ, text, highlight)
        except Exception:
            pass

    def closeEvent(self, ev):
        if getattr(self, "_presence", None):
            try:
                self._presence.stop()
            except Exception:
                pass
        for th in (getattr(self, "brain_thread", None), getattr(self, "speak_thread", None)):
            if th is not None:
                th.quit(); th.wait(1500)
        super().closeEvent(ev)


def launch(splash=None):
    app = QApplication.instance() or QApplication(sys.argv)
    win = AerisV6Window()
    win.show()
    if splash is not None:
        try:
            splash.finish(win)
        except Exception:
            try:
                splash.close()
            except Exception:
                pass
    return app.exec_()


if __name__ == "__main__":
    sys.exit(launch())
