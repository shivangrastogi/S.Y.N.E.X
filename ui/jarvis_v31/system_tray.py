"""System-tray integration for AERIS v3.1.

Replaces the legacy ``ui/ui_legacy/system_tray.py`` (which targeted the
old dashboard layout). Wires into the v3.1 main window through a small
``TrayController`` so the window doesn't need to know about tray internals.

Capabilities
------------
* Status icon — colour-coded per AI state (IDLE cyan / LISTENING green /
  PROCESSING magenta / SPEAKING purple). Painted inline (no asset files
  to manage).
* Context menu — Show / Hide window, Mic on / off, Pause, Quit.
* Single-click on the icon toggles window visibility.
* Notification helper — ``notify(title, body)`` → balloon-style toast
  via QSystemTrayIcon's built-in messageIcon API. Falls back silently
  on systems without supportsMessages().

Tray icons are painted on first state change so the GUI thread doesn't
pay startup cost for them.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from PyQt5.QtCore import QObject, QPointF, QRect, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon

log = logging.getLogger(__name__)


_STATE_COLORS = {
    "IDLE":       QColor(0,   215, 230),
    "LISTENING":  QColor(0,   220, 130),
    "PROCESSING": QColor(220, 70,  220),
    "SPEAKING":   QColor(170, 80,  255),
    "OFFLINE":    QColor(120, 120, 120),
}


def _paint_state_icon(state: str, size: int = 32) -> QIcon:
    """Render a small circle icon in the AI-state colour with a soft halo."""
    color = _STATE_COLORS.get(state, _STATE_COLORS["IDLE"])
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    # Halo
    halo = QColor(color); halo.setAlphaF(0.25)
    p.setPen(Qt.NoPen); p.setBrush(halo)
    p.drawEllipse(QPointF(size / 2, size / 2), size * 0.45, size * 0.45)
    # Core
    p.setBrush(color)
    p.drawEllipse(QPointF(size / 2, size / 2), size * 0.28, size * 0.28)
    # Inner highlight (subtle)
    inner = QColor(255, 255, 255, 90)
    p.setBrush(inner)
    p.drawEllipse(QPointF(size / 2 - size * 0.06, size / 2 - size * 0.06),
                  size * 0.10, size * 0.10)
    p.end()
    return QIcon(pm)


class TrayController(QObject):
    """Owns the QSystemTrayIcon + its menu, exposes Qt signals for actions.

    Signals
    -------
    show_window     — user picked "Show window" or clicked the icon
    hide_window     — user picked "Hide window"
    toggle_mic      — user picked "Mic on/off"
    pause_toggled   — user toggled the "Pause" check
    quit_requested  — user picked "Quit"
    """

    show_window     = pyqtSignal()
    hide_window     = pyqtSignal()
    toggle_mic      = pyqtSignal()
    pause_toggled   = pyqtSignal(bool)
    quit_requested  = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._state = "IDLE"
        self._tray: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._pause_action: Optional[QAction] = None
        self._mic_action: Optional[QAction] = None
        self._cache: dict[str, QIcon] = {}

    # ── Lifecycle ───────────────────────────────────────────────────

    def install(self) -> bool:
        """Build the tray icon + menu. Returns False if the platform has
        no system-tray support (rare; some Linux DEs without status
        notifier protocol)."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.info("[tray] system tray unavailable on this platform")
            return False

        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("A.E.R.I.S — JARVIS v3.1")
        self._tray.setIcon(self._icon_for("IDLE"))

        self._menu = QMenu()
        act_show = QAction("Show window", self._menu)
        act_show.triggered.connect(self.show_window.emit)
        self._menu.addAction(act_show)

        act_hide = QAction("Hide to tray", self._menu)
        act_hide.triggered.connect(self.hide_window.emit)
        self._menu.addAction(act_hide)

        self._menu.addSeparator()

        self._mic_action = QAction("Mic on / off", self._menu)
        self._mic_action.triggered.connect(self.toggle_mic.emit)
        self._menu.addAction(self._mic_action)

        self._pause_action = QAction("Pause", self._menu)
        self._pause_action.setCheckable(True)
        self._pause_action.toggled.connect(self.pause_toggled.emit)
        self._menu.addAction(self._pause_action)

        self._menu.addSeparator()
        act_quit = QAction("Quit AERIS", self._menu)
        act_quit.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(act_quit)

        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()
        return True

    def uninstall(self) -> None:
        if self._tray is not None:
            self._tray.hide()
            self._tray = None

    # ── State / notifications ───────────────────────────────────────

    def set_state(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        if self._tray is not None:
            self._tray.setIcon(self._icon_for(state))
            self._tray.setToolTip(f"AERIS · {state.lower()}")

    def notify(self, title: str, body: str, *, msec: int = 4000) -> None:
        """Show a balloon notification. No-op if unsupported."""
        if self._tray is None or not self._tray.supportsMessages():
            return
        try:
            self._tray.showMessage(title, body,
                                   QSystemTrayIcon.Information, msec)
        except Exception:
            pass

    def set_paused(self, paused: bool) -> None:
        """Sync the checkbox state programmatically without re-firing
        ``pause_toggled``."""
        if self._pause_action is None:
            return
        b = self._pause_action.blockSignals(True)
        try:
            self._pause_action.setChecked(paused)
        finally:
            self._pause_action.blockSignals(b)

    # ── Internals ───────────────────────────────────────────────────

    def _icon_for(self, state: str) -> QIcon:
        if state not in self._cache:
            self._cache[state] = _paint_state_icon(state)
        return self._cache[state]

    def _on_activated(self, reason):
        # Trigger == left-click; DoubleClick on some DEs.
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window.emit()


# ── Global hotkey ──────────────────────────────────────────────────── #

class GlobalHotkeyBridge(QObject):
    """Listens for a system-wide hotkey on a background thread, emits a Qt
    signal back to the GUI thread.

    Uses the ``keyboard`` package if available (no admin needed on
    Windows for non-protected hotkeys). Degrades silently when absent
    so AERIS still launches without ``keyboard`` installed.

    Default chord is ``Ctrl+Shift+Space`` — chosen for low conflict
    with common Windows shortcuts and a one-handed reach.
    """

    triggered = pyqtSignal()

    def __init__(self, hotkey: str = "ctrl+shift+space",
                 parent: Optional[QObject] = None):
        super().__init__(parent)
        self._hotkey = hotkey
        self._hook = None

    def install(self) -> bool:
        try:
            import keyboard  # type: ignore
        except ImportError:
            log.info("[hotkey] `keyboard` package not installed — "
                     "global hotkey disabled. (`pip install keyboard`)")
            return False
        try:
            # Suppress=False means we don't eat the key sequence; the
            # callback fires AND the underlying app sees the keys.
            self._hook = keyboard.add_hotkey(
                self._hotkey,
                lambda: self.triggered.emit(),
                suppress=False,
            )
            log.info("[hotkey] registered: %s", self._hotkey)
            return True
        except Exception as e:
            log.warning("[hotkey] registration failed (%s)", e)
            return False

    def uninstall(self) -> None:
        if self._hook is not None:
            try:
                import keyboard  # type: ignore
                keyboard.remove_hotkey(self._hook)
            except Exception:
                pass
            self._hook = None
