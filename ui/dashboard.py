import sys
import os
import threading
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt5.QtGui import QPixmap, QImage, QPainter
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.main_engine import JarvisMainEngine
from utils.monitor import SystemMonitor

class JarvisWorker(QThread):
    """Thread to run the main Jarvis voice loop without freezing the GUI."""
    response_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)

    def run(self):
        engine = JarvisMainEngine()
        # Override the speak method to send text back to the GUI
        original_speak = engine.tts.speak
        def gui_speak(text):
            self.response_signal.emit(text)
            original_speak(text)
        
        engine.tts.speak = gui_speak
        engine.run()

class JarvisDashboard(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Jarvis v3.0 - A.E.R.I.S")
        self.setMinimumSize(1000, 700)
        
        # Asset Loading
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        self.bg_path = os.path.join(assets_dir, "background.png")
        self.logo_path = os.path.join(assets_dir, "center_logo.png")
        self.background_image = QImage(self.bg_path)
        self.logo_pixmap = QPixmap(self.logo_path)
        
        self.setup_ui()
        self.start_backend()

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # 1. System Status Bar (Top)
        self.status_layout = QHBoxLayout()
        self.battery_label = QLabel("Battery: --%")
        self.cpu_label = QLabel("CPU: --%")
        for label in [self.battery_label, self.cpu_label]:
            label.setStyleSheet("color: white; font-size: 14px; font-weight: bold; background: rgba(0,0,0,50); padding: 5px; border-radius: 5px;")
            self.status_layout.addWidget(label)
        self.status_layout.addStretch()
        self.main_layout.addLayout(self.status_layout)

        self.main_layout.addStretch()

        # 2. Center Logo
        self.center_layout = QHBoxLayout()
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.center_layout.addWidget(self.logo_label)
        self.main_layout.addLayout(self.center_layout)

        self.main_layout.addStretch()

        # 3. Jarvis Response Area (Bottom)
        self.jarvis_response = QLabel("READY FOR COMMANDS")
        self.jarvis_response.setAlignment(Qt.AlignCenter)
        self.jarvis_response.setStyleSheet("""
            color: cyan; 
            font-size: 24px; 
            font-family: 'Consolas';
            background-color: rgba(0, 0, 0, 150); 
            border-radius: 10px;
            padding: 15px;
            margin: 20px;
        """)
        self.main_layout.addWidget(self.jarvis_response)

    def start_backend(self):
        # Start Voice Engine in Background
        self.worker = JarvisWorker()
        self.worker.response_signal.connect(self.update_response)
        self.worker.start()
        
        # Start System Monitoring
        self.timer = threading.Timer(5.0, self.update_system_stats)
        self.timer.start()

    def update_response(self, text):
        self.jarvis_response.setText(text.upper())

    def update_system_stats(self):
        import psutil
        battery = psutil.sensors_battery()
        self.battery_label.setText(f"BATTERY: {battery.percent if battery else '??'}%")
        self.cpu_label.setText(f"CPU: {psutil.cpu_percent()}%")
        # Loop the timer
        threading.Timer(10.0, self.update_system_stats).start()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self.background_image.isNull():
            scaled_bg = self.background_image.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (self.width() - scaled_bg.width()) // 2
            y = (self.height() - scaled_bg.height()) // 2
            painter.drawImage(x, y, scaled_bg)

    def resizeEvent(self, event):
        new_logo_dimension = int(min(self.width(), self.height()) * 0.7)
        if not self.logo_pixmap.isNull():
            scaled_logo = self.logo_pixmap.scaled(new_logo_dimension, new_logo_dimension, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_logo)
        super().resizeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JarvisDashboard()
    window.show()
    sys.exit(app.exec_())
