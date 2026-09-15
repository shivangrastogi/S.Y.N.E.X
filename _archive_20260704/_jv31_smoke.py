"""Smoke launcher for the JARVIS v3.1 chunks-in-progress.

Run with:  python _jv31_smoke.py
"""
from __future__ import annotations

import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from ui.jarvis_v31.floating_dock import FloatingDock
from ui.jarvis_v31.logs_bar import LogsBar
from ui.jarvis_v31.reactor import (
    ParticleField, ReactorRings, ReactorStateText, StateSwitcher,
)
from ui.jarvis_v31.title_bar import TitleBar
from ui.jarvis_v31.tokens import J
from ui.jarvis_v31.wiring_system import REACTOR_CX, REACTOR_CY, WiringSystem


def _build():
    win = QMainWindow()
    win.setWindowTitle("JARVIS v3.1 smoke")
    win.resize(1440, 900)
    win.setWindowFlag(Qt.FramelessWindowHint, True)
    win.setStyleSheet(f"QMainWindow {{ background: {J.BG.name()}; }}")

    central = QWidget()
    central.setStyleSheet(f"background: {J.BG.name()};")
    root = QVBoxLayout(central)
    root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

    bar = TitleBar()
    root.addWidget(bar)

    body = QWidget()
    body.setStyleSheet(f"background: {J.BG.name()};")
    root.addWidget(body, stretch=1)

    # ── Particle field background ───────────────────────────────────
    particles = ParticleField(count=22, parent=body)
    # ── Wiring system (1080x820 grid; positioned to center the reactor) ──
    wiring = WiringSystem(parent=body)
    # ── Reactor (460x460) — sits ON TOP of the wiring grid ──────────
    reactor = ReactorRings(parent=body)
    reactor.raise_()
    # ── State text + switcher anchored below the reactor ────────────
    state_text = ReactorStateText(parent=body)
    state_switcher = StateSwitcher(parent=body)

    def _layout_center():
        # Pin the wiring grid centered horizontally; reactor center anchors
        # at REACTOR_CX/REACTOR_CY inside the grid.
        gx = max(0, (body.width() - wiring.width()) // 2)
        gy = max(0, (body.height() - wiring.height()) // 2)
        wiring.move(gx, gy)
        particles.setGeometry(0, 0, body.width(), body.height())
        # Reactor center should land at (gx + REACTOR_CX, gy + REACTOR_CY).
        rcx = gx + REACTOR_CX
        rcy = gy + REACTOR_CY
        reactor.move(rcx - reactor.width() // 2, rcy - reactor.height() // 2)
        reactor.raise_()
        # State text below reactor
        st_w = state_text.sizeHint().width() or 460
        state_text.setFixedWidth(520)
        state_text.move(rcx - 260, rcy + reactor.height() // 2 + 12)
        # Switcher below state text
        sw_y = state_text.y() + state_text.sizeHint().height() + 6
        sw_w = state_switcher.sizeHint().width() or 360
        state_switcher.setFixedWidth(420)
        state_switcher.move(rcx - 210, sw_y)
        state_switcher.raise_()
        # Keep the dock on top of the wiring layer.
        dock.raise_()
        _reposition_dock()

    body.resizeEvent = lambda e: _layout_center()
    QTimer.singleShot(0, _layout_center)

    logs = LogsBar()
    root.addWidget(logs)

    win.setCentralWidget(central)

    # ── Floating dock is an OVERLAY (parent = body, absolute position) ──
    dock = FloatingDock(parent=body)
    dock.show()

    def _reposition_dock():
        # 12px from left edge, vertically centered inside `body`
        h = dock.sizeHint().height() or 480
        dock.move(12, max(8, (body.height() - h) // 2))

    # Reposition the dock when its width animates
    dock._anim.valueChanged.connect(lambda *_: _reposition_dock())
    # The body.resizeEvent gets reassigned below to layout the center; that
    # callback also calls _reposition_dock() at the end.
    QTimer.singleShot(0, _reposition_dock)

    # ── Wire window controls ───────────────────────────────────────
    bar.close_clicked.connect(win.close)
    bar.minimize_clicked.connect(win.showMinimized)
    bar.maximize_clicked.connect(
        lambda: win.showNormal() if win.isMaximized() else win.showMaximized()
    )

    # ── Drag-to-move ──────────────────────────────────────────────
    drag = {"start": None, "win": None}
    def _ds(p): drag["start"] = p; drag["win"] = win.frameGeometry().topLeft()
    def _dm(p):
        if drag["start"] is None: return
        win.move(drag["win"] + (p - drag["start"]))
    bar.drag_start.connect(_ds); bar.drag_move.connect(_dm)

    # ── Cycle state pill + push log lines so we can see motion ─────
    states = ["IDLE", "LISTENING", "PROCESSING", "SPEAKING"]
    counter = {"i": 0}
    log_for_state = {
        "IDLE":       ("ACT", "Response delivered. Session idle."),
        "LISTENING":  ("MIC", "Voice stream active. Listening for input…"),
        "PROCESSING": ("NLU", "Semantic parse + intent classification…"),
        "SPEAKING":   ("TTS", "Streaming response… 142ms"),
    }
    def _apply_state(s):
        bar.pill.set_state(s)
        reactor.set_state(s)
        state_text.set_state(s)
        state_switcher.set_active(s)
        wiring.set_state(s)
        if s in ("PROCESSING", "LISTENING"):
            state_text.set_last_input("chrome kholo aur weather batao")

    def _cycle():
        counter["i"] = (counter["i"] + 1) % len(states)
        s = states[counter["i"]]
        _apply_state(s)
        if s in log_for_state:
            t, txt = log_for_state[s]
            logs.add_log(t, txt, highlight=(s != "IDLE"))

    # Manual override via the state-switcher buttons
    state_switcher.state_picked.connect(_apply_state)

    # Seed the log feed with boot logs
    for typ, txt, hl in [
        ("SYS", "Neural core online · wiring grid initialized", False),
        ("NLU", "301 intent patterns loaded · 21 classes active", True),
        ("SYS", "9/9 system nodes connected via circuit layer", False),
        ("SYS", "All modules nominal · JARVIS v3.1 ready", False),
    ]:
        logs.add_log(typ, txt, hl)

    t = QTimer(win); t.timeout.connect(_cycle); t.start(2000)

    return win


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = _build()
    w.show()
    sys.exit(app.exec_())
