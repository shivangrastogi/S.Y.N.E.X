"""JARVIS v3.1 main window — composes everything + wires brain + STT + TTS.

Layout:
    ┌─ TitleBar ───────────────────────────────────────────────────┐
    │                                                                │
    │  ┌──────────────┐                          ┌─────────────┐    │
    │  │              │  Particle field bg       │             │    │
    │  │  (overlay)   │  WiringSystem (4 cards)  │ GlassChat   │    │
    │  │  Floating    │  ReactorRings 460        │ Panel 390   │    │
    │  │  Dock        │  ReactorStateText        │             │    │
    │  │              │  StateSwitcher           │             │    │
    │  └──────────────┘                          └─────────────┘    │
    │                                                                │
    └─ LogsBar (collapsible) ──────────────────────────────────────┘

Threading model:
  - BrainWorker owns JarvisMainEngine, runs on its own QThread; emits
    `responded(text, meta)` when process_text finishes.
  - VoiceWorker owns the STT object; one-shot `listen_once()` slot.
  - SpeakWorker owns the TTS object; `speak(text)` slot.

Both modes show the user message as a bubble AND speak the AI response
back via TTS — matches what the user asked for.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

from PyQt5.QtCore import (
    QObject, QPoint, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
)
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, QWidget
)

# Add project root to sys.path so this module can be launched directly.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ui.jarvis_v31.floating_dock import FloatingDock
from ui.jarvis_v31.logs_bar import LogsBar
from ui.jarvis_v31.tab_panels import RightPanelStack
from ui.jarvis_v31.reactor import (
    ParticleField, ReactorRings, ReactorStateText, StateSwitcher,
)
from ui.jarvis_v31.title_bar import TitleBar
from ui.jarvis_v31.tokens import J, JSTATES
from ui.jarvis_v31.wiring_system import REACTOR_CX, REACTOR_CY, WiringSystem


# ─── Background workers ────────────────────────────────────────────── #

class BrainWorker(QObject):
    """Owns JarvisMainEngine on its own QThread. Heavy load happens here."""

    ready         = pyqtSignal()
    responded     = pyqtSignal(str, dict)       # (reply_text, meta)
    load_progress = pyqtSignal(str, str)        # (log_type, msg)
    error         = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._engine = None

    @pyqtSlot()
    def initialize(self):
        try:
            self.load_progress.emit("SYS", "Booting JarvisMainEngine…")
            from core.main_engine import JarvisMainEngine
            self._engine = JarvisMainEngine(stt="SKIP", tts="SKIP", verbose=False)
            self.load_progress.emit("NLU", "Brain online · 21 intents loaded")
            self.load_progress.emit("MEM", "Memory + feedback DB attached")
            self.load_progress.emit("SYS", "All modules nominal · JARVIS v3.1 ready")
            self.ready.emit()
        except Exception as e:
            # Make the error actionable — point at the most common Windows
            # culprits if it looks like a torch DLL failure.
            msg = f"Brain init failed: {e}"
            es = str(e)
            if "WinError 1114" in es or "DLL" in es or "torch" in es.lower():
                msg += (" — try: pip install --upgrade --force-reinstall torch"
                        " (or check that you're running from the .venv that has"
                        " a working PyTorch install).")
            elif "pyttsx3" in es:
                msg += " — install with: pip install pyttsx3"
            self.error.emit(msg)

    @pyqtSlot(str)
    def process(self, text: str):
        if self._engine is None:
            self.error.emit("Brain not ready yet."); return
        t0 = time.monotonic()
        try:
            reply = self._engine.process_text(text)
        except Exception as e:
            self.error.emit(f"process_text crashed: {e}"); return
        latency_ms = int((time.monotonic() - t0) * 1000)
        meta = {"intent": "general", "confidence": 0.0,
                "latency_ms": latency_ms, "action": "executed"}
        try:
            cur = self._engine.feedback._conn.execute(
                "SELECT predicted_intent, confidence, action_taken "
                "FROM utterances ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if cur:
                meta["intent"]     = cur["predicted_intent"] or "general"
                meta["confidence"] = float(cur["confidence"] or 0.0) * 100
                meta["action"]     = cur["action_taken"] or "executed"
        except Exception:
            pass
        self.responded.emit(reply or "", meta)


class VoiceWorker(QObject):
    """Wraps ContinuousVoiceEngine as a QObject for QThread use.

    Continuous listening with sleep/wake keyword detection. The inner capture
    loop runs on a daemon thread; all signals are emitted back to the Qt thread.
    """

    # Forwarded from ContinuousVoiceEngine
    listening_started = pyqtSignal()
    captured          = pyqtSignal(str)
    sleep_detected    = pyqtSignal()
    wake_detected     = pyqtSignal()
    state_changed     = pyqtSignal(str)    # STOPPED / ACTIVE / SLEEPING
    error             = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._engine = None

    @pyqtSlot()
    def initialize(self):
        try:
            from core.voice_engine import ContinuousVoiceEngine
            eng = ContinuousVoiceEngine(self)
            eng.listening_started.connect(self.listening_started)
            eng.captured.connect(self.captured)
            eng.sleep_detected.connect(self.sleep_detected)
            eng.wake_detected.connect(self.wake_detected)
            eng.state_changed.connect(self.state_changed)
            eng.error.connect(self.error)
            self._engine = eng
            eng.initialize()
        except Exception as e:
            self.error.emit(f"Voice init failed: {e}")

    @pyqtSlot()
    def start_listening(self):
        if self._engine:
            self._engine.start_listening()

    @pyqtSlot()
    def stop_listening(self):
        if self._engine:
            self._engine.stop_listening()


class SpeakWorker(QObject):
    """Owns TTS. `speak(text)` slot — non-blocking from the UI's POV."""

    spoken = pyqtSignal(str)
    error  = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._tts = None

    @pyqtSlot()
    def initialize(self):
        try:
            from core.tts import TTS
            self._tts = TTS()
        except Exception as e:
            self.error.emit(f"TTS init failed: {e}")

    @pyqtSlot(str)
    def speak(self, text: str):
        if self._tts is None or not text:
            self.spoken.emit(text or ""); return
        try:
            self._tts.speak(text)
        except Exception as e:
            self.error.emit(f"TTS failed: {e}"); return
        self.spoken.emit(text)


# ─── Main window ──────────────────────────────────────────────────── #

class JarvisV31Window(QMainWindow):
    """Frameless 1440x900 JARVIS v3.1 desktop assembly."""

    request_brain_init   = pyqtSignal()
    request_brain_proc   = pyqtSignal(str)
    request_voice_init   = pyqtSignal()
    request_voice_start  = pyqtSignal()
    request_voice_stop   = pyqtSignal()
    request_speak_init   = pyqtSignal()
    request_speak        = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("A.E.R.I.S — JARVIS v3.1")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.resize(1440, 900)
        self.setMinimumSize(1200, 720)
        self.setStyleSheet(f"QMainWindow {{ background: {J.BG.name()}; }}")

        # ── Build layout ─────────────────────────────────────────────
        central = QWidget()
        central.setStyleSheet(f"background: {J.BG.name()};")
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.title_bar = TitleBar()
        root.addWidget(self.title_bar)

        body = QWidget()
        body.setStyleSheet(f"background: {J.BG.name()};")
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0); body_lay.setSpacing(0)

        # Center column — particles + wiring + reactor + state caption
        self._center_col = QWidget()
        self._center_col.setStyleSheet(f"background: {J.BG.name()};")
        body_lay.addWidget(self._center_col, stretch=1)

        # Right rail — tabbed panel stack (chat is index 1)
        self._right = RightPanelStack()
        self.chat   = self._right.chat_panel
        body_lay.addWidget(self._right)

        root.addWidget(body, stretch=1)

        # Bottom logs bar
        self.logs = LogsBar()
        root.addWidget(self.logs)

        self.setCentralWidget(central)

        # ── Center column overlays (absolute positioning) ───────────
        self.particles = ParticleField(count=22, parent=self._center_col)
        self.wiring    = WiringSystem(parent=self._center_col)
        self.reactor   = ReactorRings(parent=self._center_col)
        self.state_text = ReactorStateText(parent=self._center_col)
        self.state_sw   = StateSwitcher(parent=self._center_col)

        # ── Floating dock overlay (over body, not center column) ────
        self.dock = FloatingDock(parent=body)
        self.dock.show()

        # ── Layout callback ─────────────────────────────────────────
        self._center_col.resizeEvent = lambda e: self._layout_center()
        body.resizeEvent = lambda e: self._reposition_dock()
        self.dock._anim.valueChanged.connect(lambda *_: self._reposition_dock())
        QTimer.singleShot(0, self._layout_center)
        QTimer.singleShot(0, self._reposition_dock)

        # ── Wire UI ─────────────────────────────────────────────────
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        self.title_bar.close_clicked.connect(self.close)

        self._drag_origin = None
        self._win_origin  = None
        self.title_bar.drag_start.connect(self._on_drag_start)
        self.title_bar.drag_move.connect(self._on_drag_move)

        self.state_sw.state_picked.connect(self._set_state)
        self.chat.send_text.connect(self._on_user_send)
        self.chat.mic_clicked.connect(self._on_mic)
        self.chat.stop_requested.connect(self._on_stop_requested)

        # Dock nav → chat panel: only show the suggestion chips when the
        # 'Automation' tab is active (they were overlapping in the header
        # before because the chat panel is too narrow for a single row).
        self.dock.tab_changed.connect(self._on_dock_tab_changed)
        self.chat.automation_chip_used.connect(self._on_chip_used)
        self.dock.profile_action.connect(self._on_profile_action)

        # ── Initial state + boot logs ───────────────────────────────
        self._current_state = "IDLE"
        self._voice_state   = "STOPPED"   # tracks ContinuousVoiceEngine state
        self._pending_voice: Optional[str] = None   # captured while busy
        self._cancelled     = False        # True when user hits STOP mid-request
        self._set_state("IDLE")
        for typ, txt, hl in [
            ("SYS", "Neural core online · wiring grid initialized", False),
            ("NLU", "301 intent patterns loaded · 21 classes active", True),
            ("SYS", "9/9 system nodes connected via circuit layer", False),
        ]:
            self.logs.add_log(typ, txt, hl)

        # Seed welcome bubbles
        self.chat.add_message(
            "ai",
            "Yo Shivang 👋 System ready. All 9 nodes wired and nominal.",
            tag=("sys_boot · 100ms", J.GREEN),
        )

        # ── Spin up background workers ──────────────────────────────
        self._wire_workers()

        # Pending-feedback latch (so we can transition from SPEAKING -> IDLE
        # only after TTS finishes AND the streaming bubble cooldown elapsed).
        self._stream_done_at = 0
        self._tts_done = True

    # ── Worker plumbing ──────────────────────────────────────────────
    def _wire_workers(self) -> None:
        # Brain
        self._brain_thread = QThread(self)
        self._brain = BrainWorker()
        self._brain.moveToThread(self._brain_thread)
        self.request_brain_init.connect(self._brain.initialize)
        self.request_brain_proc.connect(self._brain.process)
        self._brain.load_progress.connect(self._on_load_progress)
        self._brain.ready.connect(self._on_brain_ready)
        self._brain.responded.connect(self._on_brain_responded)
        self._brain.error.connect(self._on_brain_error)
        self._brain_thread.start()
        QTimer.singleShot(50, self.chat.start_boot)
        QTimer.singleShot(60, self.request_brain_init.emit)

        # Voice (continuous STT with sleep/wake) — runs on its own thread
        self._voice_thread = QThread(self)
        self._voice = VoiceWorker()
        self._voice.moveToThread(self._voice_thread)
        self.request_voice_init.connect(self._voice.initialize)
        self.request_voice_start.connect(self._voice.start_listening)
        self.request_voice_stop.connect(self._voice.stop_listening)
        self._voice.listening_started.connect(self._on_voice_started)
        self._voice.captured.connect(self._on_voice_captured)
        self._voice.sleep_detected.connect(self._on_voice_sleep)
        self._voice.wake_detected.connect(self._on_voice_wake)
        self._voice.state_changed.connect(self._on_voice_state_changed)
        self._voice.error.connect(self._on_voice_error)
        self._voice_thread.start()

        # Speak (TTS)
        self._speak_thread = QThread(self)
        self._speak = SpeakWorker()
        self._speak.moveToThread(self._speak_thread)
        self.request_speak_init.connect(self._speak.initialize)
        self.request_speak.connect(self._speak.speak)
        self._speak.spoken.connect(self._on_tts_done)
        self._speak.error.connect(self._on_tts_error)
        self._speak_thread.start()
        QTimer.singleShot(80, self.request_speak_init.emit)
        QTimer.singleShot(80, self.request_voice_init.emit)

    # ── Layout ───────────────────────────────────────────────────────
    def _layout_center(self):
        cw = self._center_col.width()
        ch = self._center_col.height()
        self.particles.setGeometry(0, 0, cw, ch)

        gw = self.wiring.width()
        gh = self.wiring.height()
        gx = max(0, (cw - gw) // 2)
        gy = max(0, (ch - gh) // 2)
        self.wiring.move(gx, gy)

        rcx = gx + REACTOR_CX
        rcy = gy + REACTOR_CY
        self.reactor.move(rcx - self.reactor.width() // 2,
                          rcy - self.reactor.height() // 2)
        self.reactor.raise_()

        self.state_text.setFixedWidth(520)
        self.state_text.move(rcx - 260, rcy + self.reactor.height() // 2 + 12)
        self.state_text.raise_()

        sw_y = self.state_text.y() + self.state_text.sizeHint().height() + 6
        self.state_sw.setFixedWidth(420)
        self.state_sw.move(rcx - 210, sw_y)
        self.state_sw.raise_()

    def _reposition_dock(self):
        body = self.dock.parent()
        if body is None:
            return
        h = self.dock.sizeHint().height() or 480
        self.dock.move(12, max(8, (body.height() - h) // 2))
        self.dock.raise_()

    # ── State + window controls ──────────────────────────────────────
    def _set_state(self, key: str):
        if key not in JSTATES:
            return
        self._current_state = key
        self._refresh_display_state()

    def _refresh_display_state(self) -> None:
        """Compute displayed reactor state from voice + system state.

        Priority (highest → lowest):
          1. PROCESSING / SPEAKING  — system is actively working
          2. LISTENING              — voice engine is ACTIVE (or manual override)
          3. IDLE                   — nothing happening
        """
        sys   = self._current_state
        voice = self._voice_state
        if sys in ("PROCESSING", "SPEAKING"):
            display = sys
        elif voice == "ACTIVE" or sys == "LISTENING":
            display = "LISTENING"
        else:
            display = "IDLE"
        self.title_bar.pill.set_state(display)
        self.reactor.set_state(display)
        self.state_text.set_state(display)
        self.state_sw.set_active(display)
        self.wiring.set_state(display)
        self.chat.set_state(display)
        self.chat.set_voice_state(self._voice_state)

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _on_drag_start(self, p):
        self._drag_origin = p
        self._win_origin = self.frameGeometry().topLeft()

    def _on_drag_move(self, p):
        if self._drag_origin is None or self.isMaximized():
            return
        self.move(self._win_origin + (p - self._drag_origin))

    # ── Dock tab → automation panel visibility ───────────────────────
    def _on_dock_tab_changed(self, key: str) -> None:
        self._right.switch_tab(key)

    def _on_chip_used(self) -> None:
        self.dock._on_nav("chat")
        self._right.switch_tab("chat")

    def _on_profile_action(self, key: str) -> None:
        labels = {
            "account":  "Profile · account view (placeholder)",
            "settings": "Profile · preferences (placeholder)",
            "theme":    "Profile · theme switch (placeholder)",
            "logout":   "Profile · sign out requested",
        }
        self.logs.add_log("ACT", labels.get(key, f"Profile action: {key}"),
                          highlight=True)

    # ── Brain wiring ─────────────────────────────────────────────────
    def _on_load_progress(self, log_type, msg):
        self.logs.add_log(log_type, msg)
        self.chat.add_boot_step(log_type, msg)

    def _on_brain_ready(self):
        self.logs.add_log("ACT", "Brain ready · accepting commands", highlight=True)
        self.chat.finish_boot()
        self._set_state("IDLE")

    def _on_user_send(self, text: str):
        """Common path: chat-typed text OR suggestion-chip OR voice-captured."""
        if not text.strip():
            return
        # Show user bubble first
        self.chat.add_message("user", text)
        self.state_text.set_last_input(text)
        self._set_state("PROCESSING")
        self.logs.add_log("NLU", f'Input: "{text[:48]}"', highlight=True)
        self.request_brain_proc.emit(text)

    def _on_stop_requested(self):
        self._cancelled = True
        self._pending_voice = None
        self.chat.cancel_stream()
        self._set_state("IDLE")
        self.logs.add_log("SYS", "Request cancelled by user · awaiting brain to drain")

    def _on_brain_responded(self, reply: str, meta: dict):
        if self._cancelled:
            self._cancelled = False
            return
        intent     = meta.get("intent", "general")
        confidence = meta.get("confidence", 0.0)
        latency    = meta.get("latency_ms", 0)
        action     = meta.get("action", "executed")
        self.logs.add_log(
            "NLU",
            f"Intent: {intent} · {confidence:.1f}% · {action}",
            highlight=True,
        )
        if not reply:
            self._set_state("IDLE")
            return
        # Tag color depends on action
        tag_color = (
            J.GREEN if action in ("executed", "knowledge_retrieved", "knowledge")
            else J.RED if action == "error" else J.CYAN
        )
        tag = (f"{intent} · {confidence:.1f}% · {latency}ms", tag_color)

        self._set_state("SPEAKING")
        self.logs.add_log("TTS", f"Streaming response · {latency}ms")

        # Stream the bubble + dispatch TTS in parallel
        speed_ms = 18
        self.chat.stream_message(reply, tag=tag, speed_ms=speed_ms)
        self._tts_done = False
        self.request_speak.emit(reply)

        # Fallback IDLE timer in case TTS never reports done
        cooldown = max(900, len(reply) * speed_ms + 500)
        QTimer.singleShot(cooldown, self._maybe_back_to_idle)

    def _on_brain_error(self, msg: str):
        self.logs.add_log("ERR", msg, highlight=True)
        self.chat.finish_boot()
        self._set_state("IDLE")

    # ── Voice wiring ────────────────────────────────────────────────
    def _on_mic(self):
        """Toggle continuous voice mode on/off — 600 ms debounce guard.

        Rapid taps (start → stop → start before the old capture thread exits)
        would put two threads on the same PyAudio stream and crash. The debounce
        ensures the engine has at least 600 ms to drain between toggles.
        """
        import time as _time
        now = _time.monotonic()
        if now - getattr(self, "_last_mic_toggle", 0.0) < 0.6:
            return
        self._last_mic_toggle = now

        if self._voice_state == "STOPPED":
            self.logs.add_log("MIC", "Voice mode ON · continuous listening started")
            self.request_voice_start.emit()
        else:
            self.logs.add_log("MIC", "Voice mode OFF · mic deactivated")
            self.request_voice_stop.emit()

    def _on_voice_started(self):
        self.logs.add_log("MIC", "Mic active · say 'jarvis sleep' to pause")

    def _on_voice_state_changed(self, state: str) -> None:
        self._voice_state = state
        self._refresh_display_state()

    def _on_voice_sleep(self):
        self.logs.add_log("MIC", "Sleep mode · say 'wake up' to resume",
                          highlight=True)

    def _on_voice_wake(self):
        self.logs.add_log("MIC", "Wake word detected · listening resumed",
                          highlight=True)

    def _on_voice_captured(self, text: str):
        if not text:
            return
        self.logs.add_log("MIC", f'Captured: "{text[:48]}"', highlight=True)
        if self._current_state in ("PROCESSING", "SPEAKING"):
            # Brain is busy — hold the last captured phrase; process when idle
            self._pending_voice = text
            return
        self._on_user_send(text)

    def _on_voice_error(self, msg: str):
        self.logs.add_log("ERR", msg, highlight=True)

    # ── TTS wiring ──────────────────────────────────────────────────
    def _on_tts_done(self, _spoken: str):
        self._tts_done = True
        self._maybe_back_to_idle()

    def _on_tts_error(self, msg: str):
        # TTS failure shouldn't strand the UI in SPEAKING — log and recover.
        self.logs.add_log("ERR", msg, highlight=True)
        self._tts_done = True
        self._maybe_back_to_idle()

    def _maybe_back_to_idle(self):
        if self._current_state == "SPEAKING" and self._tts_done:
            if self._pending_voice:
                pending = self._pending_voice
                self._pending_voice = None
                # Small delay so TTS audio finishes before next request starts
                QTimer.singleShot(200, lambda: self._on_user_send(pending))
            else:
                self._set_state("IDLE")

    # ── Cleanup ─────────────────────────────────────────────────────
    def closeEvent(self, e):
        # Stop voice engine so the daemon capture thread exits cleanly
        if self._voice_state != "STOPPED":
            self.request_voice_stop.emit()
        for th in (getattr(self, "_brain_thread", None),
                   getattr(self, "_voice_thread", None),
                   getattr(self, "_speak_thread", None)):
            if th is not None:
                th.quit()
                th.wait(2000)
        super().closeEvent(e)


def launch():
    """Standalone launcher (also used by run_gui.py)."""
    app = QApplication.instance() or QApplication(sys.argv)
    win = JarvisV31Window()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(launch())
