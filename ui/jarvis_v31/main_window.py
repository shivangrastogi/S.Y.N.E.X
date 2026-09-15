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
    QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, QWidget,
    QDialog, QLabel, QPushButton
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


class _PhoneLiveWindow(QDialog):
    """Phase 4 — a live view of the phone's screen (frames pushed via
    set_frame). Closing it (X or the Stop button) tells the phone to stop
    streaming so no orphan share keeps burning the relay quota."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AERIS — Phone screen (live)")
        self.setModal(False)
        self.resize(360, 720)
        self.setStyleSheet("background:#0a0e14;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self._img = QLabel("Phone se pehli frame aa rahi hai…")
        self._img.setAlignment(Qt.AlignCenter)
        self._img.setStyleSheet("color:#7fdfff;")
        self._img.setMinimumSize(320, 600)
        lay.addWidget(self._img, 1)
        btn = QPushButton("■  Stop screen share")
        btn.setStyleSheet(
            "QPushButton{background:#c62828;color:white;font-weight:700;"
            "padding:10px;border:none;border-radius:6px;}"
            "QPushButton:hover{background:#e53935;}")
        btn.clicked.connect(self.close)
        lay.addWidget(btn)

    def set_frame(self, pixmap) -> None:
        scaled = pixmap.scaled(self._img.width(), self._img.height(),
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._img.setPixmap(scaled)

    def closeEvent(self, ev):
        # Tell the phone to stop + drop the parent's handle so a later frame
        # rebuilds a fresh window instead of touching a dead one.
        try:
            from core.cloud_bridge import get_bridge
            get_bridge().stop_phone_stream()
        except Exception:
            pass
        p = self.parent()
        if p is not None and getattr(p, "_phone_live", None) is self:
            p._phone_live = None
        super().closeEvent(ev)


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
    proactive     = pyqtSignal(str, dict)            # (offer_text, offer)

    def __init__(self):
        super().__init__()
        self._engine = None

    # Heavy ML modules imported HERE on the worker thread — the window is
    # already on screen when these run. Each phase gets its own progress
    # emit so the boot bubble advances instead of freezing.
    _HEAVY_MODULES = [
        ("torch",                 "Loading PyTorch runtime",           8),
        ("sentence_transformers", "Loading sentence-transformers",    16),
        ("sklearn.neighbors",     "Loading scikit-learn",             24),
        ("spacy",                 "Loading spaCy NLP runtime",        29),
        ("transformers",          "Loading HuggingFace transformers", 34),
    ]

    @pyqtSlot()
    def initialize(self):
        try:
            # ── Isolated-brain path (AERIS_SPLIT_BRAIN=1) ────────────────
            # torch runs in a CHILD process; the GUI process imports NO ML.
            # This is the fix for the 0xC0000374 heap crash — torch executing
            # inside this Qt worker thread corrupts the heap on the first
            # encode (docs §6.6.3); in a child process it's safe. Off by
            # default → the in-process path below is byte-for-byte unchanged.
            from core.brain_backend import use_split_brain
            if use_split_brain():
                self._initialize_split()
                return

            # Gentle-boot throttle: a short sleep between phases releases
            # the GIL + CPU so animations stay smooth on iGPU-less laptops.
            # Boot may take longer overall — that's fine, the app is
            # already open and responsive. Tunable via env.
            try:
                throttle_ms = int(os.environ.get("AERIS_BOOT_THROTTLE_MS", "90"))
            except ValueError:
                throttle_ms = 90

            def _breathe():
                if throttle_ms > 0:
                    QThread.msleep(throttle_ms)

            # AERIS_LITE_ML: the whole point is that no ML lands in RAM until
            # an utterance needs it — so skip the pre-import parade (and the
            # torch thread-pinning that would import torch to do it). The
            # engine's tiered router pins torch on its own first load.
            from core.lite_ml import lite_ml_enabled
            _lite = lite_ml_enabled()

            if _lite:
                self.load_progress.emit(
                    "NLU", "Lite boot — ML deferred until needed", 30)
            else:
                for mod, label, pct in self._HEAVY_MODULES:
                    self.load_progress.emit("NLU", label, pct)
                    try:
                        __import__(mod)
                    except Exception as ie:
                        # Missing optional module (e.g. spaCy) is not fatal —
                        # downstream loaders degrade gracefully.
                        import logging as _log
                        _log.getLogger(__name__).info(
                            "[BrainWorker] pre-import %s skipped: %s", mod, ie)
                    _breathe()

                # Pin torch to a single compute thread — the OpenMP duplicate
                # runtime (KMP_DUPLICATE_LIB_OK) corrupts the heap during
                # multi-threaded tensor ops; single-thread removes the race.
                try:
                    import torch as _torch
                    _torch.set_num_threads(1)
                    _torch.set_num_interop_threads(1)
                except Exception:
                    pass

            self.load_progress.emit("SYS", "Booting JarvisMainEngine…", 38)
            from core.main_engine import JarvisMainEngine
            # `lazy=True` defers all heavy work to setup_iter() so we can
            # paint progress between chunks instead of blocking on a single
            # multi-second constructor call.
            self._engine = JarvisMainEngine(
                stt="SKIP", tts="SKIP", verbose=False, lazy=True,
            )
            for log_type, msg, pct in self._engine.setup_iter():
                # setup_iter yields 4..100 — rescale into the 38..100 band
                # left after the pre-import phases above.
                self.load_progress.emit(log_type, msg, 38 + int(pct * 0.62))
                _breathe()
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

    def _initialize_split(self):
        """Bring up the brain in its OWN process (RemoteBrain over the service
        bus) and expose it through the same ``self._engine`` seam the GUI's
        ``process`` slot already uses — ``process_text`` + ``last_dispatch``
        are provided by RemoteBrain, and the feedback-DB fallback in
        ``process`` is already try/except-guarded, so nothing else changes."""
        import logging as _log
        log = _log.getLogger(__name__)
        self.load_progress.emit("SYS", "Starting isolated brain process…", 20)
        try:
            from core.remote_brain import RemoteBrain
            rb = RemoteBrain()
            self._engine = rb          # set before start so a stray process()
                                       # degrades gracefully ("dimaag load…")
            self.load_progress.emit("NLU", "Loading brain in child process…", 55)
            ok = rb.start(ready_timeout=240.0)
            if not ok:
                log.error("[BrainWorker] isolated brain not ready in time")
                self.error.emit("Isolated brain did not become ready in time. "
                                "Unset AERIS_SPLIT_BRAIN to use the in-process brain.")
                return
            log.info("[BrainWorker] isolated brain ready (child process)")
            self.load_progress.emit("SYS", "Isolated brain ready · accepting commands", 100)
            self.ready.emit()
        except Exception as e:
            log.exception("[BrainWorker] split-brain init failed")
            self.error.emit(f"Isolated brain init failed: {e}")

    @pyqtSlot(str)
    def process(self, text: str):
        import threading as _th, logging as _lg
        _lg.getLogger(__name__).info(
            "[trace] BrainWorker.process thread=%s text=%r",
            _th.current_thread().name, text[:60])
        if self._engine is None:
            self.error.emit("Brain not ready yet."); return
        # Clear the dispatch side-channel so a previous turn's skill can
        # never be misattributed to this turn's chip.
        self._engine.last_dispatch = None
        t0 = time.monotonic()
        try:
            reply = self._engine.process_text(text)
        except Exception as e:
            self.error.emit(f"process_text crashed: {e}"); return
        latency_ms = int((time.monotonic() - t0) * 1000)
        meta = {"intent": "general", "confidence": 0.0,
                "latency_ms": latency_ms, "action": "executed"}
        # Preferred source: the engine's synchronous dispatch side-channel
        # (exact intent/confidence/latency for THIS turn). Fallback: last
        # feedback-DB row (covers chat_fallback / rejected turns).
        ld = getattr(self._engine, "last_dispatch", None)
        if ld:
            meta["intent"]     = ld.get("intent") or "general"
            meta["confidence"] = float(ld.get("confidence") or 0.0) * 100
            meta["action"]     = ld.get("action") or "executed"
            meta["latency_ms"] = int(ld.get("latency_ms") or latency_ms)
        else:
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

    @pyqtSlot()
    def poll_proactive(self):
        """Drain the isolated brain's proactive offers — SPLIT MODE ONLY.

        In-process, proactivity is self-contained: the engine's own scheduler
        surfaces initiatives and speaks them directly. In split mode the
        engine lives in the child, `brain_service`'s ticker pushes them onto
        the bus as `event:offer`, and `RemoteBrain.poll_events()` buffers
        them — but nothing was draining that buffer, so offers reached the GUI
        process and died there. This is the missing drain.

        Runs on the brain thread (queued from the GUI's timer), so it can
        never block painting; `poll_events` is just a buffer read.
        """
        poll = getattr(self._engine, "poll_events", None)
        if poll is None:
            return                      # in-process backend — nothing to do
        try:
            from core.remote_brain import extract_offers
            for text, payload in extract_offers(poll()):
                self.proactive.emit(text, payload)
        except Exception as e:
            import logging as _lg
            _lg.getLogger(__name__).debug("[BrainWorker] poll_proactive: %s", e)


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
            # Split-mode aware: returns ContinuousVoiceEngine unless
            # AERIS_SPLIT_VOICE=1, in which case the mic and speaker live in a
            # child process behind the same signals (§6.31).
            from core.voice_engine import make_voice_engine
            eng = make_voice_engine(self)
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
    request_brain_poll   = pyqtSignal()      # split mode: drain proactive offers
    request_voice_init   = pyqtSignal()
    request_voice_start  = pyqtSignal()
    request_voice_stop   = pyqtSignal()
    request_speak_init   = pyqtSignal()
    request_speak        = pyqtSignal(str)
    # Marshals a gesture-engine event from its worker thread to the GUI
    # thread (Qt's queued connection makes the hop automatic).
    _gesture_recognized  = pyqtSignal(str)
    # Marshals the pairing-QR popup onto the GUI thread. Creating a QDialog
    # off the GUI thread hard-crashes Qt ("Cannot set parent, different
    # thread"); emitting a signal whose receiver lives on the GUI thread
    # guarantees the dialog is built there. (qr_path, pid8)
    _show_pair_qr        = pyqtSignal(str, str)
    # GUI-thread re-entry guards. If _on_user_send / _on_voice_captured are
    # ever invoked from a non-GUI thread (voice capture daemon, bridge),
    # touching widgets/QTimers there is a HARD Qt crash ("Timers cannot be
    # started from another thread"). These signals bounce the call back
    # onto the GUI thread via a queued connection.
    _gui_cmd             = pyqtSignal(str)
    _gui_voice_cap       = pyqtSignal(str)
    # Phone → laptop status reply (e.g. phone battery) marshaled to GUI.
    _phone_status        = pyqtSignal(dict)
    # Phone screen image (jpeg bytes, caption) marshaled to GUI thread.
    _phone_screen        = pyqtSignal(bytes, str)
    # Phase 2: phone→laptop WebRTC frame as a raw BGR ndarray (no JPEG hop).
    _phone_screen_np     = pyqtSignal(object)
    # Phase 4: phone tapped Exit on its own share → close the live window.
    _phone_live_stop     = pyqtSignal()
    # Phone paired + talking → auto-close the QR dialog.
    _phone_paired        = pyqtSignal()

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
        # Audit fix B1: text quick-actions fired a signal nobody listened
        # to — every "kind:text" card was a dead button. Route to the brain.
        #
        # Connected to the STACK's relays, not the panels themselves: both
        # panels are built on first view (§4.1), and reaching through to
        # `.quick_panel` / `.abilities_panel` here would construct them at
        # boot — exactly what the lazy stack exists to avoid. The stack
        # forwards each panel's signal into these once it is built, and
        # neither can fire earlier: they come from buttons the user has to
        # see to press.
        self._right.quick_submit_text.connect(self._on_user_send)
        # Abilities index: clicking a skill row lands its spoken phrase in
        # the chat input (prefill, never auto-run) and jumps to Chat.
        self._right.abilities_use_phrase.connect(self._on_use_phrase)

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

        # PROCESSING watchdog: if the brain doesn't answer within a bounded
        # budget (slow LLM / wedged skill / hung call) this fires and force-
        # resets the UI back to LISTENING so voice never gets stranded.
        self._proc_watchdog = QTimer(self)
        self._proc_watchdog.setSingleShot(True)
        self._proc_watchdog.timeout.connect(self._on_processing_timeout)

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

        # Subsystem handles default to None so closeEvent, the tray-quit
        # path, and health probes are all safe even before their staged
        # install (below) has run.
        self._resource_monitor = None
        self._power_monitor = None
        self._tray = None
        self._hotkey = None
        self._palette = None
        self._skill_watcher = None
        self._force_quit = False
        self._paused = False

        self._splash_phase("Spawning brain worker", 70)

        # ── Spin up background workers ──────────────────────────────
        self._wire_workers()

        # ── Command palette hotkey (Ctrl+Shift+P) ──────────────────
        # In-app QShortcut, NOT a global hotkey — avoids conflicts with
        # Windows shortcuts. Works whenever the AERIS window is focused.
        try:
            from PyQt5.QtWidgets import QShortcut
            from PyQt5.QtGui import QKeySequence
            self._palette_shortcut = QShortcut(
                QKeySequence("Ctrl+Shift+P"), self,
            )
            self._palette_shortcut.activated.connect(self._open_command_palette)
            # main_window has no module-level ``log`` — use logging directly.
            import logging as _log
            _log.getLogger(__name__).info(
                "[main_window] command palette shortcut registered: Ctrl+Shift+P")
        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).info(
                "[main_window] palette shortcut install failed: %s", e)

        # ── Staged subsystem boot ───────────────────────────────────
        # Every install below used to run synchronously inside this
        # constructor, delaying first paint by several seconds. They now
        # run one per QTimer tick AFTER the window is visible, spaced
        # out so boot cost is spread thin and the UI never stutters —
        # the app *feels* open instantly even on weak laptops.
        #
        # Each stage is registered with the process-wide SubsystemRegistry,
        # which remembers the outcome (so `/subsystems` and the log panel can
        # report it) and retries the ones whose failure is a *race* rather
        # than an absence. The retry budgets below encode that distinction:
        #
        #   max_retries=0  — it works on this machine or it never will.
        #                    No tray in the shell, no hotkey slot free, no
        #                    second screen. Retrying just burns CPU.
        #   max_retries>0  — it lost a race and may win the next one. The
        #                    health server's port is the canonical case: a
        #                    previous AERIS still draining holds 8765 for a
        #                    few seconds, and the old code gave up forever
        #                    on a conflict that resolves itself.
        from core.subsystem_registry import get_registry
        self._subsystems = get_registry()
        _RETRY = {                     # name → (max_retries, backoff_s)
            "health server":     (3, 5.0),    # port 8765 frees up
            "workspace monitor": (2, 15.0),   # WMI/Win32 hooks can be flaky
            "semantic memory":   (2, 20.0),   # disk/index contention
            "skill watcher":     (2, 10.0),   # filesystem watch handles
        }
        self._boot_stages = [
            ("resource monitor",  self._install_resource_monitor),
            ("tray + hotkey",     self._install_tray_and_hotkey),
            ("power adapter",     self._install_power_adapter),
            ("health server",     self._install_health_server),
            ("skill watcher",     self._install_skill_watcher),
            ("command palette",   self._install_command_palette),
            ("workspace monitor", self._install_workspace_monitor),
            ("automation engine", self._install_automation_engine),
            ("semantic memory",   self._install_semantic_memory),
        ]
        for _label, _install in self._boot_stages:
            _r, _b = _RETRY.get(_label, (0, 5.0))
            self._subsystems.register(
                _label, _install, max_retries=_r, backoff_s=_b)
        QTimer.singleShot(450, self._run_next_boot_stage)

        # Pending-feedback latch (so we can transition from SPEAKING -> IDLE
        # only after TTS finishes AND the streaming bubble cooldown elapsed).
        self._stream_done_at = 0
        self._tts_done = True

    # ── Staged subsystem boot ────────────────────────────────────────
    def _run_next_boot_stage(self) -> None:
        """Pop + run one install from the staged boot queue, then schedule
        the next tick. Each stage is individually fault-isolated — one
        broken subsystem never blocks the rest of the boot."""
        if not self._boot_stages:
            import logging as _log
            _log.getLogger(__name__).info(
                "[main_window] staged subsystem boot complete — %s — "
                "starting heavy init (brain FIRST, then tts + voice)",
                self._subsystems.summary_line())
            self._report_subsystem_health()
            # Heavy engine init runs ONE stack at a time so no two import
            # grinds ever thrash the GIL together. The brain (torch +
            # encoder) goes FIRST and alone: it is BOTH the critical path
            # to "accepting commands" AND the heaviest load, so running it
            # uncontended is the fastest route to a usable app and avoids
            # thrashing the GIL against the tts/voice grinds. TTS + the
            # vosk/pyaudio voice stack are kicked only once the brain
            # reports ready (see _kick_secondary_init) — by then the user
            # is only just starting to type, and SpeakWorker degrades
            # gracefully (shows text, skips speech) if the very first reply
            # beats TTS coming up. This shaves ~15-18s off time-to-ready
            # versus the old tts → voice → brain ordering.
            # Idempotent — split-brain may have already pre-warmed this at
            # window construction (see _kick_brain_init_once).
            self._kick_brain_init_once()
            # Safety net: if the brain init hangs WITHOUT emitting ready or
            # error, don't strand tts/voice forever — bring them up anyway.
            QTimer.singleShot(30000, self._kick_secondary_init)
            return
        label, _install = self._boot_stages.pop(0)
        # The registry runs it fault-isolated, times it, logs it loudly, and
        # schedules a retry if this subsystem has budget for one. `boot`
        # never raises, so the tick chain below is unconditional.
        self._subsystems.boot(label)
        QTimer.singleShot(250, self._run_next_boot_stage)

    def _report_subsystem_health(self) -> None:
        """Put boot failures where the user can actually see them.

        The staged installs have always been fault-isolated, but a failure
        only ever reached the log file — so a session with no tray icon and
        no /health endpoint looked, from inside the app, exactly like a
        healthy one. Anything still down after boot now says so in the log
        panel, and says whether it is coming back.
        """
        try:
            snap = self._subsystems.snapshot()
            for name in snap["degraded"]:
                self.logs.add_log(
                    "WRN", f"{name} unavailable — retrying in background",
                    highlight=False)
            for name in snap["failed"]:
                rec = self._subsystems.get(name)
                why = rec.last_error if rec else ""
                self.logs.add_log(
                    "ERR", f"{name} offline this session — {why}",
                    highlight=True)
            if not snap["degraded"] and not snap["failed"]:
                self.logs.add_log("SYS", self._subsystems.summary_line())
        except Exception:
            pass

    def _sweep_subsystem_retries(self) -> None:
        """Reconnect anything whose backoff has elapsed.

        Pull-based: the registry owns no thread, so the sweep rides the idle
        watchdog's existing 5 s tick rather than adding a timer. A tick with
        nothing due is a dict scan under a lock.
        """
        try:
            # Liveness first: a subsystem that died quietly should be marked
            # DEGRADED before we ask what is due, so it can be picked up on
            # this sweep rather than the next one.
            self._probe_subsystem_liveness()
            for name, recovered in self._subsystems.retry_due().items():
                if recovered:
                    self.logs.add_log("SYS", f"{name} reconnected")
        except Exception:
            pass

    def _probe_subsystem_liveness(self) -> None:
        """Catch subsystems that stopped working without saying so.

        Most failures announce themselves (an exception at install, an error
        signal from voice). The bridge does not: its Firestore listener can
        die — token expiry, dropped socket, the laptop sleeping — while
        `_started` stays True, so it looks healthy while receiving nothing
        until someone restarts AERIS. This is the poll that notices.
        """
        try:
            from core import bridge_subsystem
            bridge_subsystem.check_liveness(self._subsystems)
        except Exception:
            pass

    def _kick_brain_init_once(self) -> None:
        """Emit request_brain_init exactly once. Split-brain pre-warms it at
        window construction; the staged-boot completion also calls this — a
        no-op once kicked, so the child brain is never spawned twice."""
        if getattr(self, "_brain_init_kicked", False):
            return
        self._brain_init_kicked = True
        self._post_brain_pending = True
        self.request_brain_init.emit()

    def _kick_secondary_init(self) -> None:
        """Bring up TTS then the vosk/pyaudio voice stack — once, after the
        brain is ready (or failed, or a safety timeout elapsed). Idempotent:
        guarded by ``_post_brain_pending`` so the ready-signal, the error
        path and the safety timer can all call it without double-init."""
        if not getattr(self, "_post_brain_pending", False):
            return
        self._post_brain_pending = False
        import logging as _log
        _log.getLogger(__name__).info(
            "[main_window] brain settled — starting tts + voice init")
        self.request_speak_init.emit()
        # Voice is registered here rather than with the staged installs
        # because it only becomes bootable now — the vosk/pyaudio grind must
        # not overlap the brain's. Two reconnects at 20 s / 40 s: a mic held
        # by another app (Meet, Zoom, a previous AERIS draining) is the
        # common failure and it usually clears within a minute. After that
        # it stays down — a machine with no working mic will not grow one,
        # and the user can re-arm it from the mic toggle.
        self._subsystems.register(
            "voice", self._install_voice, teardown=self._teardown_voice,
            max_retries=2, backoff_s=20.0)
        # Space the vosk/pyaudio grind a beat after the tts client setup so
        # the two don't import-thrash together.
        QTimer.singleShot(2500, lambda: self._subsystems.boot("voice"))

    def _install_voice(self) -> None:
        """Ask the voice worker (own QThread) to initialise.

        The emit is queued across the thread boundary, so this returning
        means "asked", not "listening" — a failure inside the worker comes
        back later on the `error` signal and lands in `_on_voice_error`,
        which marks the subsystem DEGRADED and lets the registry schedule
        the reconnect. Boot-time and runtime failures therefore share one
        recovery path.
        """
        self.request_voice_init.emit()

    def _teardown_voice(self) -> None:
        """Stop listening before a reconnect so the second `initialize`
        does not race the first for the microphone handle."""
        self.request_voice_stop.emit()

    def _install_resource_monitor(self) -> None:
        """Background psutil sampler — feeds the logs panel and broadcasts
        memory_pressure events so caches can shrink before the OS pages
        us out."""
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

    def _install_semantic_memory(self) -> None:
        """Semantic memory — background embedding + recall."""
        from core.semantic_memory import get as _get_sm
        from core.shutdown import register as _register_shutdown
        _sm = _get_sm()
        _sm.start()
        _register_shutdown("SemanticMemory",
                           lambda: _sm.stop(timeout=1.0),
                           timeout_s=1.5)

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
        self.request_brain_poll.connect(self._brain.poll_proactive)
        self._brain.load_progress.connect(self._on_load_progress)
        self._brain.ready.connect(self._on_brain_ready)
        self._brain.responded.connect(self._on_brain_responded)
        self._brain.proactive.connect(self._on_brain_proactive)
        self._brain.error.connect(self._on_brain_error)
        # Pairing-QR popup marshaled onto the GUI thread (see signal decl).
        self._show_pair_qr.connect(self._do_show_pair_dialog)
        # GUI-thread re-entry guards (see signal decls).
        self._gui_cmd.connect(self._on_user_send)
        self._gui_voice_cap.connect(self._on_voice_captured)
        # Phone status replies → chat (marshaled to GUI thread).
        self._phone_status.connect(self._on_phone_status_gui)
        self._phone_screen.connect(self._on_phone_screen_gui)
        self._phone_screen_np.connect(self._on_phone_screen_np_gui)
        self._phone_live_stop.connect(self._close_phone_live)
        self._phone_paired.connect(self._on_phone_paired_gui)
        # Live-view window handle (Phase 4). Lazily built on first frame.
        self._phone_live = None
        # Phase 2 direct-render coalescing state.
        self._phone_pending_np = None
        self._phone_repaint_scheduled = False
        try:
            from core.cloud_bridge import get_bridge
            _b = get_bridge()
            _b.on_phone_status(lambda st: self._phone_status.emit(dict(st)))
            _b.on_phone_screen(
                lambda jpg, cap: self._phone_screen.emit(bytes(jpg), cap or ""))
            _b.on_phone_screen_np(
                lambda img: self._phone_screen_np.emit(img))
            _b.on_control(lambda action: self._phone_live_stop.emit()
                          if action in ("stop_phone_stream",
                                        "phone_stream_stopped") else None)
            _b.on_phone_connected(lambda: self._phone_paired.emit())
            _b.on_file_received(
                lambda p: self._phone_status.emit(
                    {"_screen_answer": f"📥 Phone se file aayi:\n{p}"}))
        except Exception:
            pass
        # LowestPriority: when the OS scheduler picks between this worker
        # and the GUI thread, the GUI always wins. Critical because the
        # sentence-transformers / spaCy import burns CPU and holds the GIL
        # for ~50-200 ms windows that would otherwise stutter animations.
        self._brain_thread.start(QThread.LowestPriority)
        # Run the SHARED animation bus in its low-power (15 FPS) battery
        # profile while the brain is booting. The window is on screen from
        # second one, so a fully-paused (frozen) UI would look dead — the
        # reactor should visibly pulse through the loading minute. 15 FPS
        # halves paint cost vs the normal 30 FPS profile, leaving the GUI
        # thread plenty of headroom against the worker's GIL windows.
        # _on_brain_ready switches to the full AC profile.
        self._anim_bus = get_bus()
        self._anim_bus.use_battery_profile()
        self._install_idle_watchdog()
        QTimer.singleShot(50, self.chat.start_boot)
        # Brain init: IN-PROCESS mode is NOT kicked here — _run_next_boot_stage()
        # emits request_brain_init after the last staged subsystem install, so
        # the torch/encoder import grind (which holds the GIL in long native
        # stretches) never competes with first paint or the tray/health/palette
        # installs. SPLIT-BRAIN mode PRE-WARMS instead: the isolated brain loads
        # torch in a CHILD process, so it never touches this process's GIL —
        # kicking it NOW overlaps its ~30-40s child load with first paint + the
        # staged installs, shaving that off boot-to-ready.
        try:
            from core.brain_backend import use_split_brain
            if use_split_brain():
                QTimer.singleShot(0, self._kick_brain_init_once)
        except Exception:
            pass

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
        # TTS + STT engine init is NOT scheduled here. All heavy init is
        # serialized by _run_next_boot_stage(): staged installs → TTS →
        # voice → brain, one grind at a time. Three import stacks loading
        # concurrently thrash the GIL and starve the paint timer — one at
        # a time keeps the UI fluid the whole way through.

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
        # AERIS thinking/speaking counts as activity even when the user is
        # sitting still — that is exactly when the reactor should animate at
        # full rate. Only IDLE lets the idle profile start counting down.
        if key != "IDLE":
            try:
                self._anim_bus.note_activity()
            except Exception:
                pass
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
        # Structured log line so we can confirm from data/logs/aeris.log
        # that this handler actually fired (the in-app logs panel doesn't
        # write to the file log).
        import logging as _log
        _log.getLogger(__name__).info("[main_window] _on_brain_ready: resuming animations + accepting commands")
        self.logs.add_log("ACT", "Brain ready · accepting commands", highlight=True)
        try:
            self.chat.finish_boot()
        except Exception as e:
            _log.getLogger(__name__).warning("[main_window] chat.finish_boot raised: %s", e)
        # The bus ran the low-power 15 FPS profile during boot — lift it to
        # the full-speed profile now (unless we're actually on battery, in
        # which case the power adapter will keep/put it back at 15).
        try:
            self._anim_bus.resume()
            pm = getattr(self, "_power_monitor", None)
            snap = pm.snapshot() if pm is not None else None
            if snap is None or not snap.on_battery:
                self._anim_bus.use_ac_profile()
        except Exception as e:
            _log.getLogger(__name__).warning("[main_window] _anim_bus resume/profile raised: %s", e)
        self._set_state("IDLE")
        _log.getLogger(__name__).info("[main_window] _on_brain_ready: done")
        # Brain is up and accepting commands — now bring up the secondary
        # stacks (TTS, then voice) that were deferred behind it at boot.
        self._kick_secondary_init()
        self._start_proactive_poller()
        self._supervise_bridge()

    def _supervise_bridge(self) -> None:
        """Put the phone bridge under the subsystem registry — in-process
        brain only.

        Registered here rather than with the staged installs because
        `CloudBridge.start()` needs the engine hook, which does not exist
        until the brain is up; before that it fails with "brain hook not
        wired yet" and would burn its budget on a race it cannot win yet.

        **Split mode is deliberately skipped.** There the engine — and so the
        bridge it auto-starts — lives in the child process. This process's
        `get_bridge()` is a different, never-started instance, so supervising
        it here would see "not listening", try to start a second bridge
        against the same pairing, and fail with no brain hook. The child owns
        it; the GUI has no business reconnecting something it does not hold.
        """
        import logging as _log
        try:
            from core.brain_backend import use_split_brain
            if use_split_brain():
                _log.getLogger(__name__).info(
                    "[main_window] bridge supervision skipped — split mode, "
                    "the child process owns the bridge")
                return
            from core import bridge_subsystem
            bridge_subsystem.register(self._subsystems)
            # The engine's own setup_iter usually started it already; start()
            # is idempotent, so this just brings it under supervision.
            self._subsystems.boot(bridge_subsystem.NAME)
        except Exception as e:
            _log.getLogger(__name__).warning(
                "[main_window] bridge supervision not installed: %s", e)

    # ── Idle animation profile ───────────────────────────────────────
    _IDLE_CHECK_MS = 5_000

    def _install_idle_watchdog(self) -> None:
        """Drop the animation bus to 8 FPS when nobody is interacting.

        AERIS is designed to sit open all day, and for most of that day the
        reactor and particle field are painting 30 times a second for an
        empty chair. The bus already had AC/battery profiles — this adds the
        "is anyone watching?" axis the module docstring always promised.

        Activity is sampled with an application-wide event filter rather than
        by threading `note_activity()` through every widget: a frameless
        custom-chrome window routes input through many child widgets, and one
        missed call would strand the UI at 8 FPS while the user was actively
        typing. The filter does one monotonic assignment per input event.
        """
        import logging as _log
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
            t = QTimer(self)
            t.setInterval(self._IDLE_CHECK_MS)
            t.timeout.connect(self._check_anim_idle)
            t.start()
            self._idle_timer = t
        except Exception as e:
            _log.getLogger(__name__).warning(
                "[main_window] idle watchdog not installed: %s", e)

    _ACTIVITY_EVENTS = None      # resolved lazily; QEvent isn't imported here

    def eventFilter(self, obj, event):
        """Mark user activity, then pass every event through untouched."""
        try:
            if self._ACTIVITY_EVENTS is None:
                from PyQt5.QtCore import QEvent
                type(self)._ACTIVITY_EVENTS = frozenset((
                    QEvent.MouseButtonPress, QEvent.MouseMove,
                    QEvent.KeyPress, QEvent.Wheel, QEvent.TouchBegin,
                ))
            if event.type() in self._ACTIVITY_EVENTS:
                self._anim_bus.note_activity()
        except Exception:
            pass                 # an event filter must never raise into Qt
        return super().eventFilter(obj, event)

    def _check_anim_idle(self) -> None:
        try:
            self._anim_bus.check_idle()
        except Exception:
            pass
        # Same 5 s tick carries the subsystem reconnect sweep — see
        # `_sweep_subsystem_retries`. Kept after the animation check so a
        # reconnect that throws can never cost us the FPS drop.
        self._sweep_subsystem_retries()

    _PROACTIVE_POLL_MS = 10_000

    def _start_proactive_poller(self) -> None:
        """Split mode only: pump the child brain's proactive offers into chat.

        The child's initiative ticker pushes `event:offer` onto the bus and
        RemoteBrain buffers them, but nothing drained that buffer, so offers
        never reached the user in split mode. In-process needs no poller —
        the engine's own scheduler speaks initiatives directly, and running
        one there would surface each offer twice.
        """
        import logging as _log
        try:
            from core.brain_backend import use_split_brain
            if not use_split_brain():
                return
            if getattr(self, "_proactive_timer", None) is not None:
                return
            t = QTimer(self)
            t.setInterval(self._PROACTIVE_POLL_MS)
            t.timeout.connect(self.request_brain_poll.emit)
            t.start()
            self._proactive_timer = t
            _log.getLogger(__name__).info(
                "[main_window] proactive poller started (%d ms)",
                self._PROACTIVE_POLL_MS)
        except Exception as e:
            _log.getLogger(__name__).warning(
                "[main_window] proactive poller not started: %s", e)

    def _on_brain_proactive(self, text: str, offer: dict) -> None:
        """A proactive offer arrived from the isolated brain — surface it.

        Deliberately quieter than a reply to a command: the user did not ask
        for this, so it must never stomp a turn in flight. If AERIS is busy
        thinking or speaking, the offer is dropped rather than queued —
        `initiative_engine` will raise it again on its next tick, and a stale
        nudge arriving after the moment has passed is worse than none.
        """
        import logging as _log
        if not text:
            return
        state = getattr(self, "_current_state", "IDLE")
        if state != "IDLE":
            _log.getLogger(__name__).info(
                "[main_window] proactive offer dropped (state=%s): %r",
                state, text[:60])
            return
        try:
            self.logs.add_log("ACT", f"Proactive: {text[:60]}")
            self.chat.add_message("ai", text, tag=("proactive", J.CYAN))
            self.request_speak.emit(text)
        except Exception as e:
            _log.getLogger(__name__).warning(
                "[main_window] surfacing proactive offer failed: %s", e)

    def _on_use_phrase(self, phrase: str) -> None:
        """Ability row clicked → phrase into the chat input + focus there."""
        try:
            self.chat.prefill(phrase)
            self._right.switch_tab("chat")
        except Exception:
            pass

    def _on_user_send(self, text: str):
        """Common path: chat-typed text OR suggestion-chip OR voice-captured."""
        if not text.strip():
            return
        import threading as _th, logging as _lg
        # GUI-thread guard: any widget/QTimer touch off the GUI thread is a
        # hard Qt crash. If we got here from another thread, bounce back.
        from PyQt5.QtCore import QThread as _QT
        _cur = _th.current_thread().name
        if _QT.currentThread() is not self.thread():
            _lg.getLogger(__name__).warning(
                "[trace] _on_user_send OFF-GUI-THREAD (%s) → re-marshal: %r",
                _cur, text[:40])
            self._gui_cmd.emit(text)
            return
        _lg.getLogger(__name__).info(
            "[trace] _on_user_send thread=%s text=%r", _cur, text[:60])
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
        # Arm the watchdog so PROCESSING can never wedge the UI.
        try:
            from core.voice_gate import processing_timeout_s
            self._proc_watchdog.start(int(processing_timeout_s(text) * 1000))
        except Exception:
            self._proc_watchdog.start(12000)
        self.logs.add_log("NLU", f'Input: "{text[:48]}"', highlight=True)
        self.request_brain_proc.emit(text)

    @pyqtSlot(dict)
    def _on_phone_status_gui(self, status: dict) -> None:
        """Show a phone status reply (battery etc.) in the chat."""
        try:
            # Reused channel for the async phone-screen LLM answer.
            if "_screen_answer" in status:
                ans = status["_screen_answer"]
                self.chat.add_message("ai", ans, tag=("phone_screen", J.CYAN))
                self.request_speak.emit(ans)
                return
            batt = status.get("battery")
            if batt is not None and batt >= 0:
                charging = " (charging)" if status.get("charging") else ""
                msg = f"📱 Phone battery: {batt}%{charging}"
            else:
                msg = f"📱 Phone status: {status}"
            self.chat.add_message("ai", msg, tag=("phone", J.CYAN))
            self.request_speak.emit(msg.replace("📱", "").strip())
        except Exception:
            pass

    @pyqtSlot(bytes, str)
    def _on_phone_screen_gui(self, jpeg: bytes, caption: str) -> None:
        """Phone sent a screen frame. During a LIVE stream many frames arrive,
        so show them in a dedicated live window (updated in place) rather than
        spamming the chat. If a question was pending (one-shot ask), OCR +
        answer it off the GUI thread."""
        # Live window — open on first frame, update on every subsequent one.
        try:
            first = self._phone_live is None
            self._show_phone_live(jpeg)
            if first:
                self.chat.add_message(
                    "ai", "📱 Phone screen live — window khul gayi. "
                          "Rokne ke liye 'screen share band karo'.",
                    tag=("phone_screen", J.CYAN))
        except Exception:
            pass

        from core import phone_screen
        q = phone_screen.pop_pending_question()
        if not q:
            return

        def _work():
            try:
                ans = phone_screen.analyze(jpeg, q)
            except Exception as e:
                ans = f"Phone screen samajhne mein error: {e}"
            # marshal the answer back onto the GUI thread as a chat reply.
            self._phone_status.emit({"_screen_answer": ans})

        import threading
        threading.Thread(target=_work, name="PhoneScreenLLM",
                         daemon=True).start()

    def _show_phone_live(self, jpeg: bytes) -> None:
        """Build (once) + update the phone live-view window with a frame."""
        from PyQt5.QtGui import QPixmap
        if self._phone_live is None:
            self._phone_live = _PhoneLiveWindow(self)
            self._phone_live.show()
        pix = QPixmap()
        pix.loadFromData(jpeg, "JPEG")
        self._phone_live.set_frame(pix)

    def _on_phone_screen_np_gui(self, img) -> None:
        """Phase 2: raw BGR frame from phone→laptop WebRTC. Keep only the latest
        (coalesce) so a slow repaint can't build a backlog, then flush once."""
        self._phone_pending_np = img
        if not self._phone_repaint_scheduled:
            self._phone_repaint_scheduled = True
            QTimer.singleShot(0, self._flush_phone_np)

    def _flush_phone_np(self) -> None:
        self._phone_repaint_scheduled = False
        img = self._phone_pending_np
        self._phone_pending_np = None
        if img is None:
            return
        from PyQt5.QtGui import QImage, QPixmap
        import numpy as np
        try:
            img = np.ascontiguousarray(img)
            h, w = img.shape[:2]
            fmt = getattr(QImage, "Format_BGR888", None)
            if fmt is not None:
                qimg = QImage(img.data, w, h, 3 * w, fmt)
            else:  # older Qt without BGR888 → swap to RGB
                qimg = QImage(img[:, :, ::-1].copy().data, w, h, 3 * w,
                              QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg.copy())  # copy: detach from img buffer
        except Exception:
            return
        first = self._phone_live is None
        if first:
            self._phone_live = _PhoneLiveWindow(self)
            self._phone_live.show()
            self.chat.add_message(
                "ai", "📱 Phone screen live (WebRTC — smooth). "
                      "Rokne ke liye 'screen share band karo'.",
                tag=("phone_screen", J.CYAN))
        self._phone_live.set_frame(pix)

    @pyqtSlot()
    def _close_phone_live(self) -> None:
        """Close the live window + make sure the phone stream is stopped."""
        try:
            from core.cloud_bridge import get_bridge
            get_bridge().stop_phone_stream()
        except Exception:
            pass
        if self._phone_live is not None:
            try:
                self._phone_live.close()
            except Exception:
                pass
            self._phone_live = None

    @pyqtSlot()
    def _on_phone_paired_gui(self) -> None:
        """Phone connected with the fresh key → auto-close the QR dialog."""
        dlg = getattr(self, "_pair_dialog", None)
        if dlg is not None:
            try:
                dlg.accept()
            except Exception:
                try:
                    dlg.close()
                except Exception:
                    pass
            self._pair_dialog = None
            try:
                self.chat.add_message("ai", "📱 Phone pair ho gaya ✅",
                                      tag=("phone", J.CYAN))
            except Exception:
                pass

    @pyqtSlot(str, str)
    def _do_show_pair_dialog(self, qr_path: str, pid8: str) -> None:
        """Build + show the pairing popup — always on the GUI thread (this
        slot is invoked via the _show_pair_qr queued signal)."""
        import threading as _th, logging as _lg
        _lg.getLogger(__name__).info(
            "[trace] _do_show_pair_dialog thread=%s qr=%s",
            _th.current_thread().name, qr_path)
        try:
            from ui.jarvis_v31.pair_dialog import PairDialog
            self._pair_dialog = PairDialog.show_for(qr_path, pid8, self)
            _lg.getLogger(__name__).info("[trace] pair dialog shown OK")
            self.logs.add_log("BRG", "Pairing QR shown · scan with AERIS Remote",
                              highlight=True)
            self.chat.add_message(
                "ai", "Pairing QR khul gaya 📱 — AERIS Remote app se scan karo.",
                tag=("bridge_pair", J.CYAN))
        except Exception as e:
            self.logs.add_log("ERR", f"pair dialog failed: {e}", highlight=True)
            try:
                self.chat.add_message("ai", f"QR popup nahi khula: {e}")
            except Exception:
                pass

    def _on_stop_requested(self):
        self._cancelled = True
        self._pending_voice = None
        self.chat.cancel_stream()
        self._set_state("IDLE")
        self.logs.add_log("SYS", "Request cancelled by user · awaiting brain to drain")

    def _on_brain_responded(self, reply: str, meta: dict):
        import threading as _th, logging as _lg
        from PyQt5.QtCore import QThread as _QT
        _lg.getLogger(__name__).info(
            "[trace] _on_brain_responded thread=%s on_gui=%s reply=%r",
            _th.current_thread().name,
            _QT.currentThread() is self.thread(), (reply or "")[:50])
        self._proc_watchdog.stop()        # brain answered — disarm watchdog
        if self._cancelled:
            self._cancelled = False
            return
        # Sentinel from the ``clear_chat`` skill — wipe the chat panel
        # immediately and skip the normal speak / log flow so the user
        # sees nothing left behind.
        if reply and reply.strip() == "[clear_chat]":
            try:
                self.chat.clear_history()
            except Exception as e:
                self.logs.add_log("ERR", f"clear_chat failed: {e}", highlight=True)
            self._set_state("IDLE")
            return

        # Sentinel from ``bridge_pair`` — show the QR pairing popup in-app
        # (on the GUI thread) instead of the OS image viewer.
        # Format: [pair_qr]<qr_path>|<pid8>
        if reply and reply.startswith("[pair_qr]"):
            payload = reply[len("[pair_qr]"):]
            qr_path, _, pid8 = payload.partition("|")
            # Marshal to the GUI thread via signal — NEVER build the dialog
            # inline (that crashed Qt from the worker-thread reply path).
            self._show_pair_qr.emit(qr_path, pid8)
            # A pairing is exactly the precondition whose absence put the
            # bridge in DISABLED ("Not paired yet"). Retries skip DISABLED by
            # design, so without this the bridge would stay off until the next
            # restart despite the user having just paired. `pair()` already
            # rotated the key and stopped the old listener; rearm starts the
            # new one under supervision.
            try:
                from core import bridge_subsystem
                bridge_subsystem.rearm(self._subsystems)
            except Exception:
                pass
            self._set_state("IDLE")
            return

        # Sentinel from ``phone_send_file`` — pick a file (GUI thread) + send.
        if reply and reply.strip() == "[pick_file_phone]":
            self._set_state("IDLE")
            try:
                from PyQt5.QtWidgets import QFileDialog
                path, _ = QFileDialog.getOpenFileName(
                    self, "Phone pe bhejne ke liye file chuno")
                if path:
                    self.chat.add_message("ai", f"📤 Bhej raha hoon: {path}",
                                          tag=("phone", J.CYAN))
                    import threading
                    def _snd():
                        try:
                            from core.cloud_bridge import get_bridge
                            ok, msg = get_bridge().send_file_to_phone(path)
                            self._phone_status.emit(
                                {"_screen_answer": ("📤 " + msg) if ok
                                 else ("File bhejne mein dikkat: " + msg)})
                        except Exception as e:
                            self._phone_status.emit(
                                {"_screen_answer": f"File send error: {e}"})
                    threading.Thread(target=_snd, name="FileSend",
                                     daemon=True).start()
            except Exception as e:
                self.logs.add_log("ERR", f"file pick failed: {e}",
                                  highlight=True)
            return

        # Sentinel from the ``repeat_last`` skill — re-fire the user-send
        # path with the previous command so it goes through the full brain
        # pipeline again. We do this on a tiny QTimer so the current
        # responded-emit can finish before the next one starts (prevents
        # a re-entrancy loop if repeat_last itself is somehow re-invoked).
        if reply and reply.startswith("[repeat:") and reply.endswith("]"):
            cmd = reply[len("[repeat:"):-1]
            self.logs.add_log("SYS", f"Repeating: {cmd!r}")
            self._set_state("IDLE")
            QTimer.singleShot(80, lambda: self._on_user_send(cmd))
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
        self._proc_watchdog.stop()
        import logging as _log
        _log.getLogger(__name__).error("[main_window] _on_brain_error: %s", msg)
        self.logs.add_log("ERR", msg, highlight=True)
        self.chat.finish_boot()
        # Even on init failure, resume animations so the user isn't
        # stuck staring at a half-frozen reactor.
        self._anim_bus.resume()
        self._set_state("IDLE")
        # Even if the brain failed to init, don't strand TTS/voice — a user
        # may still want spoken feedback / mic while we retry or degrade.
        self._kick_secondary_init()

    def _on_processing_timeout(self):
        """Watchdog fired — the brain never answered. Force back to LISTENING
        so voice is never stranded in PROCESSING. The slow request may still
        complete later; ``_on_brain_responded`` handles that gracefully (it
        just stops an already-stopped timer and renders the reply)."""
        if self._current_state != "PROCESSING":
            return
        self.logs.add_log("ERR", "Processing timed out — back to listening.",
                          highlight=True)
        # Snap straight back to listening and gently tell the user.
        self._set_state("IDLE")
        try:
            self.chat.add_message("ai", "Thoda time lag gaya, sir — phir se boliye.")
        except Exception:
            pass
        # If something was captured while we were wedged, handle it now.
        if self._pending_voice:
            pending = self._pending_voice
            self._pending_voice = None
            QTimer.singleShot(150, lambda: self._on_user_send(pending))

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

        # Keep the registry in step with the user's intent, so an automatic
        # reconnect never re-opens a mic they just turned off, and turning it
        # back on clears any "failed" verdict from earlier in the session.
        if self._voice_state == "STOPPED":
            self.logs.add_log("MIC", "Voice mode ON · continuous listening started")
            try:
                self._subsystems.enable("voice")
                self._subsystems.reset("voice")   # fresh retry budget
            except Exception:
                pass
            self.request_voice_start.emit()
        else:
            self.logs.add_log("MIC", "Voice mode OFF · mic deactivated")
            try:
                self._subsystems.mark_disabled("voice", "mic toggled off")
            except Exception:
                pass
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
        import threading as _th, logging as _lg
        from PyQt5.QtCore import QThread as _QT
        if _QT.currentThread() is not self.thread():
            _lg.getLogger(__name__).warning(
                "[trace] _on_voice_captured OFF-GUI-THREAD (%s) → re-marshal",
                _th.current_thread().name)
            self._gui_voice_cap.emit(text)
            return
        # Drop noise / disfluencies so a half-heard blip never flips us into
        # PROCESSING — the mic just keeps streaming (LISTENING). This is the
        # "mic na sun paye to processing me chala jata tha" fix.
        try:
            from core.voice_gate import is_meaningful_capture
            if not is_meaningful_capture(text):
                self.logs.add_log("MIC", f'Ignored (noise): "{text[:32]}"')
                return
        except Exception:
            pass
        self.logs.add_log("MIC", f'Captured: "{text[:48]}"', highlight=True)
        if self._current_state in ("PROCESSING", "SPEAKING"):
            # Brain is busy — hold the last captured phrase; process when idle
            self._pending_voice = text
            return
        self._on_user_send(text)

    def _on_voice_error(self, msg: str):
        self.logs.add_log("ERR", msg, highlight=True)
        # Hand it to the registry: DEGRADED (not FAILED — the worker and its
        # thread are still alive), which schedules a reconnect if voice has
        # budget left. Before this, a mic that went away mid-session stayed
        # gone until the app was restarted.
        try:
            self._subsystems.mark_degraded("voice", msg)
        except Exception:
            pass

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
    def _open_command_palette(self) -> None:
        """Slot for the Ctrl+Shift+P shortcut — opens the palette on the
        main Qt thread, where QApplication already exists."""
        try:
            from ui.command_palette import open_command_palette
            open_command_palette(parent=self)
        except Exception as e:
            self.logs.add_log("ERR", f"palette open failed: {e}", highlight=True)

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
            # reflect the freshly-loaded engine state. `peek` is the
            # never-constructs accessor — this comment always said "if it
            # exists", and with the lazy stack that is now literally true:
            # a user who has not opened Routines should not pay to build it
            # just so we can refresh something they cannot see. It reads
            # fresh state when they do open it.
            try:
                panel = self._right.peek("routines")
                if panel is not None:
                    panel.refresh()
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
        #
        # NEVER call get_gesture_engine() here — constructing GestureEngine
        # imports mediapipe → tensorflow → keras → sklearn → scipy, an
        # ~18 s GUI-thread freeze (measured with py-spy). Instead PEEK for
        # an existing engine on a light poll and attach the listener the
        # moment "gesture mode on" (worker thread) has built it.
        self._gesture_recognized.connect(self._on_gesture_for_gui)
        self._gesture_listener_attached = False
        self._gesture_attach_timer = QTimer(self)
        self._gesture_attach_timer.timeout.connect(self._try_attach_gesture_listener)
        self._gesture_attach_timer.start(5000)
        self._try_attach_gesture_listener()

    def _try_attach_gesture_listener(self) -> None:
        """Attach the palette-toggle listener IF the gesture engine already
        exists (peek only — never construct). Stops polling once attached."""
        if self._gesture_listener_attached:
            self._gesture_attach_timer.stop()
            return
        try:
            from core import gesture_engine as _gem
            eng = _gem._DEFAULT_ENGINE
            if eng is not None:
                eng.add_listener(self._gesture_recognized.emit)
                self._gesture_listener_attached = True
                self._gesture_attach_timer.stop()
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
                return
        except Exception:
            # Import/setup blew up. Raise so the registry records it and
            # spends a retry — see the _RETRY table in __init__.
            raise
        # Bind failed (port 8765 busy — usually a previous AERIS still
        # draining). This used to be terminal: one lost race and /health was
        # offline for the whole session. Raising hands it to the registry,
        # which retries at 5s/10s/20s — long enough for the old process to
        # let the port go.
        raise OSError("health server bind failed (port 8765 busy)")

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

        # Real shutdown path. Hide the window FIRST — the user perceives
        # the app as closed instantly; thread joins + shutdown hooks then
        # drain invisibly in the last few hundred ms of process life.
        self.hide()
        try:
            QApplication.processEvents()
        except Exception:
            pass
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
                th.wait(800)
        # Fire the shutdown coordinator AFTER threads are joined so its
        # hooks (ResourceMonitor, feedback flush, etc.) see a quiesced
        # process and aren't racing live workers for the GIL.
        try:
            from core.shutdown import fire as _shutdown_fire
            _shutdown_fire(reason="closeEvent")
        except Exception:
            pass
        super().closeEvent(e)


def launch(splash=None, boot_t0=None):
    """Standalone launcher (also used by run_gui.py).

    Instant path (default, ``splash=None``)
    ---------------------------------------
    The window is constructed lean (no heavy imports, subsystem installs
    staged on QTimer ticks) and SHOWN immediately. The brain + ML stack
    load on the worker thread while the reactor pulses at 15 FPS and the
    chat boot bubble streams progress. ``boot_t0`` (a perf_counter value
    from process start) lets us log the true launch→visible latency.

    Classic splash-first path (``splash`` supplied)
    -----------------------------------------------
    Kept for AERIS_CLASSIC_BOOT=1: splash stays up until the brain is
    ready, then the fully-loaded window replaces it.
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
        # Instant path — show immediately, everything heavy loads after.
        win.show()
        if boot_t0 is not None:
            try:
                from core.log_setup import event as _event
                _event("window_visible",
                       elapsed_ms=round((time.perf_counter() - boot_t0) * 1000, 1))
                # Event-loop latency probes: each logs how late it fired
                # vs its schedule. If actual >> scheduled, something is
                # blocking the GUI thread at loop startup.
                _probe_t0 = time.perf_counter()
                def _probe(d):
                    _event("loop_probe", scheduled_ms=d,
                           actual_ms=round((time.perf_counter() - _probe_t0) * 1000, 1))
                for _d in (0, 200, 500, 1000, 2000):
                    QTimer.singleShot(_d, lambda d=_d: _probe(d))
            except Exception:
                pass
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
