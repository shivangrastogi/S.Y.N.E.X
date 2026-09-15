from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush

class ChatPanel(QWidget):
    """
    Phase 8: The text-based history and manual override input panel.
    Expands out from the Orbital Indicator.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(350)
        self.setFixedHeight(400)
        
        self.setStyleSheet("""
            QWidget#ChatPanelContainer {
                background-color: rgba(5, 7, 10, 245);
                border: 1px solid rgba(0, 242, 255, 60);
                border-radius: 4px;
                color: #e0e0e0;
                font-family: 'Segoe UI Semibold', sans-serif;
            }
            QTextEdit {
                border: none;
                background: transparent;
                padding: 15px;
                font-size: 13px;
                line-height: 1.6;
                color: #e0e0e0;
            }
            QLineEdit {
                border: 1px solid rgba(0, 242, 255, 30);
                background-color: rgba(0, 0, 0, 180);
                padding: 12px;
                margin: 10px 15px 15px 15px;
                color: #00f2ff;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border-radius: 2px;
            }
            QLineEdit:focus {
                border: 1px solid #00f2ff;
                background-color: rgba(0, 242, 255, 15);
            }
            QLabel#HeaderTitle {
                color: #00f2ff;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 3px;
                text-transform: uppercase;
                opacity: 0.8;
            }
        """)

        self.setObjectName("ChatPanelContainer")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Top Header Area
        header_area = QWidget()
        header_area.setFixedHeight(40)
        h_layout = QHBoxLayout(header_area)
        h_layout.setContentsMargins(20, 10, 10, 0)
        
        header_label = QLabel("NEURAL_LINK :: FEED")
        header_label.setObjectName("HeaderTitle")
        h_layout.addWidget(header_label)
        
        h_layout.addStretch()
        
        self.minimize_btn = QPushButton("—")
        self.minimize_btn.setFixedSize(20, 20)
        self.minimize_btn.setCursor(Qt.PointingHandCursor)
        self.minimize_btn.setToolTip("Minimize to Orb")
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #333;
                color: #888;
                border-radius: 4px;
                font-size: 10px;
            }
            QPushButton:hover { color: #f39c12; border: 1px solid #f39c12; background-color: rgba(243, 156, 18, 10); }
        """)
        self.minimize_btn.clicked.connect(self._on_minimize_requested)
        h_layout.addWidget(self.minimize_btn)
        
        self.expand_btn = QPushButton("⇱")
        self.expand_btn.setFixedSize(20, 20)
        self.expand_btn.setCursor(Qt.PointingHandCursor)
        self.expand_btn.setToolTip("Open Full Stark Hub")
        self.expand_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #333;
                color: #888;
                border-radius: 4px;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                border: 1px solid #00f2ff;
                color: #00f2ff;
                background-color: rgba(0, 242, 255, 10);
            }
        """)
        self.expand_btn.clicked.connect(self._on_expand_requested)
        h_layout.addWidget(self.expand_btn)
        
        layout.addWidget(header_area)
        
        self.history_area = QTextEdit()
        self.history_area.setReadOnly(True)
        self.history_area.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(self.history_area)
        
        # Manual fallback input
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a command or press 'Ctrl+Space'...")
        layout.addWidget(self.input_field)

        # Partial Transcript Label (Phase 1 Streaming)
        self.partial_label = QLabel("")
        self.partial_label.setStyleSheet("color: rgba(0, 242, 255, 100); font-style: italic; font-size: 11px; margin: 0 15px 5px 15px;")
        layout.addWidget(self.partial_label)

    def set_partial_text(self, text: str):
        """Updates the transient 'typing' feedback."""
        if text:
            self.partial_label.setText(f"User (typing): {text}...")
        else:
            self.partial_label.setText("")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # --- 1. Background Glass Effect ---
        from PyQt5.QtGui import QLinearGradient, QBrush
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(0, 242, 255, 10))
        grad.setColorAt(0.5, QColor(0, 0, 0, 0))
        grad.setColorAt(1, QColor(0, 242, 255, 5))
        painter.fillRect(self.rect(), QBrush(grad))
        
        # --- 2. Technical Outer Border ---
        border_color = QColor(0, 242, 255, 40)
        painter.setPen(QPen(border_color, 1))
        painter.drawRect(0, 0, w-1, h-1)
        
        # --- 3. Corner Brackets (MK-II) ---
        accent_color = QColor(0, 242, 255, 180)
        pen = QPen(accent_color, 2)
        painter.setPen(pen)
        
        l = 25 # length
        s = 5  # gap
        
        # TL
        painter.drawLine(0, 0, l, 0)
        painter.drawLine(0, 0, 0, l)
        # TR
        painter.drawLine(w-l, 0, w, 0)
        painter.drawLine(w, 0, w, l)
        # BL
        painter.drawLine(0, h-l, 0, h)
        painter.drawLine(0, h, l, h)
        # BR
        painter.drawLine(w-l, h, w, h)
        painter.drawLine(w, h-l, w, h)

        # --- 4. Sub-accent markings ---
        painter.setPen(QPen(accent_color, 1))
        painter.setOpacity(0.4)
        # Small notches at midpoints
        # Left
        painter.drawLine(0, h//2 - 10, 0, h//2 + 10)
        # Right
        painter.drawLine(w-1, h//2 - 10, w-1, h//2 + 10)
        # Top
        painter.drawLine(w//2 - 20, 0, w//2 + 20, 0)
        painter.setOpacity(1.0)

    def _on_minimize_requested(self):
        if self.parent() and hasattr(self.parent(), '_collapse_panel'):
            self.parent()._collapse_panel()

    def append_message(self, sender: str, text: str, color: str = "#e0e0e0"):
        """Safely appends to the chat UI from the event bridge."""
        html = f"<div style='margin-bottom: 8px;'><strong style='color:{color};'>{sender}:</strong> {text}</div>"
        self.history_area.append(html)
        
        # Auto-scroll to bottom
        scrollbar = self.history_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_expand_requested(self):
        from core.event_bus import event_bus
        event_bus.emit("ui.request_expand_hub", {})
        # Optionally hide self
        if self.parent() and hasattr(self.parent(), 'hide'):
             self.parent().hide()

    def get_input_field(self) -> QLineEdit:
        return self.input_field
