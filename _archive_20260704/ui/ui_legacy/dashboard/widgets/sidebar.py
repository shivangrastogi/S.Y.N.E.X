# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/dashboard/widgets/sidebar.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QFont

class Sidebar(QWidget):
    """
    Vertical navigation sidebar for the A.E.R.I.S Dashboard.
    """
    tab_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setStyleSheet("""
            Sidebar {
                background-color: #1e1f22;
                border-right: 1px solid #3a3b3e;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: #b0b3b8;
                text-align: left;
                padding: 12px 20px;
                font-size: 14px;
                border-radius: 0px;
            }
            QPushButton:hover {
                background-color: #2b2d31;
                color: #ffffff;
            }
            QPushButton[active="true"] {
                background-color: #35373c;
                color: #00bfff;
                border-left: 3px solid #00bfff;
            }
            QLabel#LogoLabel {
                color: #00bfff;
                font-weight: bold;
                font-size: 18px;
                margin: 20px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo/Title
        logo = QLabel("A.E.R.I.S")
        logo.setObjectName("LogoLabel")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #3a3b3e;")
        layout.addWidget(line)

        # Nav Buttons
        self.buttons = []
        nav_items = [
            ("🏠 Dashboard", 0),
            ("📅 Automations", 1),
            ("🖼️ Gallery", 2),
            ("⚙️ Settings", 3)
        ]

        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=index: self._on_clicked(idx))
            layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addStretch()

        # Shutdown Button at bottom
        self.exit_btn = QPushButton("🛑 Exit System")
        self.exit_btn.setStyleSheet("color: #ff4444;")
        self.exit_btn.clicked.connect(lambda: event_bus.emit("system.shutdown_requested", {}))
        layout.addWidget(self.exit_btn)

        self._set_active(0)

    def _on_clicked(self, index):
        self._set_active(index)
        self.tab_changed.emit(index)

    def _set_active(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setProperty("active", i == index)
            btn.setStyle(btn.style()) # Refresh style
