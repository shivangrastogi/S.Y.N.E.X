# Path: d:\New folder (2) - JARVIS\ui_laptop\widgets\settings_page.py
# File: ui_laptop/widgets/settings_page.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QSlider, QSpinBox, QCheckBox, QComboBox, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from ui_laptop.widgets.toggle_switch import SmoothToggleSwitch


class QuantitySelector(QWidget):
    """Horizontal selector with [Minus] [Number] [Plus]"""
    valueChanged = pyqtSignal(int)
    
    def __init__(self, value=5, min_val=1, max_val=20, suffix="", parent=None):
        super().__init__(parent)
        self.value = value
        self.min_val = min_val
        self.max_val = max_val
        self.suffix = suffix
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        btn_style = """
            QPushButton {
                background: rgba(0, 212, 255, 0.15);
                border: 1px solid rgba(0, 212, 255, 0.4);
                border-radius: 4px;
                color: #00d4ff;
                font-size: 18px;
                font-weight: bold;
                min-width: 32px;
                min-height: 32px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.3);
                border-color: rgba(0, 255, 255, 0.6);
            }
            QPushButton:pressed {
                background: rgba(0, 255, 255, 0.5);
            }
        """
        
        self.minus_btn = QPushButton("-")
        self.minus_btn.setFixedSize(32, 32)
        self.minus_btn.setStyleSheet(btn_style)
        self.minus_btn.clicked.connect(self.decrement)
        
        self.value_label = QLabel(f"{self.value}{self.suffix}")
        self.value_label.setStyleSheet("color: #e5f6ff; font-weight: bold; font-size: 14px; min-width: 60px;")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.plus_btn = QPushButton("+")
        self.plus_btn.setFixedSize(32, 32)
        self.plus_btn.setStyleSheet(btn_style)
        self.plus_btn.clicked.connect(self.increment)
        
        layout.addStretch()
        layout.addWidget(self.minus_btn)
        layout.addWidget(self.value_label)
        layout.addWidget(self.plus_btn)
        
    def increment(self):
        if self.value < self.max_val:
            self.value += 1
            self._update_display()
            
    def decrement(self):
        if self.value > self.min_val:
            self.value -= 1
            self._update_display()
            
    def _update_display(self):
        self.value_label.setText(f"{self.value}{self.suffix}")
        self.valueChanged.emit(self.value)
        
    def set_value(self, val):
        self.value = max(self.min_val, min(self.max_val, val))
        self.value_label.setText(f"{self.value}{self.suffix}")


class SettingsCard(QFrame):
    """Card container for settings sections"""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        
        title_label = QLabel(title)
        title_label.setObjectName("settingsCardTitle")
        title_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(10)
        layout.addLayout(self.content_layout)
        
        self.setStyleSheet("""
            QFrame#settingsCard {
                background-color: rgba(8, 18, 32, 0.85);
                border: 1px solid rgba(0, 212, 255, 0.35);
                border-radius: 10px;
            }
            QLabel#settingsCardTitle {
                color: #00d4ff;
                letter-spacing: 1px;
            }
        """)
    
    def add_option(self, widget):
        self.content_layout.addWidget(widget)


class SettingRow(QWidget):
    """A single setting row with label and control"""
    
    def __init__(self, label: str, control: QWidget, description: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        label_layout = QVBoxLayout()
        label_layout.setSpacing(2)
        
        label_widget = QLabel(label)
        label_widget.setObjectName("settingLabel")
        label_widget.setFont(QFont("Segoe UI", 10))
        label_layout.addWidget(label_widget)
        
        if description:
            desc_widget = QLabel(description)
            desc_widget.setObjectName("settingDesc")
            desc_widget.setFont(QFont("Segoe UI", 8))
            desc_widget.setWordWrap(True)
            label_layout.addWidget(desc_widget)
        
        layout.addLayout(label_layout, 1)
        layout.addWidget(control, 0)
        
        self.setStyleSheet("""
            QLabel#settingLabel {
                color: #e5f6ff;
            }
            QLabel#settingDesc {
                color: #9ad4ff;
            }
        """)


class SettingsPage(QWidget):
    """Complete settings page with all configurable options"""
    
    # Signals for settings changes
    tts_enabled_changed = pyqtSignal(bool)
    tts_voice_changed = pyqtSignal(str)
    tts_rate_changed = pyqtSignal(int)
    voice_enabled_changed = pyqtSignal(bool)
    gesture_enabled_changed = pyqtSignal(bool)
    battery_alerts_changed = pyqtSignal(bool)
    auto_lock_changed = pyqtSignal(bool)
    auto_lock_timeout_changed = pyqtSignal(int)
    theme_changed = pyqtSignal(str)
    excerpt_limit_changed = pyqtSignal(int)
    google_calendar_login = pyqtSignal()
    google_calendar_logout = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the settings UI"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: rgba(10, 22, 40, 0.5);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(0, 212, 255, 0.5);
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(0, 255, 255, 0.7);
            }
        """)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        header = QLabel("SYSTEM SETTINGS")
        header.setObjectName("pageTitle")
        header.setFont(QFont("Consolas", 16, QFont.Weight.Bold))
        header.setStyleSheet("QLabel#pageTitle { color: #00d4ff; letter-spacing: 2px; }")
        layout.addWidget(header)
        
        # TTS Settings Card
        tts_card = SettingsCard("🔊 Text-to-Speech")
        
        self.tts_toggle = SmoothToggleSwitch()
        self.tts_toggle.set_on(True, animate=False)
        self.tts_toggle.toggled.connect(self.tts_enabled_changed.emit)
        tts_card.add_option(SettingRow("Enable TTS", self.tts_toggle, "Speak responses aloud"))
        
        self.tts_voice_combo = QComboBox()
        self.tts_voice_combo.addItems(["Microsoft David", "Microsoft Zira", "Microsoft Mark"])
        self.tts_voice_combo.setStyleSheet(self._combo_style())
        self.tts_voice_combo.currentTextChanged.connect(self.tts_voice_changed.emit)
        tts_card.add_option(SettingRow("Voice", self.tts_voice_combo))
        
        self.tts_rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.tts_rate_slider.setRange(-50, 50)
        self.tts_rate_slider.setValue(0)
        self.tts_rate_slider.setStyleSheet(self._slider_style())
        self.tts_rate_slider.valueChanged.connect(self.tts_rate_changed.emit)
        tts_card.add_option(SettingRow("Speech Rate", self.tts_rate_slider, "Adjust speaking speed"))
        
        layout.addWidget(tts_card)
        
        # Voice Input Settings
        voice_card = SettingsCard("🎤 Voice Input")
        
        self.voice_toggle = SmoothToggleSwitch()
        self.voice_toggle.set_on(False, animate=False)
        self.voice_toggle.toggled.connect(self.voice_enabled_changed.emit)
        voice_card.add_option(SettingRow("Auto-Start Voice Listener", self.voice_toggle, 
                                         "Start listening on launch"))
        
        layout.addWidget(voice_card)
        
        # Gesture Settings
        gesture_card = SettingsCard("✋ Gesture Control")
        
        self.gesture_toggle = SmoothToggleSwitch()
        self.gesture_toggle.set_on(False, animate=False)
        self.gesture_toggle.toggled.connect(self.gesture_enabled_changed.emit)
        gesture_card.add_option(SettingRow("Auto-Start Gestures", self.gesture_toggle,
                                           "Enable gesture mode on launch"))
        
        layout.addWidget(gesture_card)
        
        # Battery & Power Settings
        battery_card = SettingsCard("🔋 Battery & Power")
        
        self.battery_alerts_toggle = SmoothToggleSwitch()
        self.battery_alerts_toggle.set_on(True, animate=False)
        self.battery_alerts_toggle.toggled.connect(self.battery_alerts_changed.emit)
        battery_card.add_option(SettingRow("Battery Alerts", self.battery_alerts_toggle,
                                           "Notify on low/critical/full battery"))
        
        layout.addWidget(battery_card)
        
        # Security Settings
        security_card = SettingsCard("🔒 Security")
        
        self.auto_lock_toggle = SmoothToggleSwitch()
        self.auto_lock_toggle.set_on(False, animate=False)
        self.auto_lock_toggle.toggled.connect(self.auto_lock_changed.emit)
        security_card.add_option(SettingRow("Auto-Lock", self.auto_lock_toggle,
                                            "Lock system after inactivity"))
        
        self.auto_lock_spin = QSpinBox()
        self.auto_lock_spin.setRange(1, 60)
        self.auto_lock_spin.setValue(5)
        self.auto_lock_spin.setSuffix(" min")
        self.auto_lock_spin.setStyleSheet(self._spinbox_style())
        self.auto_lock_spin.valueChanged.connect(self.auto_lock_timeout_changed.emit)
        security_card.add_option(SettingRow("Auto-Lock Timeout", self.auto_lock_spin))
        
        layout.addWidget(security_card)
        
        # Appearance Settings
        appearance_card = SettingsCard("🎨 Appearance")
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Cyberpunk Blue (Default)", "Dark Purple", "Matrix Green"])
        self.theme_combo.setStyleSheet(self._combo_style())
        self.theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        appearance_card.add_option(SettingRow("Theme", self.theme_combo, "UI color scheme"))
        
        self.excerpt_selector = QuantitySelector(value=5, min_val=1, max_val=20, suffix=" lines")
        self.excerpt_selector.valueChanged.connect(self.excerpt_limit_changed.emit)
        appearance_card.add_option(SettingRow("Chat Excerpt Limit", self.excerpt_selector, "Truncate messages longer than this"))
        
        layout.addWidget(appearance_card)

        # Integrations Settings
        self.integrations_card = SettingsCard("🔗 Integrations")
        
        self.google_status_label = QLabel("Not Connected")
        self.google_status_label.setStyleSheet("color: #ff9d00; font-weight: bold;")
        
        self.google_auth_btn = QPushButton("Connect Google Calendar")
        self.google_auth_btn.setStyleSheet(self._button_style())
        self.google_auth_btn.clicked.connect(self.google_calendar_login.emit)
        
        self.google_disconnect_btn = QPushButton("Disconnect")
        self.google_disconnect_btn.setStyleSheet(self._button_style().replace("rgba(0, 212, 255, 0.2)", "rgba(255, 50, 50, 0.2)"))
        self.google_disconnect_btn.clicked.connect(self.google_calendar_logout.emit)
        self.google_disconnect_btn.setVisible(False)
        
        self.integrations_card.add_option(SettingRow("Status", self.google_status_label))
        self.integrations_card.add_option(SettingRow("Google Account", self.google_auth_btn, "Link your calendar to JARVIS"))
        self.integrations_card.add_option(SettingRow("Action", self.google_disconnect_btn))
        
        layout.addWidget(self.integrations_card)
        
        layout.addStretch()
        
        scroll.setWidget(container)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _slider_style(self):
        return """
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 0.1);
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #00d4ff, stop:1 #00a0ff);
                border: 1px solid #00d4ff;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #00ffff;
            }
        """
    
    def _combo_style(self):
        return """
            QComboBox {
                background: rgba(10, 22, 40, 0.8);
                border: 1px solid rgba(0, 212, 255, 0.4);
                border-radius: 6px;
                padding: 6px 10px;
                color: #e5f6ff;
                min-width: 160px;
            }
            QComboBox:hover {
                border-color: rgba(0, 255, 255, 0.6);
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(10, 22, 40, 0.95);
                border: 1px solid rgba(0, 212, 255, 0.6);
                selection-background-color: rgba(0, 212, 255, 0.3);
                color: #e5f6ff;
            }
        """
    
    def _spinbox_style(self):
        return """
            QSpinBox {
                background: rgba(10, 22, 40, 0.8);
                border: 1px solid rgba(0, 212, 255, 0.4);
                border-radius: 6px;
                padding: 6px 10px;
                color: #e5f6ff;
                min-width: 80px;
            }
            QSpinBox:hover {
                border-color: rgba(0, 255, 255, 0.6);
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background: rgba(0, 212, 255, 0.2);
                border-radius: 3px;
                width: 20px;
                subcontrol-origin: border;
            }
            QSpinBox::up-button {
                subcontrol-position: top right;
            }
            QSpinBox::down-button {
                subcontrol-position: bottom right;
            }
            QSpinBox::up-arrow {
                image: url(none); /* Clear default */
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-bottom: 5px solid #00d4ff;
                width: 0;
                height: 0;
            }
            QSpinBox::down-arrow {
                image: url(none);
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #00d4ff;
                width: 0;
                height: 0;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: rgba(0, 255, 255, 0.3);
            }
        """
    
    def _button_style(self):
        return """
            QPushButton {
                background: rgba(0, 212, 255, 0.2);
                border: 1px solid rgba(0, 212, 255, 0.4);
                border-radius: 6px;
                padding: 8px 15px;
                color: #e5f6ff;
                font-weight: bold;
                min-width: 180px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.4);
                border-color: rgba(0, 255, 255, 0.6);
            }
            QPushButton:pressed {
                background: rgba(0, 212, 255, 0.6);
            }
        """

    def get_settings(self):
        """Get all current settings as a dict"""
        return {
            "tts_enabled": self.tts_toggle.isChecked(),
            "tts_voice": self.tts_voice_combo.currentText(),
            "tts_rate": self.tts_rate_slider.value(),
            "voice_auto_start": self.voice_toggle.isChecked(),
            "gesture_auto_start": self.gesture_toggle.isChecked(),
            "battery_alerts": self.battery_alerts_toggle.isChecked(),
            "auto_lock": self.auto_lock_toggle.isChecked(),
            "auto_lock_timeout": self.auto_lock_spin.value(),
            "theme": self.theme_combo.currentText(),
            "chat_excerpt_limit": self.excerpt_selector.value,
        }
    
    def set_settings(self, settings: dict):
        """Apply settings from a dict"""
        if "tts_enabled" in settings:
            self.tts_toggle.set_on(settings["tts_enabled"], animate=False)
        if "tts_voice" in settings:
            idx = self.tts_voice_combo.findText(settings["tts_voice"])
            if idx >= 0:
                self.tts_voice_combo.setCurrentIndex(idx)
        if "tts_rate" in settings:
            self.tts_rate_slider.setValue(settings["tts_rate"])
        if "voice_auto_start" in settings:
            self.voice_toggle.set_on(settings["voice_auto_start"], animate=False)
        if "gesture_auto_start" in settings:
            self.gesture_toggle.set_on(settings["gesture_auto_start"], animate=False)
        if "battery_alerts" in settings:
            self.battery_alerts_toggle.set_on(settings["battery_alerts"], animate=False)
        if "auto_lock" in settings:
            self.auto_lock_toggle.set_on(settings["auto_lock"], animate=False)
        if "auto_lock_timeout" in settings:
            self.auto_lock_spin.setValue(settings["auto_lock_timeout"])
        if "theme" in settings:
            idx = self.theme_combo.findText(settings["theme"])
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)
        if "chat_excerpt_limit" in settings:
            self.excerpt_selector.set_value(settings["chat_excerpt_limit"])

    def update_google_status(self, connected: bool, email: str = ""):
        """Update the Google Integration UI based on connection status"""
        if connected:
            self.google_status_label.setText(f"Connected: {email}")
            self.google_status_label.setStyleSheet("color: #00ffaa; font-weight: bold;")
            self.google_auth_btn.setText("Reconnect")
            self.google_disconnect_btn.setVisible(True)
        else:
            self.google_status_label.setText("Not Connected")
            self.google_status_label.setStyleSheet("color: #ff9d00; font-weight: bold;")
            self.google_auth_btn.setText("Connect Google Calendar")
            self.google_disconnect_btn.setVisible(False)
