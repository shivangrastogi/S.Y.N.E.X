
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon

class NotificationItem(QFrame):
    def __init__(self, app_name, title, text, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            NotificationItem {
                background-color: #2A2D3E;
                border-radius: 8px;
                margin-bottom: 8px;
            }
            QLabel { color: #E0E0E0; }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header (App Name + Close)
        header = QHBoxLayout()
        lbl_app = QLabel(app_name)
        lbl_app.setStyleSheet("font-weight: bold; color: #00BCD4;")
        header.addWidget(lbl_app)
        header.addStretch()
        
        btn_close = QPushButton("×")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet("border: none; color: #888; font-weight: bold;")
        btn_close.clicked.connect(self.hide) # Logic to remove from list could be added
        header.addWidget(btn_close)
        
        layout.addLayout(header)
        
        # Content
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl_title)
        
        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)
        lbl_text.setStyleSheet("color: #AAA;")
        layout.addWidget(lbl_text)

class NotificationCenter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QLabel("Notifications")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(self.container)
        layout.addWidget(scroll)
        
        # Empty State
        self.lbl_empty = QLabel("No new notifications")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("color: #666; margin-top: 20px;")
        self.container_layout.addWidget(self.lbl_empty)

        # Load existing
        self.load_history()

    def load_history(self):
        """Load notifications from the backend manager on startup"""
        try:
            from backend.mobile_hub.features.notifications import NotificationManager
            manager = NotificationManager()
            history = manager.get_all()
            for notif in reversed(history): # Reversed because we insert at index 0 in add_notification
                self.add_notification(
                    notif.get("app_name") or notif.get("app", "Unknown"),
                    notif.get("title", ""),
                    notif.get("text", "")
                )
        except Exception as e:
            print(f"Error loading notification history: {e}")

    def add_notification(self, app, title, text):
        self.lbl_empty.hide()
        item = NotificationItem(app, title, text)
        self.container_layout.insertWidget(0, item) # Add to top
