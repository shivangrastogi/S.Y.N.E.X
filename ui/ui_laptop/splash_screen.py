import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QColor, QPalette

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')

class SplashWindow(QWidget):
    finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setFixedSize(600, 400)
        self.setup_ui()
        
        # Center on screen
        qr = self.frameGeometry()
        cp = self.screen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
        self.progress_val = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(30)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        # Container with dark tech background
        self.container = QWidget()
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            QWidget#container {
                background-color: #0a1628;
                border: 2px solid #00d4ff;
                border-radius: 15px;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(40, 40, 40, 40)
        container_layout.setSpacing(20)
        
        # Logo
        logo_label = QLabel()
        logo_pix = QPixmap(os.path.join(ASSETS_DIR, "logo.png"))
        if not logo_pix.isNull():
            logo_label.setPixmap(logo_pix.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(logo_label)
        
        # Title
        title_label = QLabel("JARVIS 2.0")
        title_label.setFont(QFont("Consolas", 32, QFont.Bold))
        title_label.setStyleSheet("color: #00d4ff; letter-spacing: 5px;")
        title_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(title_label)
        
        # System status
        self.status_label = QLabel("INITIALIZING CORE SYSTEMS...")
        self.status_label.setFont(QFont("Consolas", 10))
        self.status_label.setStyleSheet("color: #888888; letter-spacing: 2px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.status_label)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #00d4ff;
                border-radius: 3px;
            }
        """)
        container_layout.addWidget(self.progress_bar)
        
        layout.addWidget(self.container)

    def update_progress(self):
        self.progress_val += 1
        self.progress_bar.setValue(self.progress_val)
        
        # Dynamic status text
        if self.progress_val == 20:
            self.status_label.setText("LOADING AUDIO ENGINE...")
        elif self.progress_val == 40:
            self.status_label.setText("CALIBRATING SENSORS...")
        elif self.progress_val == 70:
            self.status_label.setText("ESTABLISHING NEURAL LINK...")
        elif self.progress_val == 90:
            self.status_label.setText("SYSTEMS READY.")
            
        if self.progress_val >= 100:
            self.timer.stop()
            self.finished.emit()
