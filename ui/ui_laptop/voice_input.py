# File: ui_laptop/voice_input.py

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QProgressBar, QTextEdit, QSizePolicy, QFrame,
                             QDialog, QFormLayout, QFileDialog, QStackedLayout)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QSize
from PyQt5.QtGui import QFont, QPainter, QColor, QLinearGradient, QPen, QPixmap, QBitmap, QRegion, QPainterPath, QTextOption, QIcon
import os
from aeris.ui_laptop.profile_ui import UserAvatarWidget

# Use workspace root for all asset/data paths
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')


# --- TrapeziumInputContainer: wraps mic, waveform, and input, draws top and left glowing edges ---
class TrapeziumInputContainer(QWidget):
    def __init__(self, *contents: QWidget):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        for content in contents:
            layout.addWidget(content)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cut = 28

        path = QPainterPath()
        path.moveTo(cut, 0)
        path.lineTo(w, 0) # Top right (flat)
        path.lineTo(w, h) # Bottom right (flat/vertical for open connection)
        path.lineTo(0, h)
        path.closeSubpath()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(10, 22, 40, 235))
        painter.drawPath(path)

        # Draw border, but skip the right side to make it "open"
        border_pen = QPen(QColor(0, 212, 255, 160), 2)
        painter.setPen(border_pen)
        
        # Manually draw 3 sides
        painter.drawLine(int(cut), 0, int(w), 0) # Top
        # Left side path
        path_left = QPainterPath()
        path_left.moveTo(cut, 0)
        path_left.lineTo(0, h) # Slanted left
        path_left.lineTo(w, h) # Bottom
        painter.drawPath(path_left)
        # Right side is open (no line)


ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class AutoResizingTextEdit(QTextEdit):
    returnPressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(40)
        self.setMaximumHeight(120)
        self.textChanged.connect(self.adjust_height)

    def adjust_height(self):
        doc_height = int(self.document().size().height()) + 12
        self.setFixedHeight(max(40, min(120, doc_height)))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers():
            self.returnPressed.emit()
        else:
            super().keyPressEvent(event)


class DecorativeLine(QWidget):
    """Horizontal line with smoky glow effect"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setFixedWidth(100)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw smoky glow on the left (very small)
        for i in range(3):
            alpha = 40 - (i * 10)
            painter.setPen(Qt.NoPen)
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


class ProfileDialog(QDialog):
    """Simple dialog to edit or login to a profile."""

    def __init__(self, parent=None, profile=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setModal(True)
        self.selected_avatar = None
        self.result_mode = None  # "save" or "login"
        data = profile or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignLeft)

        self.username_input = QLineEdit(data.get("username", ""))
        self.email_input = QLineEdit(data.get("email", ""))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Password (optional for update)")

        form.addRow("Username", self.username_input)
        form.addRow("Email", self.email_input)
        form.addRow("Password", self.password_input)

        avatar_row = QHBoxLayout()
        self.avatar_label = QLabel("No file selected")
        choose_btn = QPushButton("Choose Avatar")
        choose_btn.clicked.connect(self._choose_avatar)
        remove_btn = QPushButton("Remove Avatar")
        remove_btn.clicked.connect(self._remove_avatar)
        avatar_row.addWidget(choose_btn)
        avatar_row.addWidget(remove_btn)
        avatar_row.addWidget(self.avatar_label)

        layout.addLayout(form)
        layout.addLayout(avatar_row)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save Profile")
        login_btn = QPushButton("Login")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self._save)
        login_btn.clicked.connect(self._login)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(login_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self.setStyleSheet("""
            QDialog {
                background-color: #0a1628;
                border: 1px solid #00d4ff;
                border-radius: 10px;
                color: #e5f6ff;
            }
            QLineEdit {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(0, 212, 255, 0.4);
                border-radius: 6px;
                padding: 6px 8px;
                color: #e5f6ff;
            }
            QPushButton {
                background: rgba(0, 212, 255, 0.12);
                border: 1px solid rgba(0, 212, 255, 0.6);
                color: #e5f6ff;
                border-radius: 6px;
                padding: 8px 10px;
            }
            QPushButton:hover {
                background: rgba(0, 255, 255, 0.2);
            }
        """)

    def _choose_avatar(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Avatar", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.selected_avatar = path
            self.avatar_label.setText(os.path.basename(path))

    def _remove_avatar(self):
        self.selected_avatar = None
        self.avatar_label.setText("No file selected")

    def _save(self):
        self.result_mode = "save"
        self.accept()

    def _login(self):
        self.result_mode = "login"
        self.accept()

    def payload(self):
        data = {
            "username": self.username_input.text().strip(),
            "email": self.email_input.text().strip(),
            "password": self.password_input.text().strip() or None,
            "avatar_path": self.selected_avatar,
        }
        return data


class AnimatedWaveformMic(QWidget):
    """Animated microphone with a single tracing line"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 50)
        self.animation_state = 0
        self.is_listening = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Animation timer
        self.wave_timer = QTimer()
        self.wave_timer.timeout.connect(self.update_wave)

    def start_animation(self):
        self.is_listening = True
        self.animation_state = 0
        self.wave_timer.start(50)
        self.update()

    def stop_animation(self):
        self.is_listening = False
        self.wave_timer.stop()
        self.update()

    def update_wave(self):
        self.animation_state = (self.animation_state + 1) % 60
        self.update()

    def paintEvent(self, event):
        if not self.is_listening:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        center_y = h / 2
        mic_x = w - 4  # mic icon right edge position (reduced gap)

        left_x = 8
        right_x = w - 8

        # Base line: slightly tapered and faded at edges
        base_pen = QPen(QColor(0, 212, 255, 110), 3)
        painter.setPen(base_pen)
        painter.drawLine(int(left_x), int(center_y), int(mic_x), int(center_y))

        # Edge fade (narrowing toward left)
        fade_pen_left = QPen(QColor(0, 212, 255, 40), 2)
        painter.setPen(fade_pen_left)
        painter.drawLine(int(left_x), int(center_y), int(left_x + 18), int(center_y))

        # Tracing glow moving from right to left
        phase = self.animation_state / 60.0
        span = (mic_x - left_x)
        tracer_len = 50
        pos = mic_x - (span + tracer_len) * phase
        start = max(left_x, pos)
        end = max(left_x, pos + tracer_len)

        glow_pen = QPen(QColor(0, 255, 255, 190), 8)
        painter.setPen(glow_pen)
        painter.drawLine(int(start), int(center_y), int(end), int(center_y))

        bright_pen = QPen(QColor(160, 235, 255, 240), 3)
        painter.setPen(bright_pen)
        painter.drawLine(int(start), int(center_y), int(end), int(center_y))

        painter.end()


class AngledInputContainer(QWidget):
    """Input container with a sharp triangular left edge"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
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
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(10, 22, 40, 204))
        painter.drawPath(path)
        
        painter.setPen(QPen(QColor(0, 212, 255), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        
        painter.end()









class VoiceInputWidget(QWidget):
    """Voice input interface at the bottom of the application"""

    def setup_animation(self):
        # Stub for animation setup (to be implemented)
        pass

    def _on_lock_toggle(self):
        # Stub for lock toggle button click (to be implemented)
        pass

    def _on_logout_clicked(self):
        # Stub for logout button click (to be implemented)
        pass
        pass

    def _on_remove_avatar(self):
        # Stub for removing avatar (to be implemented)
        pass
        pass

    def _open_profile_dialog(self):
        # Deprecated: Profile is now handled by UserAvatarWidget context menu
        pass

    def _select_avatar_from_card(self):
        # Stub for avatar selection from card (to be implemented)
        pass

    def set_assistant_state(self, state: str):
        """Update voice bar visuals based on assistant state"""
        self.assistant_state = state
        
        # Color and label mapping
        state_info = {
            "IDLE": ("#00d4ff", "AERIS READY"),
            "LISTENING": ("#00ffff", "LISTENING..."),
            "THINKING": ("#ffb450", "THINKING..."),
            "SLEEPING": ("#5080ff", "ASLEEP - SAY 'WAKE UP'"),
            "SPEAKING": ("#00ffff", "SPEAKING..."),
        }
        color, label = state_info.get(state, ("#00d4ff", "AERIS"))
        
        self.listening_label.setText(label)
        self.listening_label.setStyleSheet(f"color: {color}; background: transparent; padding: 0px; letter-spacing: 2px;")
        
        # Start/stop animations based on state
        if state in ["LISTENING", "SPEAKING", "THINKING"]:
            self.waveform_animation.start_animation()
        else:
            self.waveform_animation.stop_animation()

    def toggle_listening(self):
        # Toggle hardware listening state (Mic Toggle)
        self.is_listening = not self.is_listening
        
        # Signal explicitly requests listening hardware change
        self.listening_changed.emit(self.is_listening)
        
        # Update visibility regardless of assistant state
        self.listening_label.setVisible(self.is_listening)
        if not self.is_listening:
             self.waveform_animation.stop_animation()

    send_clicked = pyqtSignal(str)  # Emit text when send is clicked
    listening_changed = pyqtSignal(bool)
    create_profile_requested = pyqtSignal(dict)
    login_requested = pyqtSignal(dict)
    logout_requested = pyqtSignal()
    avatar_change_requested = pyqtSignal(object)  # str or None
    lock_toggle_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_listening = False
        self.profile_data = {}
        self.setup_ui()
        self.setup_animation()

    def setup_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)

        # Listening status label (hidden by default)
        self.listening_label = QLabel("")
        self.listening_label.setVisible(False)
        self.listening_label.setStyleSheet("color: #00d4ff; background: transparent; padding: 0px; letter-spacing: 2px;")
        main_layout.addWidget(self.listening_label)

        # --- MIC WIDGET ---
        self.waveform_animation = AnimatedWaveformMic()
        self.voice_indicator = ClickableLabel()
        mic_icon = QPixmap(os.path.join(ASSETS_DIR, "mic_icon.png")).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.SmoothTransformation)
        self.voice_indicator.setPixmap(mic_icon)
        self.voice_indicator.setFixedSize(48, 48)
        self.voice_indicator.setStyleSheet("background: transparent; border: none;")
        self.voice_indicator.clicked.connect(self.toggle_listening)

        self.mic_widget = QWidget()
        self.mic_layout = QHBoxLayout(self.mic_widget)
        self.mic_layout.setContentsMargins(0, 0, 0, 0)
        self.mic_layout.setSpacing(10)
        self.mic_layout.addWidget(self.voice_indicator)
        self.mic_layout.addWidget(self.waveform_animation)
        self.mic_layout.addStretch()

        # --- INPUT FIELD ---
        self.input_field_container = QWidget()
        self.input_field_container.setFixedHeight(48)
        self.input = AutoResizingTextEdit()
        self.input.setPlaceholderText("Ask AERIS anything...")
        self.input.setFont(QFont("Segoe UI", 11))
        self.input.setStyleSheet("""
            QTextEdit {
                background-color: rgba(10, 22, 40, 0.85);
                color: #ffffff;
                border: 2px solid #00d4ff;
                border-radius: 8px;
                padding: 8px 70px 8px 16px;
                font-size: 12pt;
            }
            QTextEdit:focus { border: 2px solid #00ffff; }
        """)
        self.input.returnPressed.connect(self.on_send)
        
        self.send_button = QPushButton("SEND")
        self.send_button.setFixedSize(60, 36)
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff; color: #0a1628;
                border: none; border-radius: 6px; font-weight: bold;
            }
            QPushButton:hover { background-color: #00ffff; }
        """)
        self.send_button.clicked.connect(self.on_send)
        self.send_button.setParent(self.input)
        
        # Overlay send button
        def position_send(): self.send_button.move(self.input.width() - 66, 6)
        orig_resize = self.input.resizeEvent
        
        def handle_resize(e):
            orig_resize(e)
            position_send()
            
        self.input.resizeEvent = handle_resize
        position_send()

        self.input_field_layout = QHBoxLayout(self.input_field_container)
        self.input_field_layout.setContentsMargins(0, 0, 0, 0)
        self.input_field_layout.addWidget(self.input)

        # --- AVATAR WIDGET ---
        self.avatar_widget = UserAvatarWidget(parent=self, size=80)
        self.avatar_widget.avatar_changed.connect(lambda p: self.avatar_change_requested.emit(p))
        user_path = os.path.join(ASSETS_DIR, "user_logo.png")
        if os.path.exists(user_path): self.avatar_widget.set_default_icon(user_path)

        # --- BOTTOM ROW ---
        self.main_input_row = QWidget()
        self.main_input_layout = QHBoxLayout(self.main_input_row)
        self.main_input_layout.setContentsMargins(0, 0, 0, 0)
        self.main_input_layout.setSpacing(15)
        self.main_input_layout.addWidget(self.mic_widget)
        self.main_input_layout.addWidget(self.input_field_container, 1)

        self.trapezium = TrapeziumInputContainer(self.main_input_row)
        self.bottom_container = QWidget()
        self.bottom_layout = QHBoxLayout(self.bottom_container)
        self.bottom_layout.setContentsMargins(0, 0, 16, 0)
        self.bottom_layout.setSpacing(-10)
        self.bottom_layout.addWidget(self.trapezium, 1)
        self.bottom_layout.addWidget(self.avatar_widget)
        main_layout.addWidget(self.bottom_container)

        # --- PROFILE PANEL ---
        self.profile_panel = self._build_profile_panel()
        self.profile_panel.setVisible(False)

        # --- STATUS BAR ---
        self.status_bar = QWidget()
        self.status_bar.setMaximumHeight(48)
        self.status_bar.setStyleSheet("background-color: rgba(5, 11, 20, 0.95); border-top: 1px solid rgba(0, 212, 255, 0.3);")
        self.status_bar_layout = QHBoxLayout(self.status_bar)
        self.status_bar_layout.setContentsMargins(18, 10, 18, 10)
        self.status_bar_layout.addStretch()
        
        arrow = QLabel("▶")
        arrow.setStyleSheet("color: #00d4ff; background: transparent;")
        self.status_bar_layout.addWidget(arrow)
        
        self.system_label = QLabel("AERIS SYSTEMS - ANIMC LINK INTERFACE")
        self.system_label.setStyleSheet("color: #888888; background: transparent; letter-spacing: 1px;")
        self.status_bar_layout.addWidget(self.system_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(120, 7)
        self.progress_bar.setValue(65)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background: rgba(255, 255, 255, 0.1); border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #ff6600; border-radius: 2px; }
        """)
        self.status_bar_layout.addWidget(self.progress_bar)
        self.status_bar_layout.addStretch()
        main_layout.addWidget(self.status_bar)

        self.setStyleSheet("VoiceInputWidget { background: transparent; }")

    def on_send(self):
        text = self.input.toPlainText().strip()
        if text:
            self.input.setEnabled(False)
            self.send_clicked.emit(text)
            self.input.clear()
            if self.is_listening:
                self.listening_label.setText("MIC ACTIVE - LISTENING...")
            QTimer.singleShot(50, lambda: self.input.setEnabled(True))


    def _build_profile_panel(self):
        panel = QFrame(self)
        panel.setObjectName("profilePanel")
        panel.setFixedWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header with avatar and identity
        header = QHBoxLayout()
        header.setSpacing(10)
        self.profile_avatar_label = ClickableLabel()
        avatar_pixmap = QPixmap(os.path.join(ASSETS_DIR, "user_logo.png")).scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.SmoothTransformation)
        self.profile_avatar_label.setPixmap(avatar_pixmap)
        self.profile_avatar_label.setFixedSize(60, 60)
        self.profile_avatar_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 10, 20, 0.8);
                border: 1px solid #00d4ff;
                border-radius: 24px;
            }
        """)
        self.profile_avatar_label.clicked.connect(self._select_avatar_from_card)
        header.addWidget(self.profile_avatar_label)

        identity_layout = QVBoxLayout()
        self.profile_name_label = QLabel("Aeris")
        self.profile_name_label.setObjectName("profileName")
        self.profile_name_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.profile_email_label = QLabel("@aeris.ai")
        self.profile_email_label.setObjectName("profileEmail")

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setFixedWidth(10)
        self.status_label = QLabel("Online")
        self.status_label.setObjectName("statusText")
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label)
        status_row.addStretch()

        identity_layout.addWidget(self.profile_name_label)
        identity_layout.addWidget(self.profile_email_label)
        identity_layout.addLayout(status_row)
        header.addLayout(identity_layout)
        header.addStretch()
        layout.addLayout(header)

        self.profile_btn = self._make_action_button("Profile")
        self.remove_avatar_btn = self._make_action_button("Remove avatar")
        self.lock_btn = self._make_action_button("Lock system")
        self.logout_btn = self._make_action_button("Log out", danger=True)

        # Disable remove avatar button by default (no avatar initially)
        self.remove_avatar_btn.setEnabled(False)

        self.profile_btn.clicked.connect(self._open_profile_dialog)
        self.remove_avatar_btn.clicked.connect(self._on_remove_avatar)
        self.logout_btn.clicked.connect(self._on_logout_clicked)
        self.lock_btn.clicked.connect(self._on_lock_toggle)

        layout.addWidget(self.profile_btn)
        layout.addWidget(self.remove_avatar_btn)
        layout.addWidget(self.lock_btn)
        layout.addWidget(self.logout_btn)

        panel.setStyleSheet("""
            QFrame#profilePanel {
                background-color: rgba(8, 18, 32, 0.94);
                border: 1px solid rgba(0, 212, 255, 0.5);
                border-radius: 12px;
            }
            QLabel#profileName {
                color: #00d4ff;
                letter-spacing: 1px;
            }
            QLabel#profileEmail {
                color: #b0c4de;
                font-size: 10pt;
            }
            QLabel#statusDot {
                color: #26de81;
                font-size: 12pt;
            }
            QLabel#statusText {
                color: #9ad4ff;
                font-size: 9pt;
            }
        """)
        return panel

    def _make_action_button(self, label: str, danger: bool = False) -> QPushButton:
        button = QPushButton(label)
        button.setCursor(Qt.PointingHandCursor)
        button.setObjectName("profileAction")
        button.setFlat(True)
        button.setMinimumHeight(40)
        button.setMaximumHeight(46)
        button.setStyleSheet("""
            QPushButton#profileAction {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 212, 255, 0.12), stop:1 rgba(0, 212, 255, 0.05));
                border: 1px solid rgba(0, 212, 255, 0.4);
                color: #e5f6ff;
                border-radius: 8px;
                padding: 12px;
                font-size: 10pt;
                text-align: left;
            }
            QPushButton#profileAction:hover {
                border-color: rgba(0, 255, 255, 0.6);
                background: rgba(0, 255, 255, 0.12);
            }
            QPushButton#profileAction:pressed {
                background: rgba(0, 255, 255, 0.2);
            }
            QPushButton#profileAction:disabled {
                background: rgba(100, 100, 100, 0.1);
                border: 1px solid rgba(100, 100, 100, 0.3);
                color: rgba(200, 200, 200, 0.4);
            }
        """ if not danger else """
            QPushButton#profileAction {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(255, 99, 99, 0.12), stop:1 rgba(255, 99, 99, 0.05));
                border: 1px solid rgba(255, 99, 99, 0.5);
                color: #ffb3b3;
                border-radius: 8px;
                padding: 12px;
                font-size: 10pt;
                text-align: left;
            }
            QPushButton#profileAction:hover {
                border-color: rgba(255, 99, 99, 0.8);
                background: rgba(255, 99, 99, 0.12);
            }
            QPushButton#profileAction:pressed {
                background: rgba(255, 99, 99, 0.2);
            }
            QPushButton#profileAction:disabled {
                background: rgba(100, 100, 100, 0.1);
                border: 1px solid rgba(100, 100, 100, 0.3);
                color: rgba(200, 200, 200, 0.4);
            }
        """)
        return button

    def toggle_profile_panel(self):
        # Ensure the panel is parented to the main window so it is not clipped by the voice bar
        if self.profile_panel.parent() != self.window():
            self.profile_panel.setParent(self.window())

        if self.profile_panel.isVisible():
            self.profile_panel.hide()
            return

        self._position_profile_panel()
        self.profile_panel.raise_()
        self.profile_panel.show()

    def _position_profile_panel(self):
        self.profile_panel.adjustSize()
        panel_size = self.profile_panel.size()

        # Map the avatar position to the window, then anchor the panel relative to it
        btn_global = self.avatar_widget.mapToGlobal(QPoint(0, 0))
        parent = self.profile_panel.parent() or self.window()
        btn_in_parent = parent.mapFromGlobal(btn_global)

        x = btn_in_parent.x() + self.avatar_widget.width() - panel_size.width()
        y = btn_in_parent.y() - panel_size.height() - 12

        # If not enough space above, drop it below the button
        if y < 12:
            y = btn_in_parent.y() + self.avatar_widget.height() + 12

        # Keep inside parent bounds
        x = max(12, min(x, parent.width() - panel_size.width() - 12))
        y = max(12, min(y, parent.height() - panel_size.height() - 12))

        self.profile_panel.move(x, y)

    def _crop_center_square(self, pixmap: QPixmap, target_size: int) -> QPixmap:
        if pixmap.isNull():
            return pixmap
        w = pixmap.width()
        h = pixmap.height()
        side = min(w, h)
        x = (w - side) // 2
        y = (h - side) // 2
        cropped = pixmap.copy(x, y, side, side)
        return cropped.scaled(target_size, target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.SmoothTransformation)

    def set_user_profile(self, profile: dict):
        self.profile_data = profile or {}
        name = self.profile_data.get("username") or "Guest"
        email = self.profile_data.get("email") or "@aeris.ai"
        logged_in = bool(self.profile_data.get("logged_in"))
        avatar_path = self.profile_data.get("avatar_path")

        self.profile_name_label.setText(name)
        self.profile_email_label.setText(email)
        self.status_label.setText("Online" if logged_in else "Offline")
        self.status_dot.setStyleSheet(f"color: {'#26de81' if logged_in else '#9aa0a6'};")
        self.logout_btn.setText("Log out" if logged_in else "Log in")
        self.lock_btn.setText("Unlock system" if self.profile_data.get("locked") else "Lock system")

        # Disable remove avatar button if no custom avatar is set
        has_avatar = bool(avatar_path and os.path.exists(avatar_path))
        if hasattr(self, 'remove_avatar_btn'):
            self.remove_avatar_btn.setEnabled(has_avatar)
            if has_avatar:
                self.remove_avatar_btn.setToolTip("Remove current avatar")
            else:
                self.remove_avatar_btn.setToolTip("Please set an avatar to use this feature")

        # Update avatar in profile panel and main button (center-crop like WhatsApp)
        if has_avatar:
            pixmap = QPixmap(avatar_path)
            cropped_panel = self._crop_center_square(pixmap, 56)
            self.profile_avatar_label.setPixmap(cropped_panel)
            # Update main UI if needed (UserAvatarWidget handles its own icon)
            pass
        else:
            # Reset to default avatar
            default_pixmap = QPixmap(os.path.join(ASSETS_DIR, "user_logo.png"))
            self.profile_avatar_label.setPixmap(default_pixmap.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.SmoothTransformation))
            # Reset to default avatar (UserAvatarWidget handles its own icon)
            pass

    def set_lock_state(self, locked: bool):
        """Update lock state in the UI"""
        if hasattr(self, 'profile_data'):
            self.profile_data['locked'] = locked
        if hasattr(self, 'lock_btn'):
            self.lock_btn.setText("Unlock system" if locked else "Lock system")

    def set_heard_text(self, text: str):
        """Update the input field with heard text"""
        if hasattr(self, 'input'):
            self.input.setPlainText(text)

