# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/dashboard/tabs/settings_tab.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QComboBox, QCheckBox, QLineEdit, QPushButton, QFormLayout
from core.state_manager import state_manager
from memory.storage import storage
from utils.logger import logger

class SettingsTab(QWidget):
    """
    Settings view for A.E.R.I.S - controls voice, profile, and startup.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        header = QLabel("System Settings")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(15)

        # Profile Section
        self.user_name = QLineEdit(storage.get_profile_value("user_name", "Shivang"))
        self.ai_name = QLineEdit(storage.get_profile_value("assistant_name", "A.E.R.I.S"))
        
        # Voice Section
        self.voice_select = QComboBox()
        self.voice_select.addItems(["hi-IN-MadhurNeural", "en-IN-PrabhatNeural", "en-US-GuyNeural"])
        # Current logic in tts_worker uses hi-IN-MadhurNeural by default
        self.voice_select.setCurrentText("hi-IN-MadhurNeural")

        # Startup Section
        self.startup_check = QCheckBox("Launch A.E.R.I.S on Windows Startup")
        
        form.addRow(QLabel("User Name:"), self.user_name)
        form.addRow(QLabel("Assistant Name:"), self.ai_name)
        form.addRow(QLabel("Voice Model:"), self.voice_select)
        form.addRow(self.startup_check)

        layout.addLayout(form)
        
        layout.addStretch()

        # Save Button
        self.save_btn = QPushButton("Save All Changes")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #00bfff;
                color: #ffffff;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #0099cc; }
        """)
        self.save_btn.clicked.connect(self._save_settings)
        layout.addWidget(self.save_btn)

    def _save_settings(self):
        storage.set_profile_value("user_name", self.user_name.text())
        storage.set_profile_value("assistant_name", self.ai_name.text())
        logger.info("Dashboard Settings: Profile updated.")
        # Trigger an event so the UI updates elsewhere if needed
        from core.event_bus import event_bus
        event_bus.emit("ui.settings_updated", {"user_name": self.user_name.text()})
