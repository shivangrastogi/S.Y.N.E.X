from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QScrollArea)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from tools.storage_manager import StorageManager

class StorageModal(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS Storage Hub")
        self.setMinimumSize(450, 500)
        self.setStyleSheet("background-color: #0a1628; color: #e5f6ff;")
        self.storage_manager = StorageManager()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Storage Overview")
        title.setStyleSheet("color: #00d4ff; font-size: 20px; font-weight: bold; font-family: 'Consolas';")
        layout.addWidget(title)

        subtitle = QLabel("Here's how JARVIS is using your disk space.")
        subtitle.setStyleSheet("color: #9ad4ff; font-size: 13px;")
        layout.addWidget(subtitle)

        # Content Area
        self.content_container = QFrame()
        self.content_container.setStyleSheet("""
            QFrame {
                background: rgba(8, 18, 32, 0.85);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-radius: 12px;
            }
        """)
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setSpacing(20)
        content_layout.setContentsMargins(20, 20, 20, 20)

        data = self.storage_manager.get_storage_distribution()
        
        for category, info in data.items():
            if category == "Total Usage":
                continue
            
            row = QFrame()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)

            header_layout = QHBoxLayout()
            cat_label = QLabel(category)
            cat_label.setStyleSheet("color: #00d4ff; font-weight: bold; font-size: 15px;")
            
            size_label = QLabel(info['size'])
            size_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 15px;")
            
            header_layout.addWidget(cat_label)
            header_layout.addStretch()
            header_layout.addWidget(size_label)
            row_layout.addLayout(header_layout)

            desc_label = QLabel(info['description'])
            desc_label.setStyleSheet("color: #7fd7ff; font-size: 12px;")
            desc_label.setWordWrap(True)
            row_layout.addWidget(desc_label)

            content_layout.addWidget(row)

        layout.addWidget(self.content_container)

        # Total Footer
        total_frame = QFrame()
        total_frame.setStyleSheet("background: rgba(0, 212, 255, 0.1); border-radius: 8px; border: 1px solid rgba(0, 212, 255, 0.3);")
        total_layout = QHBoxLayout(total_frame)
        total_layout.setContentsMargins(15, 10, 15, 10)
        
        total_text = QLabel("Total Space Used")
        total_text.setStyleSheet("color: #e5f6ff; font-weight: bold;")
        
        total_val = QLabel(data['Total Usage'])
        total_val.setStyleSheet("color: #00ffaa; font-weight: bold; font-size: 16px;")
        
        total_layout.addWidget(total_text)
        total_layout.addStretch()
        total_layout.addWidget(total_val)
        layout.addWidget(total_frame)

        # Close Button
        close_btn = QPushButton("Done")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0,212,255,0.2), stop:1 rgba(0,140,255,0.2));
                border: 1px solid rgba(0, 212, 255, 0.4);
                border-radius: 6px;
                padding: 10px;
                color: #00d4ff;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover {
                background: rgba(0, 212, 255, 0.3);
                border-color: #00ffff;
            }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
