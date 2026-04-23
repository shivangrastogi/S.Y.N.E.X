# Path: d:\New folder (2) - JARVIS\ui_laptop\center_content.py
# File: ui_laptop/center_content.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QFrame, QPushButton, QTextEdit, QSizePolicy, QStackedWidget
from PyQt5.QtCore import Qt, QRect, QPointF, QTimer, QSize
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QRadialGradient, QPixmap, QIcon, QTextOption, QImage
import os

# Use workspace root for all asset/data paths
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ASSETS_DIR = os.path.join(WORKSPACE_ROOT, 'ui_laptop', 'assets')
import math
import numpy as np
import cv2
from aeris.ui_laptop.widgets.toggle_switch import SmoothToggleSwitch
from aeris.ui_laptop.widgets.settings_page import SettingsPage
from aeris.ui_laptop.widgets.automation_page import AutomationPage
from aeris.ui.settings_manager import SettingsManager
from aeris.ui.images_tab import ImagesTab
from aeris.core.event_bus import event_bus
from aeris.core.brain_router import brain_router
from aeris.memory.storage import storage


class RingWidget(QWidget):
    """Central circular HUD ring with state-aware visuals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.middle_angle = 0
        self.inner_angle = 0
        self.lightning_phase = 0.0
        self.current_state = "IDLE"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_state(self, state: str):
        if self.current_state == state:
            return
        self.current_state = state
        self.update()

    def _tick(self):
        # Adjust rotation speeds based on state
        speed_mult = 1.0
        if self.current_state == "THINKING":
            speed_mult = 4.0
        elif self.current_state == "SLEEPING":
            speed_mult = 0.2
            
        self.middle_angle = (self.middle_angle + (1 * speed_mult)) % 360
        self.inner_angle = (self.inner_angle - (2 * speed_mult)) % 360
        self.lightning_phase = (self.lightning_phase + (0.08 * speed_mult)) % (math.tau)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        size = min(self.width(), self.height())
        rect = QRect(0, 0, size, size)
        rect.moveCenter(self.rect().center())
        rect = rect.adjusted(10, 10, -10, -10)

        # State-based colors
        colors = {
            "IDLE": QColor(0, 200, 255, 200),
            "LISTENING": QColor(0, 255, 255, 255),
            "THINKING": QColor(255, 180, 80, 255), # Orange
            "SLEEPING": QColor(0, 100, 150, 100), # Dim blue
            "SPEAKING": QColor(0, 255, 255, 220),
        }
        primary_color = colors.get(self.current_state, colors["IDLE"])

        # Solid outer outline
        pen = QPen(primary_color, 3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect)

        # Ring with 4 gaps (clockwise)
        middle = rect.adjusted(24, 24, -24, -24)
        pen = QPen(primary_color if self.current_state != "IDLE" else QColor(220, 220, 220, 200), 2)
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
        pen = QPen(primary_color.lighter(120), 2)
        painter.setPen(pen)
        gaps = 6
        gap_deg = 16
        seg_deg = (360 - gaps * gap_deg) / gaps
        start = self.inner_angle
        for _ in range(gaps):
            painter.drawArc(inner, int(start * 16), int(seg_deg * 16))
            start += seg_deg + gap_deg

        # Inner solid outlines
        inner_outline_1 = rect.adjusted(78, 78, -78, -78)
        inner_outline_2 = rect.adjusted(92, 92, -92, -92)
        pen = QPen(primary_color, 2)
        painter.setPen(pen)
        painter.drawEllipse(inner_outline_1)
        pen = QPen(primary_color.darker(150), 2)
        painter.setPen(pen)
        painter.drawEllipse(inner_outline_2)

        # Center glow
        center = QPointF(rect.center())
        bolt_radius = inner_outline_2.width() / 2
        pulse = 0.55 + 0.45 * math.sin(self.lightning_phase)
        
        # Thinking pulse
        if self.current_state == "THINKING":
            pulse = 0.7 + 0.3 * math.sin(self.lightning_phase * 2)

        glow = QRadialGradient(center, bolt_radius * 0.9)
        glow.setColorAt(0.0, primary_color)
        glow.setColorAt(0.4, primary_color.darker(150))
        glow.setColorAt(1.0, QColor(primary_color.red(), primary_color.green(), primary_color.blue(), 0))
        
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, bolt_radius * 0.85 * pulse, bolt_radius * 0.85 * pulse)

        # Wavy lightning (horizontal)
        if self.current_state in ["LISTENING", "SPEAKING", "THINKING"]:
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
                pen = QPen(QColor(primary_color.red(), primary_color.green(), primary_color.blue(), alpha), width)
                pen.setCapStyle(Qt.RoundCap)
                pen.setJoinStyle(Qt.RoundJoin)
                painter.setPen(pen)
                for idx in range(len(points) - 1):
                    painter.drawLine(points[idx], points[idx + 1])

        painter.end()


class CenterContent(QWidget):
    """Center content area for chat messages and HUD"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #0a1628;")
        self.is_nav_visible = True
        self.backend_thread = None
        self.setup_ui()

    def set_assistant_state(self, state: str):
        """Update center HUD state visuals"""
        if hasattr(self, "ring"):
            self.ring.set_state(state)
        
        # Optional: update dashboard status bar if visible
        if hasattr(self, "status_label"):
            self.status_label.setText(f"System State: {state}")

    def set_backend_thread(self, thread):
        # backend_thread is removed in v2
        pass

    def on_image_generation_started(self, prompt):
        if hasattr(self, "images_page"):
            self.images_page.add_placeholder(prompt)

    def on_image_generation_finished(self, metadata):
        if hasattr(self, "images_page"):
            self.images_page.on_generation_finished(metadata)

    def on_image_generation_progress(self, percentage, eta):
        if hasattr(self, "images_page"):
            self.images_page.on_generation_progress(percentage, eta)

    def setup_ui(self):
        """Setup the center content UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Left panel (cyberpunk menu)
        self.left_panel = QFrame()
        self.left_panel.setObjectName("leftPanel")
        self.left_panel.setFixedWidth(260)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)
        
        nav_items = [
            ("DASHBOARD", "dashboard"),
            ("COMMUNICATION", "communication"),
            ("AUTOMATION", "automation"),
            ("MOBILE", "mobile"),
            ("COMMANDS", "commands"),
            ("IMAGES", "images"),
            ("GESTURES", "gestures"),
            ("LOGS", "logs"),
            ("SETTINGS", "settings"),
        ]

        nav_title = QLabel("A.E.R.I.S")
        nav_title.setObjectName("navTitle")
        nav_title.setFont(QFont("Consolas", 12, QFont.Bold))
        left_layout.addWidget(nav_title)

        self.nav_buttons = {}
        for title, key in nav_items:
            class NavButton(QPushButton):
                def mouseDoubleClickEvent(self, event):
                    # Ignore double clicks to prevent crash
                    event.ignore()
            btn = NavButton(title)
            btn.setCursor(Qt.PointingHandCursor)
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
        title.setFont(QFont("Consolas", 14, QFont.Bold))
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
            val.setFont(QFont("Consolas", 14, QFont.Bold))
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
            val.setFont(QFont("Consolas", 14, QFont.Bold))
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
        gesture_title.setFont(QFont("Consolas", 14, QFont.Bold))
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
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setObjectName("previewLabel")
        preview_frame_layout.addWidget(self.preview_label, 1)
        preview_layout.addWidget(preview_frame, 1)

        self.preview_footer = QLabel("WAITING")
        self.preview_footer.setObjectName("statusActive")
        self.preview_footer.setAlignment(Qt.AlignCenter)
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
                    item_widget.setCursor(Qt.PointingHandCursor)
                    item_layout = QHBoxLayout(item_widget)
                    item_layout.setContentsMargins(10, 8, 10, 8)
                    item_layout.setSpacing(10)
                    
                    # Icon (24x24 contained)
                    icon_label = QLabel()
                    icon_label.setFixedSize(24, 24)
                    icon_label.setAlignment(Qt.AlignCenter)
                    icon_path = os.path.join(os.path.dirname(__file__), "assets", icon_file)
                    if os.path.exists(icon_path):
                        pixmap = QPixmap(icon_path).scaledToHeight(24, Qt.SmoothTransformation)
                        icon_label.setPixmap(pixmap)
                    item_layout.addWidget(icon_label, 0)
                    
                    # Gesture name
                    name_label = QLabel(name)
                    name_label.setObjectName("mappingName")
                    item_layout.addWidget(name_label, 1)
                    
                    # Arrow chevron in center
                    arrow_label = QLabel("❯")
                    arrow_label.setObjectName("mappingArrow")
                    arrow_label.setAlignment(Qt.AlignCenter)
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

        # Create settings manager (which hosts settings + images)
        self.settings_page = SettingsManager()

        # Empty pages for other sections
        empty_pages = {}
        for key, title_text in [
            ("commands", "COMMANDS"),
            ("logs", "LOGS"),
        ]:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(16, 16, 16, 16)
            label = QLabel(f"{title_text} (COMING SOON)")
            label.setObjectName("emptyTitle")
            label.setAlignment(Qt.AlignCenter)
            page_layout.addWidget(label, 1)
            empty_pages[key] = page

        # Mobile page
        self.mobile_page = MobilePanel(self)

        # Images page
        self.images_page = ImagesTab()

        # Automation page
        self.automation_page = AutomationPage()

        self.pages.addWidget(dashboard_page)
        self.pages.addWidget(communication_page)
        self.pages.addWidget(self.automation_page)
        self.pages.addWidget(gestures_page)
        self.pages.addWidget(self.mobile_page)
        self.pages.addWidget(self.images_page)
        self.pages.addWidget(empty_pages["commands"])
        self.pages.addWidget(empty_pages["logs"])
        self.pages.addWidget(self.settings_page)

        self.page_keys = [
            "dashboard",
            "communication",
            "automation",
            "gestures",
            "mobile",
            "images",
            "commands",
            "logs",
            "settings",
        ]

        layout.addWidget(self.left_panel)
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

    def set_backend_thread(self, thread):
        """No-op for backward compatibility during refactor"""
        pass

    def _on_mobile_fullscreen(self):
        """Toggle navigation panel visibility"""
        self.is_nav_visible = not self.is_nav_visible
        self.left_panel.setVisible(self.is_nav_visible)

    def update_mobile_status(self, connected, name="", device_id="", ip=""):
        if hasattr(self, "mobile_page"):
            self.mobile_page.update_status(connected, name, device_id, ip)

    def update_mobile_notification(self, app, title, text):
        if hasattr(self, "mobile_page"):
            self.mobile_page.add_notification(app, title, text)

    def update_mobile_call(self, caller, number, status):
        if hasattr(self, "mobile_page"):
            # Switch to mobile page automatically on incoming call?
            if status == "ringing":
                 self._set_active_page("mobile")
            self.mobile_page.show_incoming_call(caller, number, status)

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
        
        if not active:
            self.preview_label.clear()
            self.preview_label.setText("No preview")
            self.preview_footer.setText("OFFLINE")
            self._last_hand_crop = None
        
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
        
        # Emit command to event bus
        if is_on:
            event_bus.emit("gestures.command", {"command": "start"})
            # Optionally sync with brain for feedback
            brain_router.process_input("gesture mode on")
        else:
            event_bus.emit("gestures.command", {"command": "stop"})
            brain_router.process_input("gesture mode off")

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
            Qt.FastTransformation,  # Changed from SmoothTransformation
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

        # Mapping specifically for sidebar key to StackedWidget index
        index_map = {
            "dashboard": 0,
            "communication": 1,
            "automation": 2,
            "gestures": 3,
            "mobile": 4,
            "images": 5,
            "commands": 6,
            "logs": 7,
            "settings": 8,
        }
        
        if key in index_map:
            self.pages.setCurrentIndex(index_map[key])
        else:
            print(f"⚠️ Warning: Navigation key '{key}' not found in index_map")

    def apply_settings(self, settings: dict):
        """Apply settings to the settings page"""
        # Get the settings page from the stack (index 8)
        settings_widget = self.pages.widget(8)
        if hasattr(settings_widget, 'set_settings'):
            settings_widget.set_settings(settings)

    def closeEvent(self, event):
        if hasattr(self, "gesture_anim_timer") and self.gesture_anim_timer.isActive():
            self.gesture_anim_timer.stop()
        if hasattr(self, "ring") and hasattr(self.ring, "_timer") and self.ring._timer.isActive():
            self.ring._timer.stop()
        super().closeEvent(event)


class MobilePanel(QWidget):
    """Dashboard for connected mobile devices."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.notification_manager = None
            
        self.setup_ui()
        self.load_notifications()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("MOBILE SYSTEMS")
        title.setObjectName("dashboardTitle")
        title.setFont(QFont("Consolas", 14, QFont.Bold))
        header.addWidget(title)
        header.addStretch()
        self.conn_status = QLabel("● NO DEVICE CONNECTED")
        self.conn_status.setObjectName("dashboardStatus")
        header.addWidget(self.conn_status)
        layout.addLayout(header)

        # Main Row: Info (Left) + Screen (Right/Center)
        main_h_row = QHBoxLayout()
        main_h_row.setSpacing(16)

        # Left Column: Device Info & Mirroring Launcher
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # Device Info Card
        self.device_card = QFrame()
        self.device_card.setObjectName("panelCard")
        device_layout = QVBoxLayout(self.device_card)
        
        info_row = QHBoxLayout()
        self.device_name = QLabel("Device: --")
        self.device_id = QLabel("ID: --")
        info_row.addWidget(self.device_name)
        info_row.addStretch()
        info_row.addWidget(self.device_id)
        device_layout.addLayout(info_row)

        self.ip_addr = QLabel("Address: --")
        device_layout.addWidget(self.ip_addr)
        left_col.addWidget(self.device_card)

        # Mirroring Card
        mirror_card = QFrame()
        mirror_card.setObjectName("panelCard")
        mirror_layout = QVBoxLayout(mirror_card)
        mirror_title = QLabel("SCREEN MIRRORING")
        mirror_title.setObjectName("panelTitle")
        mirror_layout.addWidget(mirror_title)
        
        mirror_btn = QPushButton("LAUNCH MIRROR (scrcpy)")
        mirror_btn.setObjectName("navButtonActive")
        mirror_btn.clicked.connect(self._launch_mirroring)
        mirror_layout.addWidget(mirror_btn)
        
        fs_btn = QPushButton("FULL SCREEN MODE")
        fs_btn.setObjectName("navButton")
        fs_btn.clicked.connect(self._toggle_full_screen)
        mirror_layout.addWidget(fs_btn)
        left_col.addWidget(mirror_card)
        
        left_col.addStretch()
        main_h_row.addLayout(left_col, 2)

        # Right Column: Call Controls & Notifications
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        # Call Controls Card
        self.call_card = QFrame()
        self.call_card.setObjectName("panelCard")
        self.call_card.setVisible(False) # Hidden until call detected
        self.call_card.setStyleSheet("#panelCard { border: 2px solid #ff4444; background: rgba(80, 20, 20, 0.4); }")
        call_layout = QVBoxLayout(self.call_card)
        
        self.call_label = QLabel("📞 INCOMING CALL")
        self.call_label.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 14px;")
        call_layout.addWidget(self.call_label)
        
        self.caller_info = QLabel("Someone is calling...")
        call_layout.addWidget(self.caller_info)
        
        call_btns = QHBoxLayout()
        ans_btn = QPushButton("ANSWER")
        ans_btn.setStyleSheet("background: #2e7d32; color: white; border-radius: 4px; font-weight: bold;")
        ans_btn.setFixedSize(120, 32)
        ans_btn.clicked.connect(self._answer_call)
        
        dec_btn = QPushButton("DECLINE")
        dec_btn.setStyleSheet("background: #c62828; color: white; border-radius: 4px; font-weight: bold;")
        dec_btn.setFixedSize(120, 32)
        dec_btn.clicked.connect(self._decline_call)
        
        self.ans_btn = ans_btn
        self.dec_btn = dec_btn
        
        call_btns.addWidget(ans_btn)
        call_btns.addWidget(dec_btn)
        call_layout.addLayout(call_btns)
        right_col.addWidget(self.call_card)

        # Default Controls (Unlock, Ring, Disconnect)
        self.controls_card = QFrame()
        self.controls_card.setObjectName("panelCard")
        ctrl_layout = QVBoxLayout(self.controls_card)
        ctrl_title = QLabel("QUICK ACTIONS")
        ctrl_title.setObjectName("panelTitle")
        ctrl_layout.addWidget(ctrl_title)
        
        ctrl_btns = QHBoxLayout()
        unlock_btn = QPushButton("UNLOCK")
        unlock_btn.setObjectName("navButton")
        unlock_btn.clicked.connect(self._on_unlock_clicked)
        
        ping_btn = QPushButton("RING")
        ping_btn.setObjectName("navButton")
        ping_btn.clicked.connect(self._on_ring_clicked)
        
        disc_btn = QPushButton("DISCONNECT")
        disc_btn.setObjectName("navButton")
        disc_btn.setStyleSheet("color: #ff8888; border: 1px solid rgba(255, 60, 60, 0.3);")
        disc_btn.clicked.connect(self._on_disconnect_clicked)
        
        ctrl_btns.addWidget(unlock_btn)
        ctrl_btns.addWidget(ping_btn)
        ctrl_btns.addWidget(disc_btn)
        ctrl_layout.addLayout(ctrl_btns)
        right_col.addWidget(self.controls_card)

        # Notifications Title
        notif_header_layout = QHBoxLayout()
        notif_header = QLabel("RECENT NOTIFICATIONS")
        notif_header.setObjectName("panelTitle")
        notif_header_layout.addWidget(notif_header)
        notif_header_layout.addStretch()
        
        clear_btn = QPushButton("CLEAR ALL")
        clear_btn.setFixedSize(100, 24)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 60, 60, 0.2);
                border: 1px solid rgba(255, 60, 60, 0.5);
                border-radius: 4px;
                color: #ffcccc;
                font-family: 'Consolas';
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(255, 60, 60, 0.4);
            }
        """)
        clear_btn.clicked.connect(self.clear_all_notifications)
        notif_header_layout.addWidget(clear_btn)
        right_col.addLayout(notif_header_layout)

        # Notifications Scroll Area
        self.notif_scroll = QScrollArea()
        self.notif_scroll.setWidgetResizable(True)
        self.notif_scroll.setObjectName("chatScroll")
        self.notif_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 8px; background: rgba(0,0,0,0.2); border-radius: 4px; }
            QScrollBar::handle:vertical { background: rgba(0, 212, 255, 0.3); border-radius: 4px; }
        """)
        
        self.notif_container = QWidget()
        self.notif_container.setStyleSheet("background: transparent;")
        self.notif_layout = QVBoxLayout(self.notif_container)
        self.notif_layout.setSpacing(8)
        self.notif_layout.addStretch()
        self.notif_scroll.setWidget(self.notif_container)
        right_col.addWidget(self.notif_scroll, 1)

        main_h_row.addLayout(right_col, 3)
        layout.addLayout(main_h_row, 1)

    def _launch_mirroring(self):
        """Invoke scrcpy to mirror the phone screen"""
        try:
            import subprocess
            subprocess.Popen(["scrcpy", "--always-on-top", "--window-title", "JARVIS Mobile Mirror"])
        except Exception as e:
            print(f"Error launching scrcpy: {e}")

    def _toggle_full_screen(self):
        """Notify parent to hide navigation for full mobile view"""
        # This will be bubbled up to CenterContent
        if hasattr(self.parent(), "_on_mobile_fullscreen"):
             self.parent()._on_mobile_fullscreen()

    def show_incoming_call(self, caller, number, status):
        """Show call card when RINGING or ACTIVE, hide otherwise"""
        if status == "ringing":
            self.call_card.setVisible(True)
            self.caller_info.setText(f"{caller}\n{number}")
            self.ans_btn.setVisible(True)
            self.dec_btn.setText("DECLINE")
        elif status == "active":
            self.call_card.setVisible(True)
            self.ans_btn.setVisible(False)
            self.dec_btn.setText("END CALL")
        else:
            self.call_card.setVisible(False)

    def _answer_call(self):
        self.call_card.setVisible(False)
        event_bus.emit("mobile.command", {"command": "answer_call"})

    def _decline_call(self):
        self.call_card.setVisible(False)
        event_bus.emit("mobile.command", {"command": "decline_call"})

    def _on_ring_clicked(self):
        event_bus.emit("mobile.command", {"command": "ring_device"})

    def _on_disconnect_clicked(self):
        """Force disconnect from mobile"""
        if hasattr(self, "backend_thread") and self.backend_thread:
            # We don't have a direct "disconnect" command yet, 
            # but we can tell the server to drop the client or just stopDiscovery in UI
            self.update_status(False)
            # For now, just disconnect the local manager if we had one here
            # But usually it's better to just wait for socket to drop.
            pass

    def load_notifications(self):
        """Load existing notifications from storage"""
        if not self.notification_manager:
            return
            
        # Clear existing (except stretch)
        while self.notif_layout.count() > 1:
            item = self.notif_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        notifications = self.notification_manager.get_all()
        # Add in reverse order so newest is at top (insert 0)
        for notif in reversed(notifications):
            self._add_notification_card(
                notif.get('app_name', 'Unknown'),
                notif.get('title', ''),
                notif.get('text', ''),
                notif.get('id', '')
            )

    def update_status(self, connected, name="", device_id="", ip=""):
        status_text = "● ACTIVE" if connected else "● DISCONNECTED"
        self.conn_status.setText(status_text)
        self.conn_status.setObjectName("statusActive" if connected else "dashboardStatus")
        self.conn_status.style().unpolish(self.conn_status)
        self.conn_status.style().polish(self.conn_status)

        self.device_name.setText(f"Device: {name}")
        self.device_id.setText(f"ID: {device_id}")
        self.ip_addr.setText(f"Address: {ip}")

    def add_notification(self, app, title, text):
        # Refresh from storage to ensure we have the ID and consistency
        # Or just add it elegantly to the UI
        if self.notification_manager:
            # It should already be saved by backend, but let's reload to be safe
            # properly we should pass the full object or ID from backend
            QTimer.singleShot(100, self.load_notifications)
        else:
             self._add_notification_card(app, title, text)

    def _add_notification_card(self, app, title, text, notif_id=""):
        card = QFrame()
        card.setObjectName("statCard")
        card.setStyleSheet("""
            #statCard {
                background-color: rgba(12, 30, 50, 0.7);
                border: 1px solid rgba(0, 212, 255, 0.15);
                border-radius: 6px;
            }
            #statCard:hover {
                border: 1px solid rgba(0, 212, 255, 0.4);
                background-color: rgba(12, 30, 50, 0.9);
            }
        """)
        
        l = QVBoxLayout(card)
        l.setContentsMargins(10, 8, 10, 8)
        l.setSpacing(4)
        
        # Header row with app name and delete button
        header_row = QHBoxLayout()
        app_label = QLabel(app)
        app_label.setStyleSheet("color: #7ffbff; font-weight: bold; font-family: 'Consolas';")
        header_row.addWidget(app_label)
        header_row.addStretch()
        
        if notif_id and self.notification_manager:
            del_btn = QPushButton("×")
            del_btn.setFixedSize(20, 20)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setToolTip("Delete Notification")
            del_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #555;
                    border: none;
                    font-weight: bold;
                    font-size: 16px;
                }
                QPushButton:hover {
                    color: #ff5555;
                }
            """)
            del_btn.clicked.connect(lambda: self.delete_notification(notif_id, card))
            header_row.addWidget(del_btn)
            
        l.addLayout(header_row)
        
        if title:
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("color: #cfe8ff; font-weight: bold;")
            title_lbl.setWordWrap(True)
            l.addWidget(title_lbl)
            
        if text:
            text_lbl = QLabel(text)
            text_lbl.setStyleSheet("color: rgba(207, 232, 255, 0.7);")
            text_lbl.setWordWrap(True)
            l.addWidget(text_lbl)
            
        # Insert at top (index 0)
        self.notif_layout.insertWidget(0, card)

    def delete_notification(self, notif_id, card_widget):
        if self.notification_manager and notif_id:
            if self.notification_manager.delete(notif_id):
                card_widget.deleteLater()

    def clear_all_notifications(self):
        if self.notification_manager:
            self.notification_manager.clear_all()
            # Clear UI (except stretch)
            while self.notif_layout.count() > 1:
                item = self.notif_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

    def _on_unlock_clicked(self):
        """Unlock device using stored PIN or prompt for one"""
        from PyQt5.QtWidgets import QInputDialog, QLineEdit, QMessageBox
        
        # Check storage for stored PIN
        stored_pin = storage.get_profile_value("mobile_unlock_pin")
        
        if stored_pin:
            # Use stored PIN directly
            event_bus.emit("mobile.command", {"command": "unlock_device", "pin": stored_pin})
            # Visual feedback
            self.conn_status.setText("● UNLOCKING...")
            QTimer.singleShot(2000, lambda: self.update_status(True)) # Reset
        else:
            # Prompt for PIN
            pin, ok = QInputDialog.getText(
                self, "Remote Unlock", "Enter PIN (saved for future use):",
                QLineEdit.EchoMode.Password
            )
            
            if ok and pin:
                # Save PIN
                storage.set_profile_value("mobile_unlock_pin", pin)
                # Send command
                event_bus.emit("mobile.command", {"command": "unlock_device", "pin": pin})

class CommunicationPanel(QWidget):
    """Right-side communication panel with collapsible chat."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.excerpt_limit = 5 # Default to 5 lines
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
        title.setFont(QFont("Consolas", 10, QFont.Bold))
        header.addWidget(title)
        header.addStretch()

        self.collapse_btn = QPushButton()
        self.collapse_btn.setObjectName("collapseBtn")
        self.collapse_btn.setFixedSize(22, 22)
        self.collapse_btn.setCursor(Qt.PointingHandCursor)
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
        bubble_layout.setAlignment(Qt.AlignTop)

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
        
        # Check for excerpt truncation
        QTimer.singleShot(10, lambda: self._handle_excerpt(bubble, text_view))

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

    def _handle_excerpt(self, bubble, text_view):
        """Truncate long messages and add Expand button if necessary"""
        # Ensure we have a valid width for height calculation
        available_width = max(120, bubble.width() - 20)
        self._update_text_height(text_view, available_width)
        
        doc = text_view.document()
        # Roughly calculate lines based on standard line height (18px) vs total height
        # Or better: use block count if user uses newlines, but for wrapped text we check height
        line_height = 20 # Font size 14px + padding
        max_h = self.excerpt_limit * line_height
        
        actual_h = doc.size().height()
        
        if actual_h > max_h + 10:
            # Message is long, truncate and add Expand button
            text_view.setFixedHeight(max_h)
            
            expand_btn = QPushButton("Expand Conversation ↓")
            expand_btn.setObjectName("expandBtn")
            expand_btn.setCursor(Qt.PointingHandCursor)
            expand_btn.setStyleSheet("""
                QPushButton#expandBtn {
                    background: transparent;
                    color: #00d4ff;
                    border: none;
                    font-family: 'Consolas';
                    font-size: 11px;
                    text-align: left;
                    padding: 2px 0;
                }
                QPushButton#expandBtn:hover {
                    color: #00ffff;
                    text-decoration: underline;
                }
            """)
            
            bubble.layout().addWidget(expand_btn)
            expand_btn.clicked.connect(lambda: self._toggle_expansion(bubble, text_view, expand_btn))

    def _toggle_expansion(self, bubble, text_view, btn):
        """Toggle between excerpt and full view"""
        is_expanded = btn.text().startswith("Collapse")
        
        if is_expanded:
            # Collapse back
            line_height = 20
            text_view.setFixedHeight(self.excerpt_limit * line_height)
            btn.setText("Expand Conversation ↓")
        else:
            # Expand to full
            doc = text_view.document()
            full_h = doc.size().height()
            text_view.setFixedHeight(int(full_h) + 10)
            btn.setText("Collapse ↑")
        
        # Optional: scroll to show the expanded content
        self._scroll_to_bottom()

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
