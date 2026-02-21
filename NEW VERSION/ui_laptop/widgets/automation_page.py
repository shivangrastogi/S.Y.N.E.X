# Path: d:\New folder (2) - JARVIS\ui_laptop\widgets\automation_page.py
# File: ui_laptop/widgets/automation_page.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QPushButton, QLineEdit, QTextEdit, QComboBox, QStackedWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap
import os

class AutomationPage(QWidget):
    """
    Unified Automation Interface for JARVIS.
    Handles messaging and social media postings.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("automationPage")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)
        
        # Header Section
        header = QHBoxLayout()
        title = QLabel("AUTOMATION")
        title.setObjectName("dashboardTitle")
        title.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        
        status = QLabel("AUTO-PILOT ACTIVE  •  MULTI-PLATFORM")
        status.setObjectName("dashboardStatus")
        status.setFont(QFont("Consolas", 9))
        header.addWidget(status)
        layout.addLayout(header)
        
        # Sub-tab Navigation
        tab_nav = QHBoxLayout()
        tab_nav.setSpacing(10)
        
        self.msg_tab_btn = QPushButton("MESSAGING")
        self.post_tab_btn = QPushButton("POSTINGS")
        
        for btn in [self.msg_tab_btn, self.post_tab_btn]:
            btn.setObjectName("subTabButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(140)
            tab_nav.addWidget(btn)
            
        self.msg_tab_btn.clicked.connect(lambda: self.set_tab(0))
        self.post_tab_btn.clicked.connect(lambda: self.set_tab(1))
        
        tab_nav.addStretch()
        layout.addLayout(tab_nav)
        
        # Content Area (Stacked)
        self.tabs = QStackedWidget()
        
        # --- Messaging Tab ---
        msg_page = QWidget()
        msg_layout = QVBoxLayout(msg_page)
        msg_layout.setContentsMargins(0, 10, 0, 0)
        
        msg_card = QFrame()
        msg_card.setObjectName("panelCard")
        msg_form = QVBoxLayout(msg_card)
        msg_form.setSpacing(15)
        
        msg_title = QLabel("SEND UNIFIED MESSAGE")
        msg_title.setObjectName("panelTitle")
        msg_form.addWidget(msg_title)
        
        # Platform Selection
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("PLATFORM:"))
        self.msg_platform = QComboBox()
        self.msg_platform.addItems(["WhatsApp", "Email"])
        self.msg_platform.setObjectName("automationCombo")
        row1.addWidget(self.msg_platform, 1)
        msg_form.addLayout(row1)
        
        # Recipient
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("RECIPIENT:"))
        self.msg_recipient = QLineEdit()
        self.msg_recipient.setPlaceholderText("Name or Phone Number...")
        self.msg_recipient.setObjectName("automationInput")
        row2.addWidget(self.msg_recipient, 1)
        msg_form.addLayout(row2)
        
        # Message Body
        msg_form.addWidget(QLabel("MESSAGE:"))
        self.msg_body = QTextEdit()
        self.msg_body.setPlaceholderText("Type your message here...")
        self.msg_body.setObjectName("automationText")
        self.msg_body.setMaximumHeight(150)
        msg_form.addWidget(self.msg_body)
        
        # Send Button
        self.send_msg_btn = QPushButton("EXECUTE SEND")
        self.send_msg_btn.setObjectName("executeButton")
        self.send_msg_btn.clicked.connect(self._on_send_msg)
        msg_form.addWidget(self.send_msg_btn)
        
        msg_layout.addWidget(msg_card)
        msg_layout.addStretch()
        
        # --- Postings Tab ---
        post_page = QWidget()
        post_layout = QVBoxLayout(post_page)
        post_layout.setContentsMargins(0, 10, 0, 0)
        
        post_card = QFrame()
        post_card.setObjectName("panelCard")
        post_form = QVBoxLayout(post_card)
        post_form.setSpacing(15)
        
        post_title = QLabel("SOCIAL MEDIA POSTING")
        post_title.setObjectName("panelTitle")
        post_form.addWidget(post_title)
        
        # Platform Selection
        row_p1 = QHBoxLayout()
        row_p1.addWidget(QLabel("PLATFORM:"))
        self.post_platform = QComboBox()
        self.post_platform.addItems(["Instagram", "Twitter / X", "Facebook", "LinkedIn"])
        self.post_platform.setObjectName("automationCombo")
        row_p1.addWidget(self.post_platform, 1)
        post_form.addLayout(row_p1)
        
        # Post Content
        post_form.addWidget(QLabel("CONTENT:"))
        self.post_content = QTextEdit()
        self.post_content.setPlaceholderText("What's on your mind?...")
        self.post_content.setObjectName("automationText")
        self.post_content.setMaximumHeight(150)
        post_form.addWidget(self.post_content)
        
        # Action Buttons
        btn_row = QHBoxLayout()
        self.post_now_btn = QPushButton("POST NOW")
        self.post_now_btn.setObjectName("executeButton")
        self.post_now_btn.clicked.connect(self._on_post_now)
        
        self.schedule_btn = QPushButton("SCHEDULE")
        self.schedule_btn.setObjectName("actionButtonSecondary")
        
        btn_row.addWidget(self.post_now_btn, 1)
        btn_row.addWidget(self.schedule_btn, 1)
        post_form.addLayout(btn_row)
        
        post_layout.addWidget(post_card)
        post_layout.addStretch()
        
        self.tabs.addWidget(msg_page)
        self.tabs.addWidget(post_page)
        layout.addWidget(self.tabs, 1)
        
        self.set_tab(0) # Default to messaging
        
        self.setStyleSheet("""
            #subTabButton {
                background-color: rgba(10, 22, 40, 0.5);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-bottom: 2px solid transparent;
                color: rgba(207, 232, 255, 0.6);
                padding: 8px;
                font-family: 'Consolas';
                font-size: 11px;
                letter-spacing: 1px;
            }
            #subTabButtonActive {
                background-color: rgba(12, 30, 50, 0.8);
                border: 1px solid rgba(0, 212, 255, 0.4);
                border-bottom: 2px solid #00d4ff;
                color: #00d4ff;
                padding: 8px;
                font-family: 'Consolas';
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            #automationInput, #automationText, #automationCombo {
                background-color: rgba(0, 0, 0, 0.2);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-radius: 4px;
                padding: 8px;
                color: #e8f6ff;
                font-family: 'Consolas';
            }
            #automationInput:focus, #automationText:focus {
                border: 1px solid rgba(0, 212, 255, 0.6);
            }
            #executeButton {
                background-color: rgba(0, 212, 255, 0.15);
                border: 1px solid rgba(0, 212, 255, 0.5);
                color: #7ffbff;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            #executeButton:hover {
                background-color: rgba(0, 212, 255, 0.3);
                border: 1px solid rgba(0, 212, 255, 0.8);
            }
            #actionButtonSecondary {
                background-color: rgba(160, 200, 255, 0.05);
                border: 1px solid rgba(160, 200, 255, 0.2);
                color: rgba(160, 200, 255, 0.6);
                padding: 10px;
                border-radius: 4px;
            }
            #panelCard {
                background-color: rgba(10, 22, 40, 0.6);
                border: 1px solid rgba(0, 212, 255, 0.25);
                border-radius: 8px;
                color: #cfe8ff;
            }
            #panelTitle {
                color: #9ad6ff;
                letter-spacing: 1px;
                font-weight: bold;
            }
            QLabel {
                color: #cfe8ff;
                font-family: 'Consolas';
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                background-color: #0a1628;
                border: 1px solid #00d4ff;
                selection-background-color: #00d4ff;
                color: #e8f6ff;
            }
        """)

    def set_tab(self, index):
        self.tabs.setCurrentIndex(index)
        self.msg_tab_btn.setObjectName("subTabButtonActive" if index == 0 else "subTabButton")
        self.post_tab_btn.setObjectName("subTabButtonActive" if index == 1 else "subTabButton")
        self.msg_tab_btn.style().unpolish(self.msg_tab_btn)
        self.msg_tab_btn.style().polish(self.msg_tab_btn)
        self.post_tab_btn.style().unpolish(self.post_tab_btn)
        self.post_tab_btn.style().polish(self.post_tab_btn)

    def _on_send_msg(self):
        platform = self.msg_platform.currentText()
        recipient = self.msg_recipient.text()
        body = self.msg_body.toPlainText()
        
        if not recipient or not body:
            return # Should show error in real app
            
        # Dispatch to backend via JARVISWindow (parent chain)
        # We'll use a standard command format that JARVIS already understands
        command = f"send {platform.lower()} to {recipient}, {body}"
        self._dispatch_command(command)
        
        # Clear fields
        self.msg_recipient.clear()
        self.msg_body.clear()

    def _on_post_now(self):
        platform = self.post_platform.currentText()
        content = self.post_content.toPlainText()
        
        if not content:
            return
            
        command = f"post to {platform.lower()}, {content}"
        self._dispatch_command(command)
        
        # Clear fields
        self.post_content.clear()

    def _dispatch_command(self, text):
        """Find the JARVISWindow and submit the text"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'on_voice_input_send'):
                parent.on_voice_input_send(text)
                break
            parent = parent.parent()
