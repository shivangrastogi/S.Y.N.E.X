from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QFrame, QPushButton, QTextEdit, QSizePolicy, QStackedWidget, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QRect, QPointF, QTimer, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QRadialGradient, QPixmap, QIcon, QTextOption, QImage
import os
import math
import numpy as np
import cv2
from ui_laptop.widgets.toggle_switch import SmoothToggleSwitch


class RingWidget(QWidget):
    """Central circular HUD ring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.middle_angle = 0
        self.inner_angle = 0
        self.lightning_phase = 0.0
        self.is_listening = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_listening(self, is_listening: bool):
        if self.is_listening == is_listening:
            return
        self.is_listening = is_listening
        self.update()

    def _tick(self):
        self.middle_angle = (self.middle_angle + 1) % 360
        self.inner_angle = (self.inner_angle - 2) % 360
        self.lightning_phase = (self.lightning_phase + 0.08) % (math.tau)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = min(self.width(), self.height())
        rect = QRect(0, 0, size, size)
        rect.moveCenter(self.rect().center())
        rect = rect.adjusted(10, 10, -10, -10)

        # Solid outer outline
        pen = QPen(QColor(0, 200, 255, 200), 3)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)

        # Ring with 4 gaps (clockwise)
        middle = rect.adjusted(24, 24, -24, -24)
        pen = QPen(QColor(220, 220, 220, 200), 2)
        painter.setPen(pen)
        gaps = 4
        gap_deg = 28
        seg_deg = (360 - gaps * gap_deg) / gaps
        start = self.middle_angle
        for _ in range(gaps):
            painter.drawArc(middle, int(start * 16), int(seg_deg * 16))
            start += seg_deg + gap_deg

        # Inner ring with 6 gaps (counter-clockwise)
        inner = rect.adjusted(58, 58, -58, -58)
        pen = QPen(QColor(160, 200, 255, 200), 2)
        painter.setPen(pen)
        gaps = 6
        gap_deg = 16
        seg_deg = (360 - gaps * gap_deg) / gaps
        start = self.inner_angle
        for _ in range(gaps):
            painter.drawArc(inner, int(start * 16), int(seg_deg * 16))
            start += seg_deg + gap_deg

        # Inner solid outlines (smaller, tighter)
        inner_outline_1 = rect.adjusted(78, 78, -78, -78)
        inner_outline_2 = rect.adjusted(92, 92, -92, -92)
        pen = QPen(QColor(0, 200, 255, 140), 2)
        painter.setPen(pen)
        painter.drawEllipse(inner_outline_1)
        pen = QPen(QColor(0, 200, 255, 110), 2)
        painter.setPen(pen)
        painter.drawEllipse(inner_outline_2)

        # Center glow
        center = QPointF(rect.center())
        bolt_radius = inner_outline_2.width() / 2
        pulse = 0.55 + 0.45 * math.sin(self.lightning_phase)
        glow = QRadialGradient(center, bolt_radius * 0.9)
        glow.setColorAt(0.0, QColor(120, 220, 255, int(70 + 70 * pulse)))
        glow.setColorAt(0.4, QColor(0, 200, 255, int(40 + 40 * pulse)))
        glow.setColorAt(1.0, QColor(0, 200, 255, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, bolt_radius * 0.85, bolt_radius * 0.85)

        # Wavy lightning (horizontal) only when listening
        if self.is_listening:
            bolt_len = bolt_radius * 1.1
            steps = 16
            x_start = -bolt_len * 0.6
            x_end = bolt_len * 0.6
            points = []
            for i in range(steps + 1):
                t = i / steps
                x = x_start + (x_end - x_start) * t
                wave = math.sin((t * 6.0 + self.lightning_phase) * math.tau)
                wave2 = math.sin((t * 12.0 + self.lightning_phase * 1.4) * math.tau)
                y = (wave * 0.55 + wave2 * 0.25) * (bolt_radius * 0.18)
                points.append(QPointF(center.x() + x, center.y() + y))

            for width, alpha in [(6, 40), (3, 110), (1.4, 220)]:
                pen = QPen(QColor(160, 240, 255, alpha), width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                for idx in range(len(points) - 1):
                    painter.drawLine(points[idx], points[idx + 1])


        painter.end()


class CenterContent(QWidget):
    """Center content area for chat messages"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0a1628;")
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the center content UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Left panel (cyberpunk menu)
        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setFixedWidth(260)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)
        
        nav_items = [
            ("DASHBOARD", "dashboard"),
            ("COMMUNICATION", "communication"),
            ("MOBILE", "mobile"),
            ("COMMANDS", "commands"),
            ("GESTURES", "gestures"),
            ("LOGS", "logs"),
            ("SETTINGS", "settings"),
        ]

        nav_title = QLabel("A.E.R.I.S")
        nav_title.setObjectName("navTitle")
        nav_title.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        left_layout.addWidget(nav_title)

        self.nav_buttons = {}
        for title, key in nav_items:
            btn = QPushButton(title)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setObjectName("navButton")
            btn.clicked.connect(lambda checked, k=key: self._set_active_page(k))
            self.nav_buttons[key] = btn
            left_layout.addWidget(btn)

        left_layout.addStretch()

        # Main content stack
        self.pages = QStackedWidget()

        # Dashboard page
        dashboard_page = QWidget()
        dashboard_layout = QVBoxLayout(dashboard_page)
        dashboard_layout.setContentsMargins(16, 16, 16, 16)
        dashboard_layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("DASHBOARD")
        title.setObjectName("dashboardTitle")
        title.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        status = QLabel("ONLINE  •  SECURE  •  READY")
        status.setObjectName("dashboardStatus")
        status.setFont(QFont("Consolas", 9))
        header.addWidget(status)
        dashboard_layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(16)

        left_stats = QVBoxLayout()
        left_stats.setSpacing(10)
        for title_text, value in [("CPU", "51%"), ("TEMP", "55°C"), ("LAT", "4.587"), ("NET", "11.5G")]:
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            label = QLabel(title_text)
            label.setObjectName("statLabel")
            val = QLabel(value)
            val.setObjectName("statValue")
            val.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            card_layout.addWidget(label)
            card_layout.addWidget(val)
            left_stats.addWidget(card)
        left_stats.addStretch()

        self.ring = RingWidget()

        right_stats = QVBoxLayout()
        right_stats.setSpacing(10)
        for title_text, value in [("POWER", "57%"), ("CORE", "5.56"), ("MEM", "8.56"), ("UTIL", "74%")]:
            card = QFrame()
            card.setObjectName("statCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            label = QLabel(title_text)
            label.setObjectName("statLabel")
            val = QLabel(value)
            val.setObjectName("statValue")
            val.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
            card_layout.addWidget(label)
            card_layout.addWidget(val)
            right_stats.addWidget(card)
        right_stats.addStretch()

        body.addLayout(left_stats)
        body.addWidget(self.ring, 1)
        body.addLayout(right_stats)
        dashboard_layout.addLayout(body, 1)

        # Communication page
        communication_page = QWidget()
        communication_layout = QVBoxLayout(communication_page)
        communication_layout.setContentsMargins(0, 0, 0, 0)
        self.communication_panel = CommunicationPanel()
        communication_layout.addWidget(self.communication_panel, 1)

        # Gestures page
        gestures_page = QWidget()
        gestures_layout = QVBoxLayout(gestures_page)
        gestures_layout.setContentsMargins(16, 8, 16, 16)
        gestures_layout.setSpacing(12)

        gesture_header = QHBoxLayout()
        gesture_title = QLabel("GESTURES")
        gesture_title.setObjectName("dashboardTitle")
        gesture_title.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
        gesture_header.addWidget(gesture_title)
        gesture_header.addSpacing(15)  # Spacing after title
        
        # Add toggle switch for gesture mode (right after title)
        self.gesture_toggle = SmoothToggleSwitch()
        self.gesture_toggle_label = QLabel("OFF")
        self.gesture_toggle_label.setObjectName("dashboardStatus")
        self.gesture_toggle_label.setFont(QFont("Consolas", 9))
        self.gesture_toggle_enabled = False  # Track if toggle allows gesture mode (OFF by default)
        self._updating_toggle_from_backend = False  # Prevent feedback loop
        self.gesture_toggle.toggled.connect(self._on_gesture_toggle)
        gesture_header.addWidget(self.gesture_toggle_label)
        gesture_header.addWidget(self.gesture_toggle)
        gesture_header.addStretch()  # Stretch after toggle
        
        gesture_status = QLabel("ONLINE  •  SECURE  •  READY")
        gesture_status.setObjectName("dashboardStatus")
        gesture_status.setFont(QFont("Consolas", 9))
        gesture_header.addWidget(gesture_status)
        gestures_layout.addLayout(gesture_header)

        info_card = QFrame()
        info_card.setObjectName("panelCard")
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)

        mode_row = QHBoxLayout()
        mode_label = QLabel("GESTURE MODE")
        mode_label.setObjectName("panelTitle")
        mode_row.addWidget(mode_label)
        mode_row.addStretch()
        self.gesture_mode_status = QLabel("● INACTIVE")
        self.gesture_mode_status.setObjectName("dashboardStatus")
        mode_row.addWidget(self.gesture_mode_status)
        info_layout.addLayout(mode_row)

        info_layout.addWidget(QLabel("Toggle Gesture Mode: V-SIGN"))
        self.gesture_camera_label = QLabel("Camera: Connected (HD)")
        self.gesture_fps_label = QLabel("FPS: --")
        info_layout.addWidget(self.gesture_camera_label)
        info_layout.addWidget(self.gesture_fps_label)

        preview_card = QFrame()
        preview_card.setObjectName("panelCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(6)
        preview_header = QHBoxLayout()
        preview_label = QLabel("LIVE PREVIEW  ACTIVE")
        preview_label.setObjectName("panelTitle")
        preview_header.addWidget(preview_label)
        preview_header.addStretch()
        preview_layout.addLayout(preview_header)

        preview_frame = QFrame()
        preview_frame.setObjectName("previewFrame")
        preview_frame_layout = QVBoxLayout(preview_frame)
        preview_frame_layout.setContentsMargins(6, 6, 6, 6)
        self.preview_label = QLabel("No preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setObjectName("previewLabel")
        preview_frame_layout.addWidget(self.preview_label, 1)
        preview_layout.addWidget(preview_frame, 1)

        self.preview_footer = QLabel("WAITING")
        self.preview_footer.setObjectName("statusActive")
        self.preview_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_footer)

        mapping_card = QFrame()
        mapping_card.setObjectName("panelCard")
        mapping_layout = QVBoxLayout(mapping_card)
        mapping_layout.setContentsMargins(12, 10, 12, 10)
        mapping_layout.setSpacing(8)

        mapping_title = QLabel("HAND GESTURE MAPPING")
        mapping_title.setObjectName("panelTitle")
        mapping_layout.addWidget(mapping_title)

        # 2x2 Grid for mappings
        grid_layout = QVBoxLayout()
        grid_layout.setSpacing(8)

        mappings = [
            ("Open Palm", "Lock Screen", "palm_icon.png"),
            ("Fist", "Mute System", "fist_icon.png"),
            ("V Sign", "Toggle Gesture Mode", "victory_icon.png"),
            ("Point", "Switch Tab", "point_icon.png"),
        ]
        
        # Create 2 rows with 2 items each
        for i in range(0, len(mappings), 2):
            row_h_layout = QHBoxLayout()
            row_h_layout.setSpacing(12)
            
            # Add 2 items per row
            for j in range(2):
                if i + j < len(mappings):
                    name, action, icon_file = mappings[i + j]
                    
                    # Create mapping item container
                    item_widget = QFrame()
                    item_widget.setObjectName("mappingRow")
                    item_widget.setCursor(Qt.CursorShape.PointingHandCursor)
                    item_layout = QHBoxLayout(item_widget)
                    item_layout.setContentsMargins(10, 8, 10, 8)
                    item_layout.setSpacing(10)
                    
                    # Icon (24x24 contained)
                    icon_label = QLabel()
                    icon_label.setFixedSize(24, 24)
                    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    icon_path = os.path.join(os.path.dirname(__file__), "assets", icon_file)
                    if os.path.exists(icon_path):
                        pixmap = QPixmap(icon_path).scaledToHeight(24, Qt.TransformationMode.SmoothTransformation)
                        icon_label.setPixmap(pixmap)
                    item_layout.addWidget(icon_label, 0)
                    
                    # Gesture name
                    name_label = QLabel(name)
                    name_label.setObjectName("mappingName")
                    item_layout.addWidget(name_label, 1)
                    
                    # Arrow chevron in center
                    arrow_label = QLabel("❯")
                    arrow_label.setObjectName("mappingArrow")
                    arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    item_layout.addWidget(arrow_label, 0)
                    
                    # Action
                    action_label = QLabel(action)
                    action_label.setObjectName("mappingAction")
                    item_layout.addWidget(action_label, 1)
                    
                    row_h_layout.addWidget(item_widget, 1)
            
            grid_layout.addLayout(row_h_layout)
        
        mapping_layout.addLayout(grid_layout, 1)

        log_card = QFrame()
        log_card.setObjectName("panelCard")
        log_card.setMaximumHeight(120)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(12, 8, 12, 8)
        log_layout.setSpacing(4)
        log_title = QLabel("GESTURE ACTIVITY LOG")
        log_title.setObjectName("panelTitle")
        log_layout.addWidget(log_title)
        for entry in [
            "[21:01:14] V-SIGN detected → Gesture Mode ON",
            "[21:01:38] PALM detected → Lock Screen",
            "[20:59:42] FIST detected → System Muted",
        ]:
            log_item = QLabel(entry)
            log_item.setObjectName("logEntry")
            log_layout.addWidget(log_item)

        # Reflow to match target layout: left column (mode + mapping), right column (preview), activity log below
        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        left_col.addWidget(info_card)
        left_col.addWidget(mapping_card, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        right_col.addWidget(preview_card)

        main_row.addLayout(left_col, 3)
        main_row.addLayout(right_col, 2)

        gestures_layout.addLayout(main_row)
        gestures_layout.addWidget(log_card)

        # Empty pages
        empty_pages = {}
        for key, title_text in [
            ("mobile", "MOBILE"),
            ("commands", "COMMANDS"),
            ("logs", "LOGS"),
            ("settings", "SETTINGS"),
        ]:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(16, 16, 16, 16)
            label = QLabel(f"{title_text} (EMPTY)")
            label.setObjectName("emptyTitle")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_layout.addWidget(label, 1)
            empty_pages[key] = page

        self.pages.addWidget(dashboard_page)
        self.pages.addWidget(communication_page)
        self.pages.addWidget(gestures_page)
        self.pages.addWidget(empty_pages["mobile"])
        self.pages.addWidget(empty_pages["commands"])
        self.pages.addWidget(empty_pages["logs"])
        self.pages.addWidget(empty_pages["settings"])

        self.page_keys = [
            "dashboard",
            "communication",
            "gestures",
            "mobile",
            "commands",
            "logs",
            "settings",
        ]

        layout.addWidget(left_panel)
        layout.addWidget(self.pages, 1)
        
        self.setStyleSheet("""
            #leftPanel {
                background-color: rgba(8, 16, 28, 0.8);
                border: 1px solid rgba(0, 212, 255, 0.25);
                border-radius: 10px;
            }
            #navTitle {
                color: #8fdcff;
                letter-spacing: 3px;
                padding: 6px 4px 12px 4px;
            }
            #navButton {
                text-align: left;
                padding: 8px 10px;
                border-radius: 6px;
                background-color: rgba(10, 22, 40, 0.5);
                border: 1px solid rgba(0, 212, 255, 0.15);
                color: #cfe8ff;
                font-family: 'Consolas';
            }
            #navButton:hover {
                border: 1px solid rgba(0, 212, 255, 0.5);
                background-color: rgba(12, 30, 50, 0.7);
            }
            #navButtonActive {
                text-align: left;
                padding: 8px 10px;
                border-radius: 6px;
                background-color: rgba(12, 30, 50, 0.9);
                border: 1px solid rgba(0, 255, 255, 0.8);
                color: #7ffbff;
                font-family: 'Consolas';
            }
            #dashboardTitle {
                color: #cfe8ff;
                letter-spacing: 2px;
            }
            #dashboardStatus {
                color: #7fd7ff;
            }
            #statCard {
                background-color: rgba(10, 22, 40, 0.6);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-radius: 6px;
            }
            #statLabel {
                color: rgba(207, 232, 255, 0.6);
            }
            #statValue {
                color: #9ad6ff;
            }
            #card {
                background-color: rgba(10, 22, 40, 0.6);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-radius: 6px;
            }
            #cardActive {
                background-color: rgba(12, 30, 50, 0.8);
                border: 1px solid rgba(255, 148, 0, 0.8);
                border-radius: 6px;
            }
            #cardIcon {
                color: #9ad6ff;
                background-color: rgba(0, 212, 255, 0.12);
                border: 1px solid rgba(0, 212, 255, 0.35);
                border-radius: 6px;
            }
            #cardIconActive {
                color: #ffb36a;
                background-color: rgba(255, 148, 0, 0.18);
                border: 1px solid rgba(255, 148, 0, 0.8);
                border-radius: 6px;
            }
            #cardTitle {
                color: #cfe8ff;
            }
            #cardTitleActive {
                color: #ffb36a;
            }
            #cardSubtitle {
                color: rgba(207, 232, 255, 0.6);
            }
            #cardSubtitleActive {
                color: rgba(255, 179, 106, 0.7);
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
            }
            #statusActive {
                color: #6dff9f;
            }
            #previewFrame {
                background-color: rgba(4, 10, 18, 0.8);
                border: 1px solid rgba(0, 212, 255, 0.35);
                border-radius: 6px;
                min-height: 200px;
            }
            #previewLabel {
                color: rgba(207, 232, 255, 0.6);
            }
            #gestureAnimIcon {
                font-size: 48px;
                color: #7ffbff;
            }
            #gestureAnimText {
                color: #9ad6ff;
            }
            #gestureAnimPulse {
                font-size: 48px;
                color: #6dff9f;
                text-shadow: 0 0 12px rgba(0, 255, 255, 0.9);
            }
            #mappingName {
                color: #cfe8ff;
            }
            #mappingAction {
                color: #7fd7ff;
            }
            #mappingArrow {
                color: rgba(0, 212, 255, 0.6);
                font-size: 16px;
                font-weight: bold;
            }
            #mappingRow {
                background-color: transparent;
                border: 1px solid rgba(0, 212, 255, 0.15);
                border-radius: 6px;
                padding: 0px;
                margin: 0px;
            }
            #mappingRow:hover {
                background-color: rgba(0, 150, 200, 0.3);
                border-top: 2px solid rgba(0, 212, 255, 0.8);
                border-bottom: 2px solid rgba(0, 212, 255, 0.8);
                border-left: 1px solid rgba(0, 212, 255, 0.5);
                border-right: 1px solid rgba(0, 212, 255, 0.5);
                border-radius: 6px;
                padding: 0px;
                margin-top: 4px;
                margin-bottom: 4px;
            }
            #mappingRow:hover #mappingName {
                color: #6dff9f;
            }
            #mappingRow:hover #mappingAction {
                color: #6dff9f;
            }
            #mappingRow:hover #mappingArrow {
                color: #6dff9f;
            }
            #logEntry {
                color: #a6d9ff;
            }
            #emptyTitle {
                color: rgba(207, 232, 255, 0.5);
                letter-spacing: 2px;
            }
        """)
        
        self.setLayout(layout)
        self._set_active_page("dashboard")  # Start with dashboard, not gestures

    def set_listening(self, is_listening: bool):
        self.ring.set_listening(is_listening)

    def add_chat_message(self, text: str, sender: str = "user"):
        self.communication_panel.add_message(text, sender)

    def update_gesture_status(self, active: bool, gesture: str, fps: float):
        status_text = "● ACTIVE" if active else "● INACTIVE"
        self.gesture_mode_status.setText(status_text)
        self.gesture_mode_status.setObjectName("statusActive" if active else "dashboardStatus")
        self.gesture_mode_status.style().unpolish(self.gesture_mode_status)
        self.gesture_mode_status.style().polish(self.gesture_mode_status)
        
        # Update toggle switch (without triggering toggle signal)
        self._updating_toggle_from_backend = True
        self.gesture_toggle.set_on(active, animate=True)
        self.gesture_toggle_label.setText("ON" if active else "OFF")
        self._updating_toggle_from_backend = False
        
        if fps > 0:
            self.gesture_fps_label.setText(f"FPS: {fps:.0f}")
        if active:
            self.preview_footer.setText(gesture.replace("_", " "))
        elif gesture not in ("NONE", "TRANSITIONING"):
            self.preview_footer.setText(gesture.replace("_", " "))
    
    def _on_gesture_toggle(self, is_on):
        """Handle gesture mode toggle from UI"""
        # Ignore updates from backend to prevent feedback loop
        if self._updating_toggle_from_backend:
            return
        
        self.gesture_toggle_enabled = is_on
        if hasattr(self, '_backend_thread') and self._backend_thread:
            if is_on:
                # Turn ON: send voice command to override and activate gesture
                self._backend_thread.submit_text("gesture mode on")
            else:
                # Turn OFF: directly disable gesture allowed flag (blocks camera)
                self._backend_thread.set_gesture_allowed(False)

    def update_gesture_preview(self, frame):
        if frame is None:
            self.preview_label.setText("No preview")
            return
        
        # Handle JPEG bytes or memoryview
        image = QImage()
        try:
            if isinstance(frame, (bytes, bytearray, memoryview)):
                image.loadFromData(bytes(frame))
            else:
                # Assume numpy array in BGR - make a copy to avoid issues
                if hasattr(frame, 'copy'):
                    frame = frame.copy()
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if 'cv2' in dir() else frame[:, :, ::-1]
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                # Ensure data is contiguous
                if not rgb.flags['C_CONTIGUOUS']:
                    rgb = np.ascontiguousarray(rgb)
                image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        except Exception as e:
            self.preview_label.setText(f"Preview error: {str(e)[:30]}")
            return

        if image.isNull():
            self.preview_label.setText("Invalid frame")
            return

        pixmap = QPixmap.fromImage(image)
        
        # Use the full preview area
        available_size = self.preview_label.contentsRect().size()
        target_width = max(1, available_size.width())
        target_height = max(1, available_size.height())
        target_size = QSize(target_width, target_height)

        # Keep aspect ratio
        fitted_size = pixmap.size().scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio
        )

        # Gentle zoom-in to reduce empty space
        zoom_factor = 1.08
        zoomed_size = QSize(
            min(target_width, int(fitted_size.width() * zoom_factor)),
            min(target_height, int(fitted_size.height() * zoom_factor)),
        )

        # Use FastTransformation for smoother updates (less CPU intensive)
        scaled_pixmap = pixmap.scaled(
            zoomed_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,  # Changed from SmoothTransformation
        )

        # Direct pixmap update without opacity effects to prevent flicker
        self.preview_label.setPixmap(scaled_pixmap)

    def update_gesture_event(self, gesture: str):
        pretty = gesture.replace("_", " ")
        self.preview_footer.setText(f"{pretty} detected")

    def _pulse_gesture_anim(self):
        # Animation removed from UI; no-op to avoid repeated logs or errors
        return

    def _set_active_page(self, key: str):
        if key not in self.nav_buttons:
            return
        for k, btn in self.nav_buttons.items():
            btn.setObjectName("navButtonActive" if k == key else "navButton")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        index_map = {
            "dashboard": 0,
            "communication": 1,
            "gestures": 2,
            "mobile": 3,
            "commands": 4,
            "logs": 5,
            "settings": 6,
        }
        self.pages.setCurrentIndex(index_map[key])

    def closeEvent(self, event):
        if hasattr(self, "gesture_anim_timer") and self.gesture_anim_timer.isActive():
            self.gesture_anim_timer.stop()
        super().closeEvent(event)


class CommunicationPanel(QWidget):
    """Right-side communication panel with collapsible chat."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self._build_ui()

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(8)

        self._collapse_spacer = QWidget()
        self._collapse_spacer.setVisible(False)
        self._layout.addWidget(self._collapse_spacer, 1)

        self.header_widget = QWidget()
        header = QHBoxLayout(self.header_widget)
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("COMMUNICATION")
        title.setObjectName("commTitle")
        title.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self.collapse_btn = QPushButton()
        self.collapse_btn.setObjectName("collapseBtn")
        self.collapse_btn.setFixedSize(22, 22)
        self.collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "minimize_logo.png")
        if os.path.exists(icon_path):
            icon = QIcon(QPixmap(icon_path))
            self.collapse_btn.setIcon(icon)
            self.collapse_btn.setIconSize(self.collapse_btn.size())
        self.collapse_btn.clicked.connect(self.toggle_collapsed)
        header.addWidget(self.collapse_btn)

        self._layout.addWidget(self.header_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setObjectName("chatScroll")

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(6, 6, 6, 6)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_container)
        self._layout.addWidget(self.scroll_area, 1)
        self._bubbles = []

        self.setStyleSheet("""
            CommunicationPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(12, 24, 40, 0.95), stop:1 rgba(6, 12, 22, 0.95));
                border: 1px solid rgba(0, 212, 255, 0.45);
                border-radius: 12px;
            }
            #commTitle {
                color: #cfe8ff;
                letter-spacing: 2px;
                font-family: 'Orbitron', 'Consolas', 'Segoe UI';
            }
            #collapseBtn {
                background-color: rgba(0, 212, 255, 0.15);
                border: 1px solid rgba(0, 212, 255, 0.35);
                border-radius: 4px;
            }
            #collapseBtn:hover {
                background-color: rgba(0, 212, 255, 0.35);
            }
            #chatScroll {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(0, 0, 0, 0.2);
                width: 8px;
                margin: 2px 0 2px 0;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 212, 255, 0.5);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QWidget#chatBubbleUser {
                background-color: rgba(0, 212, 255, 0.25);
                border: 1px solid rgba(0, 212, 255, 0.45);
                border-radius: 10px;
            }
            QWidget#chatBubbleBot {
                background-color: rgba(12, 30, 50, 0.8);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-radius: 10px;
            }
            QWidget#chatBubbleUser[newMessage="true"], QWidget#chatBubbleBot[newMessage="true"] {
                border: 1px solid rgba(255, 180, 80, 0.9);
            }
            QLabel#chatText, QTextEdit#chatText {
                color: #e8f6ff;
                font-family: 'Orbitron', 'Consolas', 'Segoe UI';
                letter-spacing: 0.6px;
                background-color: transparent;
                border: none;
            }
        """)

    def toggle_collapsed(self):
        self.set_collapsed(not self.is_collapsed)

    def set_collapsed(self, collapsed: bool):
        self.is_collapsed = collapsed
        self.scroll_area.setVisible(not collapsed)
        self._collapse_spacer.setVisible(collapsed)
        self.updateGeometry()

    def add_message(self, text: str, sender: str = "user"):
        bubble = QWidget()
        bubble.setObjectName("chatBubbleUser" if sender == "user" else "chatBubbleBot")
        bubble.setProperty("newMessage", True)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(10, 8, 10, 8)
        bubble_layout.setSpacing(2)
        bubble_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Use QTextEdit for robust wrapping
        text_view = QTextEdit()
        text_view.setObjectName("chatText")
        text_view.setReadOnly(True)
        text_view.setText(text)
        text_view.setFrameStyle(QFrame.Shape.NoFrame)
        text_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        text_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        text_view.viewport().setAutoFillBackground(False)
        text_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        # Prefer word-boundary wrapping to avoid broken words
        text_view.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        
        text_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Force styles specifically for this instance to ensure visibility
        text_view.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: #e8f6ff;
                font-family: 'Orbitron', 'Consolas', 'Segoe UI';
                font-size: 14px;
            }
        """)
        
        bubble_layout.addWidget(text_view)

        # Calculate proper width for the bubble
        available_width = max(120, self.scroll_area.viewport().width() - 40)
        bubble.setMaximumWidth(available_width)
        bubble.setMinimumWidth(80)

        row = QHBoxLayout()
        if sender == "user":
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()

        self.messages_layout.insertLayout(self.messages_layout.count() - 1, row)
        self._bubbles.append(bubble)
        
        # Initial height adjustment
        self._update_text_height(text_view, available_width - 20)

        self._scroll_to_bottom()
        QTimer.singleShot(60, self._scroll_to_bottom)
        QTimer.singleShot(1200, lambda: self._clear_new_focus(bubble))

    def _update_text_height(self, text_view, width=None):
        if not isinstance(text_view, QTextEdit):
            return
        
        if width is None:
             width = text_view.width()
             
        doc = text_view.document()
        # Set the text width to the available width to calculate height correctly
        doc.setTextWidth(max(10, width)) 
        
        # Get the layout height
        h = doc.size().height()
        
        # Set the fixed height with a small buffer for safety
        text_view.setFixedHeight(int(h) + 10)

    def _scroll_to_bottom(self):
        QTimer.singleShot(0, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    def _clear_new_focus(self, bubble: QWidget):
        if bubble:
            bubble.setProperty("newMessage", False)
            bubble.style().unpolish(bubble)
            bubble.style().polish(bubble)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Recalculate widths for all bubbles when panel is resized
        available_width = max(120, self.scroll_area.viewport().width() - 40)
        
        for bubble in self._bubbles:
            bubble.setMaximumWidth(available_width)
            if bubble.layout() and bubble.layout().count() > 0:
                widget = bubble.layout().itemAt(0).widget()
                if isinstance(widget, QTextEdit):
                    # Update height based on new width
                    self._update_text_height(widget, available_width - 20)
