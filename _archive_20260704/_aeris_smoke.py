"""Tiny standalone launcher for whatever AERIS chunk is currently being built.

Each chunk extends `_build_demo_window()` to add the new component(s). Run
with: python _aeris_smoke.py
"""
from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from ui.aeris_v4.arc_reactor import ArcReactor, ReactorStateText
from ui.aeris_v4.chat_panel import ChatPanel
from ui.aeris_v4.logs_panel import SystemLogsPanel
from ui.aeris_v4.sidebar import Sidebar
from ui.aeris_v4.theme import C
from ui.aeris_v4.title_bar import TitleBar


def _build_demo_window() -> QMainWindow:
    win = QMainWindow()
    win.setWindowTitle("AERIS smoke")
    win.resize(1440, 900)
    win.setWindowFlag(Qt.FramelessWindowHint, True)
    win.setStyleSheet(f"QMainWindow {{ background: {C.BG.name()}; }}")

    central = QWidget()
    root = QVBoxLayout(central)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    bar = TitleBar()
    root.addWidget(bar)

    body = QWidget()
    body_lay = QHBoxLayout(body)
    body_lay.setContentsMargins(0, 0, 0, 0)
    body_lay.setSpacing(0)

    sidebar = Sidebar()
    body_lay.addWidget(sidebar)

    # Center column: reactor + state text, vertically centered.
    center = QWidget()
    center_lay = QVBoxLayout(center)
    center_lay.setContentsMargins(0, 40, 0, 20)
    center_lay.setSpacing(28)
    center_lay.setAlignment(Qt.AlignHCenter)

    reactor = ArcReactor()
    state_text = ReactorStateText()

    center_lay.addStretch(1)
    center_lay.addWidget(reactor, alignment=Qt.AlignHCenter)
    center_lay.addWidget(state_text, alignment=Qt.AlignHCenter)
    center_lay.addStretch(2)

    # Bottom logs panel (collapsible; pinned to the bottom of the center column).
    logs = SystemLogsPanel()
    center_lay.addWidget(logs)
    # Seed with the boot logs from BOOT_LOGS in aeris-app.jsx.
    for typ, txt, hl in [
        ("SYS", "AERIS core initialized. Loading semantic engine…", False),
        ("SYS", "Semantic engine v3.1 online. 301 patterns loaded.", False),
        ("NLU", "Intent classifier ready. 21 intent classes active.", True),
        ("MEM", "Memory index loaded. 0 prior sessions found.", False),
        ("SYS", "All modules nominal. Awaiting user input.", False),
    ]:
        logs.add_log(typ, txt, hl)

    body_lay.addWidget(center, stretch=1)

    chat = ChatPanel()
    body_lay.addWidget(chat)

    root.addWidget(body)

    # Hamburger toggles the sidebar collapse.
    bar.sidebar_toggled.connect(sidebar.toggle)

    central.setStyleSheet(f"background: {C.BG.name()};")
    win.setCentralWidget(central)

    # Wire the window-control signals so close actually closes during smoke.
    bar.close_clicked.connect(win.close)
    bar.minimize_clicked.connect(win.showMinimized)
    bar.maximize_clicked.connect(
        lambda: win.showNormal() if win.isMaximized() else win.showMaximized()
    )

    # Cycle the state pill every 2s so we can see the color transitions.
    from PyQt5.QtCore import QTimer
    states = ["IDLE", "LISTENING", "PROCESSING", "SPEAKING", "ERROR"]
    counter = {"i": 0}

    def _cycle():
        counter["i"] = (counter["i"] + 1) % len(states)
        s = states[counter["i"]]
        bar.pill.set_state(s)
        reactor.set_state(s)
        state_text.set_state(s)
        chat.set_state(s)
        # Echo a fake user input so PROCESSING/LISTENING sub-text has content
        if s in ("PROCESSING", "LISTENING"):
            state_text.set_last_input("chrome kholo aur weather batao")
        # Demo the streaming bubble when entering SPEAKING.
        if s == "SPEAKING":
            chat.stream_message(
                "Chrome khol raha hoon. Weather report bhi dikha deta hoon ek second.",
                tag=("open_app • 96.4% • 142ms", C.GREEN),
                speed_ms=22,
            )
        # Push a representative log line for each state transition.
        log_for_state = {
            "IDLE":       ("ACT", "Response delivered. Session idle."),
            "LISTENING":  ("MIC", "Voice stream active. Listening for input…"),
            "PROCESSING": ("NLU", "Running semantic parse + intent classification…"),
            "SPEAKING":   ("TTS", "Streaming response… latency 142ms"),
            "ERROR":      ("ERR", "Speech recognition failed: timeout"),
        }
        if s in log_for_state:
            t, txt = log_for_state[s]
            logs.add_log(t, txt, highlight=(s != "IDLE"))

    # Wire chat send -> append a fake user message echo + jump to PROCESSING
    def _on_send(text: str):
        chat.set_state("PROCESSING")
        bar.pill.set_state("PROCESSING")
        reactor.set_state("PROCESSING")
        state_text.set_state("PROCESSING")
        state_text.set_last_input(text)

    chat.send_text.connect(_on_send)

    t = QTimer(win)
    t.timeout.connect(_cycle)
    t.start(2000)

    # Drag-to-move wiring (frameless windows need this).
    drag_origin = {"start": None, "win_pos": None}

    def _drag_start(global_pos):
        drag_origin["start"] = global_pos
        drag_origin["win_pos"] = win.frameGeometry().topLeft()

    def _drag_move(global_pos):
        if drag_origin["start"] is None:
            return
        delta = global_pos - drag_origin["start"]
        win.move(drag_origin["win_pos"] + delta)

    bar.drag_start.connect(_drag_start)
    bar.drag_move.connect(_drag_move)

    return win


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = _build_demo_window()
    w.show()
    sys.exit(app.exec_())
