from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QScrollArea, QFrame, QLineEdit, QComboBox, QPushButton
from PyQt5.QtCore import Qt
from memory.storage import storage

class SettingsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLabel { color: #888; font-size: 12px; }
            QLineEdit { 
                background-color: #1a1c22; 
                border: 1px solid #333; 
                color: #e0e0e0; 
                padding: 10px; 
                border-radius: 5px;
                font-size: 14px;
            }
            QComboBox {
                background-color: #1a1c22;
                border: 1px solid #333;
                color: #e0e0e0;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton#SaveBtn {
                background-color: #00f2ff;
                color: #000;
                font-weight: bold;
                border: none;
                padding: 12px;
                border-radius: 5px;
                margin-top: 20px;
            }
            QPushButton#SaveBtn:hover {
                background-color: #00d2df;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)
        
        # Header
        header = QLabel("CORE CONFIGURATION")
        header.setStyleSheet("color: #00f2ff; font-size: 18px; font-weight: bold; letter-spacing: 1px;")
        main_layout.addWidget(header)
        
        # Settings Groups
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setSpacing(30)
        
        # 1. Identity
        id_group = self._create_group("IDENTITY")
        self.user_name = QLineEdit(storage.get_profile_value("user_name", "User"))
        self.assistant_name = QLineEdit(storage.get_profile_value("assistant_name", "A.E.R.I.S"))
        
        id_group.layout().addWidget(QLabel("PRIMARY USER NAME"))
        id_group.layout().addWidget(self.user_name)
        id_group.layout().addWidget(QLabel("ASSISTANT DESIGNATION"))
        id_group.layout().addWidget(self.assistant_name)
        layout.addWidget(id_group)
        
        # 2. Voice Engine
        voice_group = self._create_group("VOICE ENGINE")
        self.voice_model = QComboBox()
        self.voice_model.addItems(["Native (Offline)", "Edge-TTS (Online/High Quality)", "XTTS v2 (Premium/Bilingual)"])
        
        # Select current
        current_tts = storage.get_profile_value("tts_provider", "native")
        idx = 0
        if current_tts == "edge": idx = 1
        elif current_tts == "xtts": idx = 2
        self.voice_model.setCurrentIndex(idx)
        
        voice_group.layout().addWidget(QLabel("TTS PROVIDER"))
        voice_group.layout().addWidget(self.voice_model)
        layout.addWidget(voice_group)
        
        layout.addStretch()
        
        # Save Button
        save_btn = QPushButton("SYNCHRONIZE CORE")
        save_btn.setObjectName("SaveBtn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn)
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _create_group(self, title):
        group = QFrame()
        group.setStyleSheet("background-color: #16181c; border-radius: 10px; padding: 20px;")
        layout = QVBoxLayout(group)
        t = QLabel(title)
        t.setStyleSheet("color: #00f2ff; font-size: 10px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(t)
        return group

    def _save_settings(self):
        # Update storage
        storage.set_profile_value("user_name", self.user_name.text())
        storage.set_profile_value("assistant_name", self.assistant_name.text())
        
        providers = ["native", "edge", "xtts"]
        storage.set_profile_value("tts_provider", providers[self.voice_model.currentIndex()])
        
        from core.event_bus import event_bus
        event_bus.emit("system.profile_updated", {})
        
        # Visual feedback on button
        btn = self.findChild(QPushButton, "SaveBtn")
        btn.setText("CORE SYNCHRONIZED ✓")
        btn.setStyleSheet("background-color: #2ecc71; color: #fff;")
