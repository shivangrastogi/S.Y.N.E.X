from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
from PyQt5.QtCore import Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QIcon, QPainter, QColor, QLinearGradient, QBrush, QPen

class SidebarButton(QPushButton):
    def __init__(self, label, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.setText(f"  {label.upper()}")
        self.setCheckable(True)
        self.setMinimumHeight(60)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #555;
                border: none;
                text-align: left;
                padding-left: 25px;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 2px;
                font-family: 'Segoe UI', sans-serif;
            }
            QPushButton:hover {
                color: #00f2ff;
                background-color: rgba(0, 242, 255, 5);
            }
            QPushButton:checked {
                color: #00f2ff;
                background-color: rgba(0, 242, 255, 15);
            }
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            # Neon selection bar
            painter.setBrush(QColor("#00f2ff"))
            painter.setPen(Qt.NoPen)
            painter.drawRect(0, 15, 3, 30)
            # Subtle glow
            grad = QLinearGradient(0, 0, 50, 0)
            grad.setColorAt(0, QColor(0, 242, 255, 40))
            grad.setColorAt(1, QColor(0, 242, 255, 0))
            painter.fillRect(3, 0, 50, self.height(), QBrush(grad))

class StarkSidebar(QFrame):
    tab_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setObjectName("Sidebar")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 40, 0, 40)
        layout.setSpacing(5)
        
        # FUI Header
        logo = QLabel("A.E.R.I.S // HUB")
        logo.setStyleSheet("color: #00f2ff; font-weight: bold; font-size: 14px; letter-spacing: 5px; padding: 25px;")
        layout.addWidget(logo)
        
        # Decorative divider
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: rgba(0, 242, 255, 30); margin: 0 25px 20px 25px;")
        layout.addWidget(line)
        
        self.buttons = []
        self._add_tab("Core Hub", 0)
        self._add_tab("Automation", 1)
        self._add_tab("Image Vault", 2)
        self._add_tab("Neural Setup", 3)
        
        layout.addStretch()
        
        # Technical Readout (Fake Data)
        readout = QLabel("OS_REL: V2.0.0_STARK\nSTATUS: ENCRYPTED\nUPLINK: ACTIVE")
        readout.setStyleSheet("color: #222; font-size: 9px; font-family: monospace; padding: 25px; line-height: 15px;")
        layout.addWidget(readout)

    def _add_tab(self, label, index):
        btn = SidebarButton(label, index, self)
        btn.clicked.connect(lambda: self._on_btn_clicked(index))
        self.layout().addWidget(btn)
        self.buttons.append(btn)
        if index == 0:
            btn.setChecked(True)

    def _on_btn_clicked(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.tab_changed.emit(index)

    def paintEvent(self, event):
        painter = QPainter(self)
        # Gradient background
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0, QColor(10, 12, 15))
        grad.setColorAt(1, QColor(5, 7, 10))
        painter.fillRect(self.rect(), QBrush(grad))
        
        # Right border glow
        painter.setPen(QPen(QColor(0, 242, 255, 20), 1))
        painter.drawLine(self.width()-1, 0, self.width()-1, self.height())
