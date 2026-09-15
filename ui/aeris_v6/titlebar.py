"""AppTitleBar — frameless drag bar with telemetry + window controls.

Ports ``AppTitleBar`` from ``jv5-app.jsx``: brand on the left, a dense row of
live telemetry pills in the centre, and a state pill + clock + ⌘K button +
min/max/close on the right. Dragging anywhere on the empty bar moves the
frameless window.
"""
from __future__ import annotations

from PyQt5.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ui.aeris_v6.tokens import (
    J, W_BOLD, W_SEMIBOLD, ca, col, font_mono, font_ui, rgba_str, JSTATES,
)
from ui.aeris_v6.widgets import StatusDot, paint_icon, vline


class _Pill(QWidget):
    def __init__(self, label, value, color_key, pulse=False, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(5)
        self._dot = StatusDot(col(color_key), size=4)
        lay.addWidget(self._dot)
        lk = QLabel(label); lk.setFont(font_mono(8, W_BOLD, 1.2))
        lk.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        lay.addWidget(lk)
        self._val = QLabel(value); self._val.setFont(font_mono(9, W_SEMIBOLD))
        self._val.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        lay.addWidget(self._val)

    def set_value(self, v: str):
        self._val.setText(v)

    def set_color(self, color_key: str):
        try:
            self._dot.set_color(col(color_key))
        except Exception:
            pass


class _WindowControls(QWidget):
    minimize = pyqtSignal()
    maximize = pyqtSignal()
    close = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(4)
        for name, sig, hover in (
            ("minimize", self.minimize, "cyan"),
            ("maximize", self.maximize, "cyan"),
            ("close", self.close, "red"),
        ):
            lay.addWidget(_CtrlBtn(name, sig, hover))


class _CtrlBtn(QWidget):
    def __init__(self, name, sig, hover_key, parent=None):
        super().__init__(parent)
        self._name = name
        self._sig = sig
        self._hover = False
        self._hover_key = hover_key
        self.setFixedSize(26, 22)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, _e): self._hover = True; self.update()
    def leaveEvent(self, _e): self._hover = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._sig.emit()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        if self._hover:
            p.setBrush(ca(self._hover_key, 0.16)); p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 6, 6)
        c = col(self._hover_key) if self._hover else col("textMut")
        side = 12
        x = (self.width() - side) / 2; y = (self.height() - side) / 2
        paint_icon(p, self._name, QRectF(x, y, side, side), c, stroke=1.3)
        p.end()


class AppTitleBar(QFrame):
    minimizeRequested = pyqtSignal()
    maximizeRequested = pyqtSignal()
    closeRequested = pyqtSignal()
    cmdkRequested = pyqtSignal()

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._win = window
        self._drag_pos = None
        self.setFixedHeight(40)
        self.setStyleSheet(
            f"AppTitleBar{{background:{rgba_str((8,12,22), 0.96)};"
            f"border-bottom:1px solid {rgba_str('border', 0.7)};}}"
        )
        lay = QHBoxLayout(self); lay.setContentsMargins(16, 0, 10, 0); lay.setSpacing(10)

        # brand
        lay.addWidget(StatusDot(col("cyan"), size=8))
        brand = QLabel("A.E.R.I.S"); brand.setFont(font_ui(12, W_BOLD, 2))
        brand.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
        lay.addWidget(brand)
        ver = QLabel("v6"); ver.setFont(font_mono(9))
        ver.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        lay.addWidget(ver)
        lay.addWidget(vline(14))
        machine = QLabel("Shivang's Machine"); machine.setFont(font_mono(9))
        machine.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        lay.addWidget(machine)

        lay.addStretch(1)

        # center telemetry
        self.pill_model = _Pill("MODEL", "Opus 4.8", "cyan", pulse=True)
        self.pill_gpu = _Pill("GPU", "18%", "purple")
        self.pill_mem = _Pill("MEM", "4.2/16G", "cyan")
        self.pill_net = _Pill("NET", "↓1.4 ↑0.3", "green")
        self.pill_wake = _Pill("WAKE", "ARMED", "amber", pulse=True)
        self.pill_presence = _Pill("PRESENCE", "—", "cyan")
        for w in (self.pill_model, self.pill_gpu, self.pill_mem, self.pill_net,
                  self.pill_wake, self.pill_presence):
            lay.addWidget(w); lay.addWidget(vline(10))

        lay.addStretch(1)

        # state pill
        self._state_frame = QFrame()
        sf = QHBoxLayout(self._state_frame); sf.setContentsMargins(8, 3, 10, 3); sf.setSpacing(6)
        self._state_dot = StatusDot(col("cyan"), size=5)
        self._state_lbl = QLabel("STANDBY"); self._state_lbl.setFont(font_ui(8, W_BOLD, 1.5))
        sf.addWidget(self._state_dot); sf.addWidget(self._state_lbl)
        lay.addWidget(self._state_frame)
        self.set_state("IDLE")

        self._clock = QLabel("--:--:--"); self._clock.setFont(font_mono(10, W_BOLD, 1))
        self._clock.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        lay.addWidget(self._clock)

        # ⌘K
        self._cmdk = _CmdKButton(); self._cmdk.clicked.connect(self.cmdkRequested)
        lay.addWidget(self._cmdk)
        lay.addWidget(vline(14))

        ctrls = _WindowControls()
        ctrls.minimize.connect(self.minimizeRequested)
        ctrls.maximize.connect(self.maximizeRequested)
        ctrls.close.connect(self.closeRequested)
        lay.addWidget(ctrls)

    def set_clock(self, text: str):
        self._clock.setText(text)

    # Presence state → coloured PRESENCE pill (away/idle/active/focus).
    _PRESENCE_COLORS = {
        "away": "textMut", "idle": "amber", "active": "green", "focus": "cyan",
    }

    def set_presence(self, state: str, detail: str = "") -> None:
        label = state.upper() if state else "—"
        if detail:
            label = f"{label} · {detail}"
        self.pill_presence.set_value(label)
        self.pill_presence.set_color(self._PRESENCE_COLORS.get(state, "cyan"))

    def set_state(self, state: str):
        s = JSTATES.get(state, JSTATES["IDLE"])
        c = col(s["key"])
        self._state_dot.set_color(c)
        label = "STANDBY" if state == "IDLE" else s["label"]
        self._state_lbl.setText(label)
        self._state_lbl.setStyleSheet(f"color:{rgba_str(s['key'],1)};background:transparent;")
        self._state_frame.setStyleSheet(
            f"QFrame{{background:{rgba_str(s['key'], 0.1)};"
            f"border:1px solid {rgba_str(s['key'], 0.4)};border-radius:10px;}}"
        )

    # ── frameless drag ─────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPos() - self._win.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            if not self._win.isMaximized():
                self._win.move(e.globalPos() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, _e):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, _e):
        self.maximizeRequested.emit()


class _CmdKButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self); lay.setContentsMargins(8, 3, 8, 3); lay.setSpacing(5)
        from ui.aeris_v6.widgets import IconWidget
        lay.addWidget(IconWidget("search", 11, col("textMut")))
        lbl = QLabel("Ctrl K"); lbl.setFont(font_mono(8, W_BOLD, 0.5))
        lbl.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        lay.addWidget(lbl)
        self._restyle()

    def _restyle(self):
        bd = rgba_str("cyan", 0.4) if self._hover else "rgba(255,255,255,0.08)"
        self.setStyleSheet(
            f"_CmdKButton{{background:rgba(255,255,255,0.04);"
            f"border:1px solid {bd};border-radius:6px;}}"
        )

    def enterEvent(self, _e): self._hover = True; self._restyle()
    def leaveEvent(self, _e): self._hover = False; self._restyle()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()
