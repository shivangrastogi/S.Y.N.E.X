# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/status_indicator.py
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QTimer

class StatusIndicator(QWidget):
    """
    The minimalist 'Orb'.
    A custom-painted Qt Widget that pulses and changes color based on A.E.R.I.S state.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Animation Properties
        self._radius = 15.0
        self._growing = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(50)
        
        # State Colors
        self.colors = {
            "IDLE": QColor("#004466"),          # Dim Cyan (Debug Visible)
            "LISTENING": QColor("#00ff88"),     # Bright Green
            "THINKING": QColor("#ffaa00"),      # Yellow/Orange
            "EXECUTING": QColor("#00bfff"),     # Cyan / Deep Blue
            "SPEAKING": QColor("#a200ff"),      # Deep Purple
            "SAFE_MODE": QColor("#ff0044")      # Red Alert
        }
        self.current_state = "IDLE"

    def set_state(self, state: str):
        if state in self.colors:
            self.current_state = state
            
            # Reset pulsing animation based on activity
            if state == "IDLE":
                self._timer.stop()
                self._radius = 15.0
            else:
                self._timer.start(50)
                
            self.update()

    def _animate(self):
        """Gentle pulsing animation."""
        step = 1.0
        if self.current_state in ["THINKING", "EXECUTING"]:
            step = 2.0  # Pulse faster when busy
            
        if self._growing:
            self._radius += step
            if self._radius >= 25.0:
                self._growing = False
        else:
            self._radius -= step
            if self._radius <= 15.0:
                self._growing = True
                
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Center coordinates
        cx = self.width() / 2
        cy = self.height() / 2
        
        color = self.colors.get(self.current_state, QColor("#2a2b2e"))
        
        # Outer Glow
        painter.setOpacity(0.3)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(int(cx - self._radius), int(cy - self._radius), int(self._radius * 2), int(self._radius * 2))
        
        # Inner Solid Core
        painter.setOpacity(1.0)
        painter.setBrush(color.darker(150))
        painter.drawEllipse(int(cx - 10), int(cy - 10), 20, 20)
