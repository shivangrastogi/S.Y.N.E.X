from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, pyqtSignal, QSize, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QBrush


class SmoothToggleSwitch(QWidget):
    """Smooth animated toggle switch for gesture mode"""
    toggled = pyqtSignal(bool)  # Emits True when ON, False when OFF
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 28)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._is_on = False
        self._slider_pos = 0
        self._animation = None
        
    def is_on(self):
        return self._is_on
    
    def set_on(self, value: bool, animate=True):
        """Set toggle state with optional animation"""
        if self._is_on == value:
            return
        
        self._is_on = value
        target_pos = 32 if value else 0
        
        if animate:
            # Stop any running animation
            if self._animation:
                self._animation.stop()
                try:
                    self._animation.finished.disconnect()
                except:
                    pass
            
            # Create smooth animation
            self._animation = QPropertyAnimation(self, b"sliderPos")
            self._animation.setDuration(300)  # 300ms animation
            self._animation.setStartValue(self._slider_pos)
            self._animation.setEndValue(target_pos)
            self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
            # Ensure final position is set when animation completes
            self._animation.finished.connect(lambda: self._finalize_animation(target_pos))
            self._animation.start()
        else:
            self._slider_pos = target_pos
            self.update()
        
        self.toggled.emit(value)
    
    def _finalize_animation(self, final_pos):
        """Ensure slider ends at exact position after animation"""
        self._slider_pos = final_pos
        self.update()
    
    def toggle(self):
        """Toggle the switch"""
        self.set_on(not self._is_on)
    
    def mousePressEvent(self, event):
        """Handle click to toggle"""
        self.toggle()
        super().mousePressEvent(event)
    
    def keyPressEvent(self, event):
        """Handle space/return to toggle"""
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return):
            self.toggle()
        super().keyPressEvent(event)
    
    # Property for animation - use pyqtProperty for proper Qt integration
    def _get_slider_pos(self):
        return self._slider_pos
    
    def _set_slider_pos(self, value):
        self._slider_pos = value
        self.update()
    
    sliderPos = pyqtProperty(int, _get_slider_pos, _set_slider_pos)
    
    def sizeHint(self):
        return QSize(60, 28)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width, height = self.width(), self.height()
        radius = height // 2
        
        # Background
        bg_color = QColor(0, 212, 255) if self._is_on else QColor(100, 100, 100)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, width, height, radius, radius)
        
        # Slider circle
        slider_x = self._slider_pos
        slider_color = QColor(255, 255, 255)
        painter.setBrush(QBrush(slider_color))
        painter.drawEllipse(slider_x, 2, height - 4, height - 4)
        
        # Glow effect for ON state
        if self._is_on:
            painter.setPen(QColor(0, 212, 255, 80))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(-2, -2, width + 4, height + 4, radius + 2, radius + 2)
        
        painter.end()
