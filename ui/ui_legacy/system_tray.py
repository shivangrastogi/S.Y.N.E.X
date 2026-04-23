# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/system_tray.py
import sys
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt
from core.event_bus import event_bus
from core.state_manager import state_manager
from utils.logger import logger

class SystemTray(QSystemTrayIcon):
    """
    Phase 8: Manages the background system tray icon and context menu.
    Allows A.E.R.I.S to stay alive even when the front-end UI is hidden.
    """
    def __init__(self, app, main_window):
        # Generate a simple placeholder icon natively
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#00bfff"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        
        super().__init__(QIcon(pixmap), main_window)
        self.app = app
        self.main_window = main_window
        # Link the bridge to tray for expand events
        from core.event_bus import event_bus
        event_bus.subscribe("ui.request_expand_hub", lambda p: self._open_hub())
        
        self.setToolTip("A.E.R.I.S Core active")
        
        # Build Context Menu
        self.menu = QMenu()
        
        self.toggle_action = QAction("Show/Hide Overlay")
        self.toggle_action.triggered.connect(self._toggle_window)
        self.menu.addAction(self.toggle_action)

        self.hub_action = QAction("A.E.R.I.S Stark Hub")
        self.hub_action.triggered.connect(self._open_hub)
        self.menu.addAction(self.hub_action)
        
        self.startup_action = QAction("Run at Startup", checkable=True)
        self.startup_action.setChecked(self._is_startup_enabled())
        self.startup_action.triggered.connect(self._toggle_startup)
        self.menu.addAction(self.startup_action)

        self.debug_action = QAction("Debug Logging", checkable=True)
        self.debug_action.setChecked(False)
        self.debug_action.triggered.connect(self._toggle_debug_logging)
        self.menu.addAction(self.debug_action)

        self.menu.addSeparator()
        
        self.exit_action = QAction("Exit A.E.R.I.S")
        self.exit_action.triggered.connect(self._exit_system)
        self.menu.addAction(self.exit_action)
        
        self.setContextMenu(self.menu)
        
        # Left click action
        self.activated.connect(self._on_tray_click)

    def _toggle_window(self):
        if self.main_window.isVisible() and self.main_window._panel_expanded:
            self.main_window.hide()
        else:
            self.main_window._expand_panel()
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    def _open_hub(self):
        logger.info("SystemTray: Launching A.E.R.I.S Stark Hub.")
        if not hasattr(self, 'stark_hub') or self.stark_hub is None:
            from ui.v2.stark_hub import StarkHubWindow
            self.stark_hub = StarkHubWindow()
        
        self.stark_hub.show()
        self.stark_hub.raise_()
        self.stark_hub.activateWindow()

    def _on_tray_click(self, reason):
        logger.info(f"SystemTray: Icon activated with reason: {reason}")
        if reason in [QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick]:
            self._toggle_window()

    def _is_startup_enabled(self):
        """Checks Windows Registry for startup entry."""
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "AERIS_AI")
            return True
        except:
            return False

    def _toggle_startup(self):
        import winreg
        import os
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if self.startup_action.isChecked():
                winreg.SetValueEx(key, "AERIS_AI", 0, winreg.REG_SZ, f'"{exe_path}"')
                logger.info("Startup registration active.")
            else:
                winreg.DeleteValue(key, "AERIS_AI")
                logger.info("Startup registration removed.")
        except Exception as e:
            logger.error(f"Failed to toggle startup: {e}")

    def _toggle_debug_logging(self):
        import logging
        level = logging.DEBUG if self.debug_action.isChecked() else logging.INFO
        logging.getLogger().setLevel(level)
        logger.info(f"Logging level changed to {'DEBUG' if level == logging.DEBUG else 'INFO'}")

    def _exit_system(self):
        logger.info("System Tray EXIT triggered. Emitting shutdown request.")
        
        # Disable the tray to prevent double clicks during cleanup
        self.exit_action.setEnabled(False)
        self.toggle_action.setEnabled(False)
        
        # Close Stark Hub if open
        if hasattr(self, 'stark_hub') and self.stark_hub:
            self.stark_hub.close()
            
        # Fire graceful shutdown into the A.E.R.I.S background loop
        event_bus.emit("system.shutdown_requested", {})
