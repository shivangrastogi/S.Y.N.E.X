# auth/loading_window.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from .engine_manager import engine_manager  # Import the manager


class LoadingWindow(QWidget):
    # Signal to tell MainApp we are done
    models_loaded_signal = pyqtSignal()

    def __init__(self, user_data):
        super().__init__()
        # Store user_data to pass it to the chat window later
        self.user_data = user_data

        self.setWindowTitle("Loading JARVIS")
        self.setGeometry(500, 300, 300, 150)

        layout = QVBoxLayout()
        self.label = QLabel("JARVIS is loading, please wait...")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)

        # Timer to check if models are loaded
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_if_loaded)
        self.check_timer.start(250)  # Check 4 times per second

    def check_if_loaded(self):
        if engine_manager.is_models_loaded():
            self.check_timer.stop()
            self.models_loaded_signal.emit()  # Tell MainApp we're ready