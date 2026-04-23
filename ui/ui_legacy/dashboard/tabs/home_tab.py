# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/dashboard/tabs/home_tab.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QFrame
from PyQt5.QtCore import Qt

class HomeTab(QWidget):
    """
    Main Dashboard landing page - shows system metrics and health.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        header = QLabel("System Overview")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(header)

        # Grid for Stats Cards
        grid = QGridLayout()
        grid.setSpacing(20)

        self.cpu_card = self._create_card("CPU Usage", "0%")
        self.ram_card = self._create_card("RAM Usage", "0%")
        self.state_card = self._create_card("Engine State", "IDLE")
        self.uptime_card = self._create_card("System Uptime", "00:00:00")

        grid.addWidget(self.cpu_card, 0, 0)
        grid.addWidget(self.ram_card, 0, 1)
        grid.addWidget(self.state_card, 1, 0)
        grid.addWidget(self.uptime_card, 1, 1)

        layout.addLayout(grid)
        layout.addStretch()

    def _create_card(self, title, value):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #2b2d31;
                border-radius: 10px;
                padding: 20px;
            }
            QLabel#Title { color: #b0b3b8; font-size: 14px; }
            QLabel#Value { color: #00bfff; font-size: 28px; font-weight: bold; margin-top: 10px; }
        """)
        l = QVBoxLayout(card)
        
        t_lbl = QLabel(title)
        t_lbl.setObjectName("Title")
        
        v_lbl = QLabel(value)
        v_lbl.setObjectName("Value")
        
        l.addWidget(t_lbl)
        l.addWidget(v_lbl)
        
        # Store references for updates
        card.value_label = v_lbl
        return card
