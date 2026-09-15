# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/main_window.py
import sys
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QDesktopWidget
from PyQt5.QtCore import Qt, QPoint
from ui.status_indicator import StatusIndicator
from ui.chat_panel import ChatPanel
from ui.event_bridge import ui_bridge
from core.brain_router import brain_router
from core.state_manager import state_manager, AssistantState
from memory.storage import storage
from utils.logger import logger

class MainWindow(QWidget):
    """
    Phase 8: The primary frameless, transparent overlay wrapping the Orb and Chat.
    """
    def __init__(self):
        super().__init__()
        # Frameless, Always on Top, Transparent
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Layout: Orb on Left, Panel on Right
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)
        
        self.orb = StatusIndicator(self)
        self.layout.addWidget(self.orb, alignment=Qt.AlignBottom | Qt.AlignRight)
        
        self.panel = ChatPanel(self)
        self.layout.addWidget(self.panel, alignment=Qt.AlignBottom | Qt.AlignRight)
        
        # Start with panel collapsed
        self._panel_expanded = False
        self.panel.hide()
        
        # Auto-hide timer (Phase 9)
        from PyQt5.QtCore import QTimer
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._collapse_panel)
        
        # Cache screen geometry to avoid expensive QDesktopWidget calls on every move/resize
        self._cached_screen_rect = QDesktopWidget().availableGeometry()
        self._last_geometry_refresh = time.time()
        
        # Initial sizing
        self._set_geometry()
        
        # Connect to Event Bridge (Allows safe cross-thread UI updates)
        self._connect_signals()
        
        # Mouse Drag State
        self._drag_pos = None

        self.show()
        logger.info(f"MainWindow: UI Visible at {self.geometry().x()}, {self.geometry().y()} with size {self.width()}x{self.height()}")
        
        # Set intro text
        self.panel.append_message("System", f"{storage.get_profile_value('assistant_name', 'A.E.R.I.S')} Phase 8 Overlay Initialized.", "#00bfff")

    def _set_geometry(self):
        # Refresh cache if older than 30 seconds (safety for monitor changes)
        if time.time() - self._last_geometry_refresh > 30:
            self._cached_screen_rect = QDesktopWidget().availableGeometry()
            self._last_geometry_refresh = time.time()
            
        screen = self._cached_screen_rect
        width = 420 if self._panel_expanded else 70
        height = 400 if self._panel_expanded else 70
        # Position at bottom-right
        margin = 20
        self.setGeometry(screen.width() - width - margin, screen.height() - height - margin, width, height)

    def _connect_signals(self):
        # Tie Qt Signals to UI refreshes
        ui_bridge.state_changed.connect(self._on_state_changed)
        ui_bridge.text_heard.connect(lambda t: self.panel.append_message("User", t, "#00ff88"))
        ui_bridge.partial_text_heard.connect(self.panel.set_partial_text)
        ui_bridge.task_started.connect(lambda p: self.panel.append_message("System", f"Executing target: {p.get('intent')}", "#ffaa00"))
        ui_bridge.manual_listen_trigger.connect(self._on_hotkey_triggered)
        
        # Wire the user input field directly into the core Brain Router
        self.panel.get_input_field().returnPressed.connect(self._on_manual_input)

    def _on_hotkey_triggered(self):
        """Triggered by Ctrl+Space globally."""
        self._expand_panel()
        self.panel.get_input_field().setFocus()
        state_manager.transition_to(AssistantState.LISTENING)
        self.panel.append_message("System", "Listening via Hotkey...", "#00ff88")

    def _on_state_changed(self, new_state: str):
        """Reacts to A.E.R.I.S core state changes (e.g., IDLE, LISTENING)."""
        self.orb.set_state(new_state)
        
        if new_state == "IDLE":
            # Start 5-second countdown to collapse
            self._hide_timer.start(5000)
        else:
            # We are active, stop any pending hide and ensure expanded
            self._hide_timer.stop()
            self._expand_panel()

    def _on_manual_input(self):
        """Passes manual typing directly to the execution router."""
        text = self.panel.get_input_field().text().strip()
        if not text: return
        
        self.panel.get_input_field().clear()
        self.panel.append_message("User", text, "#00ff88")
        
        # Transitioning to LISTENING is redundant here because brain_router.process_input 
        # immediately transitions to THINKING, which is a valid transition from IDLE/LISTENING.
        # state_manager.transition_to(AssistantState.LISTENING)
        brain_router.process_input(text)

    # --- Mouse Dragging to Move the Overlay ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()
            
    def mouseDoubleClickEvent(self, event):
        # Double click the widget to toggle the panel
        if event.button() == Qt.LeftButton:
            if self._panel_expanded:
                self._collapse_panel()
            else:
                self._expand_panel()

    def _expand_panel(self):
        if not self._panel_expanded:
            self._panel_expanded = True
            self.panel.show()
            self._set_geometry()

    def _collapse_panel(self):
        if self._panel_expanded:
            self._panel_expanded = False
            self.panel.hide()
            self._set_geometry()
