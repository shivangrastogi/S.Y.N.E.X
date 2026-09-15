"""BootScreen — optional in-app boot/identity screen (jv3-boot.jsx).

A full-window centred ArcReactor with a progress bar and rolling status line.
The repo entry point (`run_aeris_v6.py`) already shows the lightweight splash
during heavy imports, so this is provided as a reusable component for callers
that want the in-window cinematic boot before revealing the main UI.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ui.aeris_v6.reactor import ArcReactor
from ui.aeris_v6.tokens import W_BOLD, col, font_mono, font_ui, rgba_str


class BootScreen(QWidget):
    completed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{rgba_str('bg',1)};")
        root = QVBoxLayout(self); root.setAlignment(Qt.AlignCenter); root.setSpacing(18)

        self._reactor = ArcReactor(size=300)
        self._reactor.set_state("PROCESSING")
        wrap = QWidget(); from PyQt5.QtWidgets import QHBoxLayout
        wl = QHBoxLayout(wrap); wl.addStretch(1); wl.addWidget(self._reactor); wl.addStretch(1)
        root.addWidget(wrap)

        brand = QLabel("A.E.R.I.S"); brand.setAlignment(Qt.AlignCenter)
        brand.setFont(font_ui(26, W_BOLD, 6))
        brand.setStyleSheet(f"color:{rgba_str('cyan',1)};background:transparent;")
        root.addWidget(brand)

        self._status = QLabel("Initialising neural core…"); self._status.setAlignment(Qt.AlignCenter)
        self._status.setFont(font_mono(10))
        self._status.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        root.addWidget(self._status)

        self._bar_bg = QFrame(); self._bar_bg.setFixedSize(280, 4)
        self._bar_bg.setStyleSheet("background:rgba(255,255,255,0.08);border-radius:2px;")
        self._bar = QFrame(self._bar_bg); self._bar.setFixedSize(0, 4)
        self._bar.setStyleSheet(f"background:{rgba_str('cyan',1)};border-radius:2px;")
        from PyQt5.QtWidgets import QHBoxLayout as _H
        brow = _H(); brow.addStretch(1); brow.addWidget(self._bar_bg); brow.addStretch(1)
        root.addLayout(brow)

    def set_progress(self, pct: int, status: str = None):
        pct = max(0, min(100, pct))
        self._bar.setFixedSize(int(280 * pct / 100), 4)
        if status:
            self._status.setText(status)
        if pct >= 100:
            self.completed.emit()
