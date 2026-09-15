# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/dashboard/tabs/gallery_tab.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QGridLayout, QFrame
from PyQt5.QtCore import Qt

class GalleryTab(QWidget):
    """
    Image Gallery view for A.E.R.I.S - shows generated images.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        header = QLabel("Generated Image Gallery")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(header)

        # Scroll Area for Images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")
        
        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setSpacing(15)
        
        # Placeholder / Empty state
        self.empty_label = QLabel("No images generated yet. Ask A.E.R.I.S to create something!")
        self.empty_label.setStyleSheet("color: #b0b3b8; font-style: italic;")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.grid.addWidget(self.empty_label, 0, 0)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def add_image(self, path):
        # Implementation for adding an actual image thumbnail to the grid
        pass
