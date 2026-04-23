from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal

class ImagesTab(QWidget):
    style_changed = pyqtSignal(str)
    magic_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel("IMAGES TAB (Coming Soon)")
        label.setStyleSheet("color: rgba(207, 232, 255, 0.5); font-size: 18px; letter-spacing: 2px;")
        layout.addWidget(label)

    def add_placeholder(self, prompt):
        pass

    def on_generation_finished(self, metadata):
        pass

    def on_generation_progress(self, percentage, eta):
        pass
