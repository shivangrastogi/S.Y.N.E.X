
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

class CallPopup(QWidget):
    # Signals to Main Controller
    accepted = pyqtSignal()
    declined = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.caller_name = "Unknown"
        self.caller_number = ""
        
        self.init_ui()
        self.hide()

    def init_ui(self):
        # Main Container with shadow
        container = QFrame(self)
        container.setStyleSheet("""
            QFrame {
                background-color: #1E1E2E;
                border-radius: 16px;
                border: 1px solid #333;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        container.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(container)
        
        # Header
        self.lbl_status = QLabel("Incoming Call...")
        self.lbl_status.setStyleSheet("color: #AAA; font-size: 12px;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)
        
        # Caller Info
        self.lbl_name = QLabel(self.caller_name)
        self.lbl_name.setStyleSheet("color: #FFF; font-size: 20px; font-weight: bold;")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_name)
        
        self.lbl_number = QLabel(self.caller_number)
        self.lbl_number.setStyleSheet("color: #DDD; font-size: 14px;")
        self.lbl_number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_number)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_decline = QPushButton("Decline")
        btn_decline.setStyleSheet("""
            QPushButton {
                background-color: #FF5252;
                color: white;
                border-radius: 20px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #FF1744; }
        """)
        btn_decline.clicked.connect(self.on_decline)
        
        btn_accept = QPushButton("Accept")
        btn_accept.setObjectName("btn_accept")
        btn_accept.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 20px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #00E676; }
        """)
        btn_accept.clicked.connect(self.on_accept)
        self.btn_accept = btn_accept
        self.btn_decline = btn_decline
        
        btn_layout.addWidget(btn_decline)
        btn_layout.addWidget(btn_accept)
        layout.addLayout(btn_layout)
        
        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(container)
        self.resize(300, 180)

    def show_call(self, name, number):
        self.caller_name = name
        self.caller_number = number
        self.lbl_name.setText(name)
        self.lbl_number.setText(number)
        self.lbl_status.setText("Incoming Call...")
        self.btn_accept.setVisible(True)
        self.btn_decline.setText("Decline")
        
        # Position at top right
        screen = self.screen().geometry()
        self.move(screen.width() - 320, 100)
        
        self.show()
        self.raise_()

    def update_status(self, status):
        """Update popup for active call state"""
        if status.lower() == "active":
            self.lbl_status.setText("Call Active")
            self.btn_accept.setVisible(False)
            self.btn_decline.setText("End Call")
            self.btn_decline.setStyleSheet("""
                QPushButton {
                    background-color: #FF5252;
                    color: white;
                    border-radius: 20px;
                    padding: 10px 40px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #FF1744; }
            """)
        elif status.lower() == "ringing":
             self.lbl_status.setText("Incoming Call...")
             self.btn_accept.setVisible(True)
             self.btn_decline.setText("Decline")

    def on_accept(self):
        self.accepted.emit()

    def on_decline(self):
        self.declined.emit()
