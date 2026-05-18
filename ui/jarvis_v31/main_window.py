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

from ui.jarvis_v31.animation_bus import get_bus
from ui.jarvis_v31.floating_dock import FloatingDock
from ui.jarvis_v31.logs_bar import LogsBar
from ui.jarvis_v31.tab_panels import RightPanelStack
from ui.jarvis_v31.reactor import (
    ParticleField, ReactorRings, ReactorStateText, StateSwitcher,
)
from ui.jarvis_v31.title_bar import TitleBar
from ui.jarvis_v31.tokens import J, JSTATES
from ui.jarvis_v31.command_palette import CommandPalette
from ui.jarvis_v31.system_tray import GlobalHotkeyBridge, TrayController
from ui.jarvis_v31.wiring_system import REACTOR_CX, REACTOR_CY, WiringSystem


# ─── Background workers ────────────────────────────────────────────── #

class BrainWorker(QObject):
    """Owns JarvisMainEngine on its own QThread. Heavy load happens here.

    Boot is driven through ``JarvisMainEngine.setup_iter()`` so the worker
    can emit fine-grained progress between chunks. Each emit is a queued
    signal — the main thread gets a chance to repaint between phases
    instead of seeing the boot bubble freeze at 15 % during the
    sentence-encoder load.
    """

    ready         = pyqtSignal()
    responded     = pyqtSignal(str, dict)            # (reply_text, meta)
    load_progress = pyqtSignal(str, str, int)        # (log_type, msg, pct)
    error         = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._engine = None

    @pyqtSlot()
    def initialize(self):
        try:
            self.load_progress.emit("SYS", "Booting JarvisMainEngine…", 4)
            from core.main_engine import JarvisMainEngine
            # `lazy=True` defers all heavy work to setup_iter() so we can
            # paint progress between chunks instead of blocking on a single
            # multi-second constructor call.
            self._engine = JarvisMainEngine(
                stt="SKIP", tts="SKIP", verbose=False, lazy=True,
            )
            for log_type, msg, pct in self._engine.setup_iter():
                self.load_progress.emit(log_type, msg, pct)
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
    # Marshals a gesture-engine event from its worker thread to the GUI
    # thread (Qt's queued connection makes the hop automatic).
    _gesture_recognized  = pyqtSignal(str)

    def __init__(self, splash=None):
        super().__init__()
        # Optional pre-boot splash — if supplied, the constructor pings it
        # between heavy phases so the user sees the progress bar advance
        # instead of staring at a frozen "Building main window…" line.
        self._splash = splash
        self._splash_phase("Building window shell", 60)

        self.setWindowTitle("A.E.R.I.S — JARVIS v3.1")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.resize(1440, 900)
        self.setMinimumSize(1200, 720)
        self.setStyleSheet(f"QMainWindow {{ background: {J.BG.name()}; }}")

        # Receive the focus message posted by a second-launch attempt
        # (see core/single_instance.py). Stored as an int once for the
        # nativeEvent hot path so we don't pay an import per WM_USER.
        try:
            from core.single_instance import WM_AERIS_FOCUS
            self._WM_AERIS_FOCUS = WM_AERIS_FOCUS
        except Exception:
            self._WM_AERIS_FOCUS = 0

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

        self._splash_phase("Spawning brain worker", 70)

        # ── Spin up background workers ──────────────────────────────
        self._wire_workers()

        self._splash_phase("Wiring resource monitor", 74)

        # ── Resource monitor ────────────────────────────────────────
        # Background psutil sampler — feeds the logs panel and broadcasts
        # memory_pressure events so caches can shrink before the OS pages
        # us out. Started AFTER worker wiring so the first sample reflects
        # a representative resident-set size.
        try:
            from core.resource_monitor import get_monitor
            from core.cache_registry import register_pressure_handler
            from core.shutdown import register as _register_shutdown
            from core.skill_breaker import shutdown_pool as _shutdown_skill_pool
            self._resource_monitor = get_monitor()
            # Wire bounded caches FIRST so the very first pressure event
            # (if RSS is already high at boot) sees a subscriber.
            register_pressure_handler(self._resource_monitor)
            # Then add a higher-impact responder: drop the brain's
            # encoder/neural weights if it's been idle and we're under
            # pressure. Subscribed AFTER the caches so the small caches
            # get a chance to shrink before we evict ~600 MB of weights.
            self._resource_monitor.subscribe(self._on_pressure_unload_brain)
            self._resource_monitor.start()
            _register_shutdown("ResourceMonitor",
                               lambda: self._resource_monitor.stop(timeout=1.0),
                               timeout_s=1.5)
            # Skill breaker thread-pool — cancel any in-flight skill
            # invocations so process exit doesn't hang on a stuck handler.
            _register_shutdown("SkillBreakerPool", _shutdown_skill_pool,
                               timeout_s=1.0)
        except Exception as _e:
            self._resource_monitor = None

        self._splash_phase("Installing tray + hotkey", 78)
        # ── System tray + global hotkey ─────────────────────────────
        self._install_tray_and_hotkey()

        self._splash_phase("Installing power adapter", 81)
        # ── Power + idle adaptive behaviour ─────────────────────────
        self._install_power_adapter()

        self._splash_phase("Starting health server", 84)
        # ── Local /health + /metrics HTTP server ────────────────────
        self._install_health_server()

        self._splash_phase("Starting skill watcher", 87)
        # ── Skill hot-reload watcher ────────────────────────────────
        self._install_skill_watcher()

        self._splash_phase("Building command palette", 90)
        # ── Command palette (Ctrl+K) ────────────────────────────────
        self._install_command_palette()

        self._splash_phase("Starting workspace monitor", 92)
        # ── Workspace profile detector ──────────────────────────────
        self._install_workspace_monitor()

        self._splash_phase("Starting automation engine", 95)
        # ── Automation engine (routines + triggers + actions) ───────
        self._install_automation_engine()

        self._splash_phase("Starting semantic memory", 98)
        # ── Semantic memory (background embedding + recall) ─────────
        try:
            from core.semantic_memory import get as _get_sm
            from core.shutdown import register as _register_shutdown
            _sm = _get_sm()
            _sm.start()
            _register_shutdown("SemanticMemory",
                               lambda: _sm.stop(timeout=1.0),
                               timeout_s=1.5)
        except Exception:
            pass

        # Pending-feedback latch (so we can transition from SPEAKING -> IDLE
        # only after TTS finishes AND the streaming bubble cooldown elapsed).
        self._stream_done_at = 0
        self._tts_done = True

    # ── Splash bridge ────────────────────────────────────────────────
    def _splash_phase(self, label: str, pct: int) -> None:
        """Push a status update + pump events so the splash keeps animating
        during the synchronous parts of the constructor.

        No-op when launched without a splash (tests, ``__main__`` path).
        """
        sp = getattr(self, "_splash", None)
        if sp is None:
            return
        try:
            sp.update_status(f"{label} ({pct}%)")
        except Exception:
            pass
        # processEvents lets the splash QTimer fire and repaint mid-constructor.
        try:
            QApplication.processEvents()
        except Exception:
            pass

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
        # LowestPriority: when the OS scheduler picks between this worker
        # and the GUI thread, the GUI always wins. Critical because the
        # sentence-transformers / spaCy import burns CPU and holds the GIL
        # for ~50-200 ms windows that would otherwise stutter animations.
        self._brain_thread.start(QThread.LowestPriority)
        # Pause the SHARED animation bus while the brain is booting.
        # Every animated widget (reactor, wiring, particles, dots, pills,
        # brand mark, state pill, etc.) subscribes to this single timer —
        # so one pause() halts the whole grid until the brain is ready.
        # That frees the GUI thread to repaint just the boot bubble + chat
        # without competing with 30 FPS reactor/wire renders.
        self._anim_bus = get_bus()
        self._anim_bus.pause()
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
        # Tray icon mirrors the AI state so the user can see "PROCESSING"
        # in the taskbar tray even when the window is minimised.
        tray = getattr(self, "_tray", None)
        if tray is not None and not getattr(self, "_paused", False):
            tray.set_state(display)

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
    def _on_load_progress(self, log_type: str, msg: str, pct: int) -> None:
        self.logs.add_log(log_type, msg)
        self.chat.add_boot_step(log_type, msg, pct)

    def _on_pressure_unload_brain(self, level: int) -> None:
        """When pressure rises, ask the brain to drop idle model weights.

        Runs on ResourceMonitor's thread — only touches brain attributes
        we know are thread-safe (the brain itself locks).
        """
        try:
            from core.resource_monitor import LEVEL_WARNING
            if level >= LEVEL_WARNING:
                engine = getattr(self._brain, "_engine", None)
                if engine is not None and getattr(engine, "brain", None) is not None:
                    engine.brain.try_unload_idle()
        except Exception:
            pass

    def _on_brain_ready(self):
        self.logs.add_log("ACT", "Brain ready · accepting commands", highlight=True)
        self.chat.finish_boot()
        # Animation bus was paused in _wire_workers to keep the GUI smooth
        # while the brain hammered the GIL. Now that we're idle, resume it.
        self._anim_bus.resume()
        self._set_state("IDLE")

    def _on_user_send(self, text: str):
        """Common path: chat-typed text OR suggestion-chip OR voice-captured."""
        if not text.strip():
            return
        # Show user bubble first
        self.chat.add_message("user", text)
        # Auto-record into semantic memory so 'recall' skill can find it later.
        try:
            from core import semantic_memory
            semantic_memory.get().add("user", text)
        except Exception:
            pass
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
        # Record AERIS' side of the exchange so "recall" can surface AI
        # answers too (not just user prompts).
        try:
            from core import semantic_memory
            if reply:
                semantic_memory.get().add("ai", reply)
        except Exception:
            pass
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
        # Even on init failure, resume animations so the user isn't
        # stuck staring at a half-frozen reactor.
        self._anim_bus.resume()
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

    # ── System tray + global hotkey ─────────────────────────────────
    def _install_tray_and_hotkey(self) -> None:
        """Build the QSystemTrayIcon, register the global hotkey, wire
        their signals to the existing window-level actions.

        Both subsystems degrade silently — a system without tray support
        or without the ``keyboard`` package still gets a working AERIS.
        """
        self._tray: Optional[TrayController] = None
        self._hotkey: Optional[GlobalHotkeyBridge] = None
        self._paused = False

        try:
            self._tray = TrayController(parent=self)
            if self._tray.install():
                self._tray.show_window.connect(self._raise_and_activate)
                self._tray.hide_window.connect(self.hide)
                self._tray.toggle_mic.connect(self._on_mic)
                self._tray.pause_toggled.connect(self._on_pause_toggled)
                self._tray.quit_requested.connect(self._on_quit_from_tray)
            else:
                self._tray = None
        except Exception as e:
            self._tray = None

        try:
            self._hotkey = GlobalHotkeyBridge(parent=self)
            if self._hotkey.install():
                # Hotkey activates the window AND starts listening if mic
                # is currently off — single-touch "talk to AERIS".
                self._hotkey.triggered.connect(self._on_global_hotkey)
            else:
                self._hotkey = None
        except Exception:
            self._hotkey = None

    def _on_global_hotkey(self) -> None:
        self._raise_and_activate()
        if self._voice_state == "STOPPED":
            self._on_mic()

    def _on_pause_toggled(self, paused: bool) -> None:
        self._paused = paused
        if paused:
            # When paused: stop voice + halt the animation bus so we burn
            # no CPU but the window stays interactive.
            if self._voice_state != "STOPPED":
                self.request_voice_stop.emit()
            self._anim_bus.pause()
            if self._tray is not None:
                self._tray.set_state("OFFLINE")
        else:
            self._anim_bus.resume()
            if self._tray is not None:
                self._tray.set_state(self._current_state)

    def _on_quit_from_tray(self) -> None:
        # Bypass minimize-to-tray on closeEvent and exit cleanly.
        self._force_quit = True
        self.close()

    # ── Skill hot-reload ────────────────────────────────────────────
    def _install_skill_watcher(self) -> None:
        """Background poller — when a file under ``skills/`` changes,
        reload that module so the user can iterate on plugins without
        restarting AERIS. Surfaces every reload as a logs-bar entry.
        """
        try:
            from core.shutdown import register as _register_shutdown
            from core.skill_watcher import get_watcher
            from core.log_setup import event as _log_event

            def _on_reload(mod_name: str, ok: bool, err):
                if ok:
                    msg = f"reloaded {mod_name}"
                    self.logs.add_log("SYS", msg, False)
                else:
                    self.logs.add_log("SYS", f"reload failed: {mod_name} — {err}",
                                      True)
                _log_event("skill_reload", module=mod_name, ok=ok, error=err)

            self._skill_watcher = get_watcher(on_reload=_on_reload)
            self._skill_watcher.start()
            _register_shutdown("SkillWatcher",
                               lambda: self._skill_watcher.stop(timeout=0.5),
                               timeout_s=1.0)
        except Exception:
            self._skill_watcher = None

    # ── Automation engine ───────────────────────────────────────────
    def _install_automation_engine(self) -> None:
        """Start the routine scheduler + wire its action callbacks.

        The engine runs its own daemon thread for time triggers and
        subscribes to PowerMonitor / WorkspaceMonitor / GestureEngine
        for event triggers. ``ai_prompt`` actions are routed through
        the brain worker via the existing ``request_brain_proc`` signal;
        ``notify`` actions land in the tray toast surface.
        """
        try:
            from core.automation import get_engine as _ge
            from core.shutdown import register as _register_shutdown
            from core.log_setup import event as _log_event
            engine = _ge()

            # ai_prompt → BrainWorker (cross-thread; emit() is thread-safe).
            engine.register_ai_prompt_handler(
                lambda text: self.request_brain_proc.emit(text)
            )

            # notify → tray toast (or logs panel if tray unavailable).
            def _notify(title: str, body: str) -> None:
                if getattr(self, "_tray", None) is not None:
                    self._tray.notify(title, body)
                try:
                    self.logs.add_log("ACT", f"{title} · {body}", False)
                except Exception:
                    pass
            engine.register_notify_handler(_notify)

            engine.start()
            _log_event("automation_started",
                       routine_count=len(engine.list_routines()))
            _register_shutdown("AutomationEngine",
                               lambda: engine.stop(timeout=1.0),
                               timeout_s=1.5)
            self._automation = engine

            # If the routines panel exists, force a refresh so cards
            # reflect the freshly-loaded engine state.
            try:
                self._right.routines_panel.refresh()
            except Exception:
                pass
        except Exception:
            self._automation = None

    # ── Workspace profile detector ──────────────────────────────────
    def _install_workspace_monitor(self) -> None:
        """Polls the foreground process every ~5s and classifies the
        user's current workspace (CODING / MEETING / GAMING / ...).
        Surfaces in the tray tooltip + the logs panel.
        """
        try:
            from core.shutdown import register as _register_shutdown
            from core.workspace_profile import get_monitor as _gw
            from core.log_setup import event as _log_event
            self._workspace_monitor = _gw()
            self._current_profile = "IDLE"

            def _on_profile(profile: str, fg: str) -> None:
                self._current_profile = profile
                _log_event("workspace_changed", profile=profile, foreground=fg)
                self.logs.add_log("SYS", f"workspace: {profile} ({fg or '?'})",
                                  False)
                tray = getattr(self, "_tray", None)
                if tray is not None and tray._tray is not None:
                    tray._tray.setToolTip(
                        f"AERIS · {self._current_state.lower()} · "
                        f"workspace={profile.lower()}"
                    )

            self._workspace_monitor.subscribe(_on_profile)
            self._workspace_monitor.start()
            _register_shutdown("WorkspaceMonitor",
                               lambda: self._workspace_monitor.stop(timeout=0.5),
                               timeout_s=1.0)
        except Exception:
            self._workspace_monitor = None
            self._current_profile = "IDLE"

    # ── Command palette ─────────────────────────────────────────────
    def _install_command_palette(self) -> None:
        """Ctrl+K floats a fuzzy-search overlay over the main window.

        Selecting a skill feeds its primary pattern through the normal
        brain pipeline; selecting an action calls the built-in handler
        (pause / hide / reload / quit).

        Also wires the gesture engine's ``ok_sign`` event to toggle the
        palette so the user can pop it open hands-free.
        """
        try:
            self._palette = CommandPalette(self)
            self._palette.submit_text.connect(self._on_user_send)
            self._palette.action.connect(self._on_palette_action)
        except Exception:
            self._palette = None

        # Bridge: gesture engine fires listeners on a worker thread; we
        # need to invoke palette.toggle() on the GUI thread. Use a queued
        # signal so the cross-thread hop is automatic.
        self._gesture_recognized.connect(self._on_gesture_for_gui)
        try:
            from core.gesture_engine import get_gesture_engine
            eng = get_gesture_engine()
            eng.add_listener(self._gesture_recognized.emit)
        except Exception:
            pass

    def _on_gesture_for_gui(self, name: str) -> None:
        """Runs on the GUI thread. Only handles gestures with UI side
        effects — system actions (lock, mic mute, scroll) are handled
        inside the gesture engine itself.
        """
        if name == "ok_sign" and self._palette is not None:
            self._palette.toggle()
        # Surface every gesture in the logs panel so the user gets
        # immediate feedback that the engine recognised something.
        try:
            self.logs.add_log("ACT", f"gesture: {name}", False)
        except Exception:
            pass
        if self._tray is not None:
            self._tray.notify("Gesture", name.replace("_", " "))

    def _on_palette_action(self, action: str) -> None:
        if action == "quit":
            self._on_quit_from_tray()
        elif action == "hide":
            self.hide()
            if self._tray is not None:
                self._tray.notify("AERIS hidden",
                                  "Right-click the tray icon or press "
                                  "Ctrl+Shift+Space to bring it back.")
        elif action == "pause":
            pause_action = getattr(self._tray, "_pause_action", None) if self._tray else None
            if pause_action is not None:
                pause_action.toggle()
            else:
                self._on_pause_toggled(not getattr(self, "_paused", False))
        elif action == "reload_skills":
            if getattr(self, "_skill_watcher", None) is not None:
                # Force an immediate poll cycle by mutating mtime tracker.
                self._skill_watcher._mtimes = {}
                self.logs.add_log("SYS", "Skill registry rescan queued", False)

    # ── Health server ───────────────────────────────────────────────
    def _install_health_server(self) -> None:
        """Expose /health, /metrics, /skills, /shutdown on
        ``127.0.0.1:8765`` for ``curl`` / external monitors / the mobile
        companion. Loopback-only — no authentication needed.
        """
        try:
            from core.health_server import start_server, stop_server
            from core.shutdown import register as _register_shutdown
            started = start_server(
                brain_ready_fn=lambda: getattr(self._brain, "_engine", None) is not None,
                voice_state_fn=lambda: self._voice_state,
                shutdown_fn=self._on_quit_from_tray,
            )
            if started:
                _register_shutdown("HealthServer", stop_server, timeout_s=1.0)
        except Exception:
            pass

    # ── Power + idle adapter ────────────────────────────────────────
    def _install_power_adapter(self) -> None:
        """Drop animation FPS to 15 when on battery or when the user is
        idle for >5 min; restore 30 FPS when on AC and active. Saves
        ~30 paint events/sec on battery — measurable in
        ``ResourceMonitor`` CPU% when nothing else is happening.
        """
        try:
            from core.power_state import get_monitor as _get_power
            from core.shutdown import register as _register_shutdown
            self._power_monitor = _get_power()
            # Subscribe BEFORE start() so we get the first sample's
            # transition (from unknown → known).
            self._power_monitor.on_power_change(self._on_power_change)
            self._power_monitor.on_idle_change(self._on_idle_change)
            self._power_monitor.start()
            _register_shutdown("PowerMonitor",
                               lambda: self._power_monitor.stop(timeout=1.0),
                               timeout_s=1.5)
        except Exception:
            self._power_monitor = None

    def _on_power_change(self, on_battery: bool, percent: int, plugged: bool) -> None:
        # Called on PowerMonitor's thread — no Qt work here beyond signal
        # emits (set_interval just calls QTimer.start which is queued by
        # Qt to the timer's thread, which IS the GUI thread).
        if on_battery:
            self._anim_bus.use_battery_profile()
            if hasattr(self, "_tray") and self._tray is not None:
                self._tray.notify("On battery",
                                  f"FPS lowered to 15. Battery: {percent}%")
        else:
            # Don't restore FPS if user is currently idle.
            idle_snap = self._power_monitor.snapshot()
            if not idle_snap.is_idle:
                self._anim_bus.use_ac_profile()

    def _on_idle_change(self, idle_s: int, is_idle: bool) -> None:
        if is_idle:
            self._anim_bus.use_battery_profile()
        else:
            # Returning from idle — only restore 30 FPS if also on AC.
            snap = self._power_monitor.snapshot()
            if not snap.on_battery:
                self._anim_bus.use_ac_profile()

    # ── Single-instance focus channel ───────────────────────────────
    def nativeEvent(self, event_type, message):
        """Listen for the WM_AERIS_FOCUS message posted by a second-launch.

        Bring the window to the foreground + activate it. Non-Windows
        platforms simply forward to the base implementation.
        """
        if (self._WM_AERIS_FOCUS
                and sys.platform == "win32"
                and event_type in (b"windows_generic_MSG", "windows_generic_MSG")):
            try:
                import ctypes
                MSG = ctypes.c_void_p(int(message))
                # PyQt5 passes the MSG struct pointer; cast and read message field.
                # Layout: HWND (8) + UINT (4) + ... — message is at offset 8 on 64-bit.
                msg_id = ctypes.c_uint.from_address(int(message) + ctypes.sizeof(ctypes.c_void_p)).value
                if msg_id == self._WM_AERIS_FOCUS:
                    self._raise_and_activate()
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(event_type, message)

    def _raise_and_activate(self) -> None:
        """Restore from minimised + bring to front + give keyboard focus."""
        if self.isMinimized():
            self.showNormal()
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

    # ── Cleanup ─────────────────────────────────────────────────────
    def closeEvent(self, e):
        # Minimise-to-tray instead of exit when the tray is available and
        # the user clicked the X (not "Quit AERIS" from the tray menu).
        if (getattr(self, "_tray", None) is not None
                and not getattr(self, "_force_quit", False)):
            e.ignore()
            self.hide()
            self._tray.notify("AERIS is still running",
                              "Right-click the tray icon to quit.")
            return

        # Real shutdown path.
        if self._voice_state != "STOPPED":
            self.request_voice_stop.emit()
        if getattr(self, "_hotkey", None) is not None:
            self._hotkey.uninstall()
        if getattr(self, "_tray", None) is not None:
            self._tray.uninstall()
        for th in (getattr(self, "_brain_thread", None),
                   getattr(self, "_voice_thread", None),
                   getattr(self, "_speak_thread", None)):
            if th is not None:
                th.quit()
                th.wait(2000)
        # Fire the shutdown coordinator AFTER threads are joined so its
        # hooks (ResourceMonitor, feedback flush, etc.) see a quiesced
        # process and aren't racing live workers for the GIL.
        try:
            from core.shutdown import fire as _shutdown_fire
            _shutdown_fire(reason="closeEvent")
        except Exception:
            pass
        super().closeEvent(e)


def launch(splash=None):
    """Standalone launcher (also used by run_gui.py).

    Splash-first lifecycle
    ----------------------
    When a ``splash`` is supplied we keep it visible UNTIL the brain
    finishes loading, then atomically replace it with the main window.
    The user never sees a half-loaded GUI:

        splash up
          → ML imports finish
          → main window CONSTRUCTED (spawns brain worker) but HIDDEN
          → brain boot progress mirrored to splash status text
          → brain emits 'ready'
          → splash closes, window.show(), animations resume

    Without a splash we keep the original behaviour (show immediately,
    boot bubble in chat) — used by tests and standalone launches.
    """
    app = QApplication.instance() or QApplication(sys.argv)

    # Install the shutdown coordinator so SIGINT / Qt quit / atexit all
    # converge on the same teardown path. Idempotent — safe even if
    # run_gui.py already called install_handlers().
    try:
        from core.shutdown import install_handlers, install_qt_handler
        install_handlers()
        install_qt_handler(app)
    except Exception:
        pass

    # Pass the splash INTO the window so its constructor can post phase
    # updates between the synchronous installs — keeps the splash text +
    # progress moving instead of freezing at "Building main window".
    win = JarvisV31Window(splash=splash)

    if splash is None:
        # Legacy path — show immediately, brain loads in background.
        win.show()
        return app.exec_()

    # Splash-first path: keep window hidden while brain boots.
    # Update splash status from the same load_progress signal that
    # drives the in-chat boot bubble.
    def _on_progress(_log_type, msg, pct):
        try:
            splash.update_status(f"{msg} ({pct}%)")
        except Exception:
            pass

    def _on_ready():
        # Brain is up. Hand off to the real window — show first, then
        # close splash so there's no visible gap.
        try:
            win.show()
            win.raise_()
            win.activateWindow()
        finally:
            try: splash.finish(win)
            except Exception: pass

    try:
        win._brain.load_progress.connect(_on_progress)
        win._brain.ready.connect(_on_ready)
        # Safety net: if the brain dies during boot, still show the
        # window so the user can see the error in the logs panel.
        win._brain.error.connect(lambda _msg: _on_ready())
    except Exception:
        # Couldn't wire — fall back to showing the window right away.
        win.show()
        splash.finish(win)

    return app.exec_()


if __name__ == "__main__":
    sys.exit(launch())
