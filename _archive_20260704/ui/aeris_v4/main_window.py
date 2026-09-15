"""AERIS v4 main window — composed root.

Lays out the four major surfaces (title bar / sidebar / center column with
reactor+state+logs / chat panel) and wires user actions to JarvisMainEngine.

Threading model:
  - The engine load (~120 MB encoder) and every process_text() call run on
    a `BrainWorker` living on its own QThread. The UI thread only receives
    Qt signals, so it never blocks on inference.
  - State transitions (IDLE → PROCESSING → SPEAKING → IDLE) are driven by
    signals from the worker, not from the UI side, so the reactor / chat
    panel / title pill always reflect the actual brain status.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

from PyQt5.QtCore import (
    QObject, QPoint, QPointF, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
)
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget
)

# Add project root to path so this file can be launched directly.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ui.aeris_v4.arc_reactor import ArcReactor, ReactorStateText
from ui.aeris_v4.chat_panel import ChatPanel
from ui.aeris_v4.logs_panel import SystemLogsPanel
from ui.aeris_v4.sidebar import Sidebar
from ui.aeris_v4.theme import C
from ui.aeris_v4.title_bar import TitleBar


# ─── Background brain worker ─────────────────────────────────────────── #

class BrainWorker(QObject):
    """Runs JarvisMainEngine on a worker thread.

    Signals:
        ready                       — engine finished loading
        responded(text, meta_dict)  — process_text returned (meta has intent/conf)
        load_progress(msg)          — log strings during init for the SystemLogsPanel
    """

    ready          = pyqtSignal()
    responded      = pyqtSignal(str, dict)
    load_progress  = pyqtSignal(str, str)   # (log_type, text)
    error          = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._engine = None  # type: Optional[object]

    @pyqtSlot()
    def initialize(self):
        try:
            self.load_progress.emit("SYS", "Loading JarvisMainEngine…")
            from core.main_engine import JarvisMainEngine
            self._engine = JarvisMainEngine(stt="SKIP", tts="SKIP", verbose=False)
            self.load_progress.emit("NLU", "Brain online. Encoder + k-NN ready.")
            self.load_progress.emit("MEM", "Memory + feedback DB attached.")
            self.load_progress.emit("SYS", "All modules nominal. Awaiting input.")
            self.ready.emit()
        except Exception as e:
            self.error.emit(str(e))

    @pyqtSlot(str)
    def process(self, text: str):
        if self._engine is None:
            self.error.emit("Brain not ready yet.")
            return
        t0 = time.monotonic()
        try:
            reply = self._engine.process_text(text)
        except Exception as e:
            self.error.emit(f"process_text crashed: {e}")
            return
        latency_ms = int((time.monotonic() - t0) * 1000)
        # Try to pull intent + confidence off the engine for the chat tag.
        meta = {"intent": "general", "confidence": 0.0,
                "latency_ms": latency_ms, "action": "executed"}
        try:
            # JarvisMainEngine doesn't currently expose last_pred — use the
            # feedback log's tail row for the freshest intent/confidence.
            cur = self._engine.feedback._conn.execute(
                "SELECT predicted_intent, confidence, action_taken "
                "FROM utterances ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if cur:
                meta["intent"] = cur["predicted_intent"] or "general"
                meta["confidence"] = float(cur["confidence"] or 0.0) * 100
                meta["action"] = cur["action_taken"] or "executed"
        except Exception:
            pass
        self.responded.emit(reply or "", meta)


# ─── Main window ────────────────────────────────────────────────────── #

class AerisMainWindow(QMainWindow):
    """Frameless 1440x900 window assembling all v4 surfaces."""

    request_process = pyqtSignal(str)
    request_init    = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("A.E.R.I.S")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(f"QMainWindow {{ background: {C.BG.name()}; }}")

        # ── Build layout ─────────────────────────────────────────────
        central = QWidget()
        central.setStyleSheet(f"background: {C.BG.name()};")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.title_bar = TitleBar()
        root.addWidget(self.title_bar)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0); body_lay.setSpacing(0)

        self.sidebar = Sidebar()
        body_lay.addWidget(self.sidebar)

        # Center column
        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 40, 0, 0); center_lay.setSpacing(28)

        center_lay.addStretch(1)
        self.reactor = ArcReactor()
        center_lay.addWidget(self.reactor, alignment=Qt.AlignHCenter)
        self.state_text = ReactorStateText()
        center_lay.addWidget(self.state_text, alignment=Qt.AlignHCenter)
        center_lay.addStretch(2)

        # Logs at the bottom of the center column
        self.logs = SystemLogsPanel()
        center_lay.addWidget(self.logs)

        body_lay.addWidget(center, stretch=1)

        self.chat = ChatPanel()
        body_lay.addWidget(self.chat)

        root.addWidget(body)
        self.setCentralWidget(central)

        # ── Wire UI events ───────────────────────────────────────────
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.sidebar_toggled.connect(self.sidebar.toggle)

        # Drag-to-move (frameless windows need explicit drag handling)
        self._drag_origin = None
        self._win_origin = None
        self.title_bar.drag_start.connect(self._on_drag_start)
        self.title_bar.drag_move.connect(self._on_drag_move)

        # Chat input → brain
        self.chat.send_text.connect(self._on_user_send)
        self.chat.mic_clicked.connect(self._on_mic_clicked)

        # Initial state + welcome logs (the worker will append more during init).
        self._set_state("IDLE")
        self.logs.add_log("SYS", "AERIS UI mounted. Booting brain…")

        # ── Spin up worker thread ───────────────────────────────────
        self._brain_thread = QThread(self)
        self._brain = BrainWorker()
        self._brain.moveToThread(self._brain_thread)
        self.request_init.connect(self._brain.initialize)
        self.request_process.connect(self._brain.process)

        self._brain.load_progress.connect(self._on_load_progress)
        self._brain.ready.connect(self._on_brain_ready)
        self._brain.responded.connect(self._on_brain_responded)
        self._brain.error.connect(self._on_brain_error)

        self._brain_thread.start()
        # Defer init by one tick so the window shows before the heavy load.
        QTimer.singleShot(50, self.request_init.emit)

    # ── State management ────────────────────────────────────────────
    def _set_state(self, key: str):
        self.title_bar.pill.set_state(key)
        self.reactor.set_state(key)
        self.state_text.set_state(key)
        self.chat.set_state(key)

    # ── Drag + window controls ──────────────────────────────────────
    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _on_drag_start(self, global_pos):
        self._drag_origin = global_pos
        self._win_origin = self.frameGeometry().topLeft()

    def _on_drag_move(self, global_pos):
        if self._drag_origin is None:
            return
        if self.isMaximized():
            return
        delta = global_pos - self._drag_origin
        self.move(self._win_origin + delta)

    # ── Brain wiring ─────────────────────────────────────────────────
    def _on_load_progress(self, log_type: str, msg: str):
        self.logs.add_log(log_type, msg)

    def _on_brain_ready(self):
        self.logs.add_log("ACT", "Brain ready. Type a command to begin.", highlight=True)
        self._set_state("IDLE")

    def _on_user_send(self, text: str):
        self.state_text.set_last_input(text)
        self._set_state("PROCESSING")
        self.logs.add_log("NLU", f'Input received: "{text[:60]}"', highlight=True)
        self.request_process.emit(text)

    def _on_brain_responded(self, reply: str, meta: dict):
        intent     = meta.get("intent",     "general")
        confidence = meta.get("confidence", 0.0)
        latency    = meta.get("latency_ms", 0)
        action     = meta.get("action",     "executed")
        self.logs.add_log(
            "NLU",
            f"Intent: {intent} | Confidence: {confidence:.1f}% | Action: {action}",
            highlight=True,
        )
        if not reply:
            # Silent / empty turn (e.g. memory ack returned None somehow).
            self._set_state("IDLE")
            return
        # Stream the reply into the chat with a green tag pill.
        tag_color = C.GREEN if action in ("executed", "knowledge_retrieved") \
                    else C.RED if action == "error" else C.CYAN
        tag = (f"{intent} • {confidence:.1f}% • {latency}ms", tag_color)
        self._set_state("SPEAKING")
        self.logs.add_log("TTS", f"Streaming response… latency {latency}ms")
        self.chat.stream_message(reply, tag=tag, speed_ms=20)
        # Drop back to IDLE after the typewriter finishes.
        # Length-of-text * speed gives an upper bound; pad +400ms for safety.
        cooldown = max(800, len(reply) * 22 + 400)
        QTimer.singleShot(cooldown, lambda: self._set_state("IDLE"))

    def _on_brain_error(self, msg: str):
        self.logs.add_log("ERR", msg, highlight=True)
        self._set_state("ERROR")
        QTimer.singleShot(1500, lambda: self._set_state("IDLE"))

    def _on_mic_clicked(self):
        # No STT wired in v4 yet — flash LISTENING briefly so the mic glow
        # animates, then return to IDLE. (Real STT lands when C12 is built.)
        self.logs.add_log("MIC", "Voice capture not yet wired in v4 (STT skipped).")
        self._set_state("LISTENING")
        QTimer.singleShot(1200, lambda: self._set_state("IDLE"))

    # ── Cleanup ──────────────────────────────────────────────────────
    def closeEvent(self, e):
        self._brain_thread.quit()
        self._brain_thread.wait(2000)
        super().closeEvent(e)


def launch():
    """Standalone launcher (used by run_gui.py)."""
    app = QApplication.instance() or QApplication(sys.argv)
    win = AerisMainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(launch())
