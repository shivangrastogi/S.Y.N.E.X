from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QProgressBar, QTextEdit, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QSize
from PyQt6.QtGui import QFont, QPainter, QColor, QLinearGradient, QPen, QPixmap, QBitmap, QRegion, QPainterPath, QTextOption
import os

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class AutoResizingTextEdit(QTextEdit):
    """Text edit that auto-resizes height to fit content and handles Enter key"""
    returnPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        self.textChanged.connect(self._adjust_height)
        self.setFixedHeight(45) # Initial height

    def _adjust_height(self):
        doc = self.document()
        doc.setTextWidth(self.width())
        h = doc.size().height()
        new_height = max(45, min(120, int(h) + 10)) # Min 45, Max 120
        if new_height != self.height():
            self.setFixedHeight(new_height)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            event.accept()
            self.returnPressed.emit()
        else:
            super().keyPressEvent(event)
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_height()


class DecorativeLine(QWidget):
    """Horizontal line with smoky glow effect"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setFixedWidth(100)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw smoky glow on the left (very small)
        for i in range(3):
            alpha = 40 - (i * 10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 212, 255, alpha))
            painter.drawEllipse(5 - i*2, 27 - i*2, 6 + i*4, 6 + i*4)
        
        # Draw main horizontal line
        gradient = QLinearGradient(0, 30, 100, 30)
        gradient.setColorAt(0, QColor(0, 212, 255, 200))
        gradient.setColorAt(0.5, QColor(0, 255, 255, 255))
        gradient.setColorAt(1, QColor(0, 212, 255, 100))
        
        pen = QPen(gradient, 2)
        painter.setPen(pen)
        painter.drawLine(15, 30, 95, 30)
        
        # Add subtle glow under the line
        pen = QPen(QColor(0, 212, 255, 60), 4)
        painter.setPen(pen)
        painter.drawLine(15, 30, 95, 30)
        
        painter.end()


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class AngledInputContainer(QWidget):
    """Input container with a sharp triangular left edge"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        h = self.height()
        w = self.width()
        offset = 20
        tip = offset + 18
        
        radius = 6
        tip_round = 6
        path = QPainterPath()
        path.moveTo(tip, 0)
        path.lineTo(w - radius, 0)
        path.quadTo(w, 0, w, radius)
        path.lineTo(w, h - radius)
        path.quadTo(w, h, w - radius, h)
        path.lineTo(tip, h)
        # rounded tip (top/bottom connections)
        path.quadTo(tip - tip_round, h, tip - (tip_round * 2), h / 2)
        path.quadTo(tip - tip_round, 0, tip, 0)
        path.closeSubpath()
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 22, 40, 204))
        painter.drawPath(path)
        
        painter.setPen(QPen(QColor(0, 212, 255), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        painter.end()




class VoiceInputWidget(QWidget):
    """Voice input interface at the bottom of the application"""
    
    send_clicked = pyqtSignal(str)  # Emit text when send is clicked
    listening_changed = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_listening = False
        self.setup_ui()
        self.setup_animation()
        # Install event filter to reposition send button
        self.input_field.installEventFilter(self)
    
    def eventFilter(self, obj, event):
        """Reposition and resize send button when input field is resized"""
        if obj == self.input_field and event.type() == event.Type.Resize:
            self.update_send_button_position()
        return super().eventFilter(obj, event)
    
    def update_send_button_position(self):
        """Update send button position and height to match input field"""
        # Get input field height (accounting for border)
        field_height = self.input_field.height()
        # Position button flush to right edge, full height
        self.send_button.setGeometry(
            self.input_field.width() - 86,  # 85px width + 1px for border
            1,  # 1px from top for border
            85,  # width
            field_height - 2  # height minus top and bottom borders
        )
        
    def setup_ui(self):
        """Setup the voice input UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top section: Voice input and controls
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(10, 10, 10, 10)
        input_layout.setSpacing(10)
        
        # Add 1/3 empty space on the left
        input_layout.addStretch(1)
        
        # Voice indicator with image
        self.voice_indicator = ClickableLabel()
        mic_path = os.path.join(ASSETS_DIR, "mic_icon.png")
        mic_pixmap = QPixmap(mic_path)
        self.voice_indicator.setPixmap(mic_pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.voice_indicator.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: transparent;
                border: none;
                border-radius: 25px;
                min-width: 50px;
                max-width: 50px;
                min-height: 50px;
                max-height: 50px;
            }
        """)
        self.voice_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.voice_indicator.setCursor(Qt.CursorShape.PointingHandCursor)
        self.voice_indicator.clicked.connect(self.toggle_listening)
        input_layout.addWidget(self.voice_indicator, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # Voice status label
        status_input_container = QWidget()
        status_input_layout = QVBoxLayout(status_input_container)
        status_input_layout.setContentsMargins(0, 0, 0, 0)
        status_input_layout.setSpacing(2)
        
        # Status label
        self.status_label = QLabel("VOICE INPUT ACTIVE")
        self.status_label.setFont(QFont("Consolas", 9))
        self.status_label.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                background-color: transparent;
                padding: 0px;
                letter-spacing: 2px;
            }
        """)
        status_input_layout.addWidget(self.status_label)
        
        # Listening status (hidden)
        self.listening_label = QLabel("")
        self.listening_label.setVisible(False)
        status_input_layout.addWidget(self.listening_label)
        
        # Input field with embedded send button
        input_with_button = AngledInputContainer()
        input_with_button.setMaximumWidth(700)
        # Allow container to expand vertically
        input_with_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum) 
        
        input_with_button_layout = QHBoxLayout(input_with_button)
        input_with_button_layout.setContentsMargins(0, 0, 0, 0)
        input_with_button_layout.setSpacing(0)
        
        self.input_field = AutoResizingTextEdit()
        self.input_field.setPlaceholderText("Ask AERIS anything...")
        self.input_field.setFont(QFont("Segoe UI", 11))
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #ffffff;
                border: none;
                border-radius: 0px;
                padding: 10px 100px 10px 40px;
                font-size: 11pt;
            }
            QTextEdit:focus {
                border: none;
                background-color: transparent;
            }
        """)
        self.input_field.returnPressed.connect(self.on_send)
        input_with_button_layout.addWidget(self.input_field)
        
        # Send button inside input field
        self.send_button = QPushButton("SEND")
        self.send_button.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setFixedWidth(85)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 212, 255, 0.3);
                color: #00d4ff;
                border: none;
                border-left: 1px solid #00d4ff;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                font-size: 9pt;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: rgba(0, 212, 255, 0.5);
                border-left: 1px solid #00ffff;
            }
            QPushButton:pressed {
                background-color: rgba(0, 212, 255, 0.7);
            }
        """)
        self.send_button.clicked.connect(self.on_send)
        
        # Position button on top of input field (right side, full height)
        self.send_button.setParent(self.input_field)
        self.update_send_button_position()
        
        # REMOVED: self.text_display_label and its setup
        
        status_input_layout.addWidget(input_with_button)
        
        input_layout.addWidget(status_input_container, 2, Qt.AlignmentFlag.AlignVCenter)
        
        # User profile icon with circular image and cyberpunk outline
        self.profile_icon = QLabel()
        user_path = os.path.join(ASSETS_DIR, "user_logo.png")
        user_pixmap = QPixmap(user_path)
        
        # Create circular mask
        from PyQt6.QtGui import QBitmap, QRegion
        from PyQt6.QtCore import QRect
        
        scaled_pixmap = user_pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.profile_icon.setPixmap(scaled_pixmap)
        self.profile_icon.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 10, 20, 0.8);
                border: 1px solid #00d4ff;
                border-radius: 30px;
                min-width: 60px;
                max-width: 60px;
                min-height: 60px;
                max-height: 60px;
            }
        """)
        self.profile_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_icon.setScaledContents(False)
        input_layout.addWidget(self.profile_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        
        # Style the container
        input_container.setStyleSheet("""
            QWidget {
                background-color: rgba(10, 22, 40, 0.95);
                border-top: 2px solid #00d4ff;
                border-radius: 0px;
            }
        """)
        
        main_layout.addWidget(input_container)
        
        # Bottom section: Status bar
        status_bar = QWidget()
        status_bar.setMaximumHeight(25)
        status_bar_layout = QHBoxLayout(status_bar)
        status_bar_layout.setContentsMargins(15, 3, 15, 3)
        status_bar_layout.setSpacing(8)
        
        # Add stretch to center content
        status_bar_layout.addStretch()
        
        # Decorative arrow
        arrow_label = QLabel("▶")
        arrow_label.setFont(QFont("Arial", 7))
        arrow_label.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                background-color: transparent;
            }
        """)
        status_bar_layout.addWidget(arrow_label)
        
        # Status text
        self.system_label = QLabel("AERIS SYSTEMS - ANIMC LINK INTERFACE")
        self.system_label.setFont(QFont("Consolas", 8))
        self.system_label.setStyleSheet("""
            QLabel {
                color: #888888;
                background-color: transparent;
                letter-spacing: 1px;
            }
        """)
        status_bar_layout.addWidget(self.system_label)
        
        # Progress bar (inline with text)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(65)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(120)
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff6600, stop:1 #ff9900);
                border-radius: 2px;
            }
        """)
        status_bar_layout.addWidget(self.progress_bar)
        
        status_bar_layout.addStretch()
        
        # Style the status bar
        status_bar.setStyleSheet("""
            QWidget {
                background-color: rgba(5, 11, 20, 0.95);
                border-top: 1px solid rgba(0, 212, 255, 0.3);
            }
        """)
        
        main_layout.addWidget(status_bar)
        
        # Set overall widget style
        self.setStyleSheet("""
            VoiceInputWidget {
                background-color: transparent;
            }
        """)
        
    def setup_animation(self):
        """Setup listening animation"""
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_listening)
        self.animation_state = 0
        
    def animate_listening(self):
        """Animate the listening indicator"""
        self.animation_state = (self.animation_state + 1) % 4
        dots = "." * self.animation_state
        self.listening_label.setText(f"Listening{dots}   ")
        
    def start_listening(self):
        """Start voice listening"""
        self.is_listening = True
        self.animation_timer.start(500)
        self.listening_changed.emit(True)
        self.voice_indicator.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: transparent;
                border: none;
                border-radius: 25px;
                min-width: 50px;
                max-width: 50px;
                min-height: 50px;
                max-height: 50px;
            }
        """)
        
    def stop_listening(self):
        """Stop voice listening"""
        self.is_listening = False
        self.animation_timer.stop()
        self.listening_changed.emit(False)
        self.voice_indicator.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: transparent;
                border: none;
                border-radius: 25px;
                min-width: 50px;
                max-width: 50px;
                min-height: 50px;
                max-height: 50px;
            }
        """)
        
    def toggle_listening(self):
        """Toggle listening state"""
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()
            
    def on_send(self):
        """Handle send button click"""
        text = self.input_field.toPlainText().strip()
        if text:
            self.send_clicked.emit(text)
            self.input_field.clear()
            self.stop_listening()

    # REMOVED: _update_text_display method
