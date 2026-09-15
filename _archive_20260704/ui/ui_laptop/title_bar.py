# Path: d:\New folder (2) - JARVIS\ui_laptop\title_bar.py
# File: ui_laptop/title_bar.py
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PyQt5.QtGui import QPixmap, QIcon, QFont, QPainter, QPen, QColor, QBrush, QLinearGradient, QPainterPath
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QPoint, QRect, QPointF
from PyQt5.QtCore import QTimer
from aeris.ui_laptop.config import (
    LOGO_PATH, MINIMIZE_ICON_PATH, MAXIMIZE_ICON_PATH, CLOSE_ICON_PATH, TRAY_ICON_PATH,
    TITLE_BAR_HEIGHT, BUTTON_SIZE, LOGO_WIDTH, LOGO_HEIGHT
)


class CustomTitleBar(QWidget):
    """Custom title bar with logo and window control buttons"""
    
    # Signals for window control
    minimize_clicked = pyqtSignal()
    tray_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()
    close_clicked = pyqtSignal()
    drag_position_changed = pyqtSignal(QPoint, bool, bool)  # global_pos, is_dragging, is_drag_start
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_maximized = False
        self.drag_position = None
        self.setup_ui()
        self.apply_styles()
    
    def setup_ui(self):
        """Setup the title bar UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)
        
        # Logo
        self.logo_label = QLabel()
        self.set_logo()
        layout.addWidget(self.logo_label)
        
        # Spacer (stretch to center the status text)
        layout.addStretch()
        
        # Spacer (stretch to push buttons to right)
        layout.addStretch()
        
        # Spacer (stretch to push buttons to right)
        layout.addStretch()
        
        # Minimize button
        self.minimize_btn = self.create_button(MINIMIZE_ICON_PATH, "Minimize")
        self.minimize_btn.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self.minimize_btn)
        
        # Tray button (Minimize to Tray)
        self.tray_btn = self.create_button(TRAY_ICON_PATH, "Minimize to Tray")
        self.tray_btn.clicked.connect(self.tray_clicked.emit)
        layout.addWidget(self.tray_btn)
        
        # Maximize button
        self.maximize_btn = self.create_button(MAXIMIZE_ICON_PATH, "Maximize")
        self.maximize_btn.clicked.connect(self.on_maximize_clicked)
        layout.addWidget(self.maximize_btn)
        
        # Close button
        self.close_btn = self.create_button(CLOSE_ICON_PATH, "Close")
        self.close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.close_btn)
        
        self.setLayout(layout)
        self.setFixedHeight(TITLE_BAR_HEIGHT)
    
    def set_logo(self):
        """Load and scale logo with high-DPI support"""
        try:
            pixmap = QPixmap(LOGO_PATH)
            if not pixmap.isNull():
                # efficient height calculation
                avail_height = self.height() - 8
                target_height = max(30, avail_height)
                
                # High DPI scaling
                dpr = self.devicePixelRatio()
                target_height_phys = int(target_height * dpr)
                
                scaled_pixmap = pixmap.scaledToHeight(
                    target_height_phys,
                    Qt.SmoothTransformation
                )
                scaled_pixmap.setDevicePixelRatio(dpr)
                
                self.logo_label.setPixmap(scaled_pixmap)
                # Adjust width based on logical size
                self.logo_label.setMinimumWidth(int(scaled_pixmap.width() / dpr))
            else:
                self.logo_label.setText("JARVIS")
        except Exception as e:
            print(f"Error loading logo: {e}")
            self.logo_label.setText("JARVIS")
    
    def create_button(self, icon_path, tooltip):
        """Create a styled button with icon"""
        btn = QPushButton()
        btn.setToolTip(tooltip)
        icon_size = 20
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.PointingHandCursor)
        
        try:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaledToWidth(
                    icon_size,
                    Qt.SmoothTransformation
                )
                icon = QIcon(scaled_pixmap)
                btn.setIcon(icon)
                btn.setIconSize(QSize(icon_size, icon_size))
        except Exception as e:
            print(f"Error loading icon: {e}")
        
        return btn
    

    
    def on_maximize_clicked(self):
        """Toggle maximize/restore"""
        self.is_maximized = not self.is_maximized
        self.maximize_clicked.emit()
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPos()
            self._press_local = event.pos()
            self._restore_ready = False
            self._restore_ratio = None
            self.drag_position = event.globalPos() - self.window().frameGeometry().topLeft()
            # Emit drag start
            self.drag_position_changed.emit(event.globalPos(), True, True)
            event.accept()
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to maximize/restore"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Don't process double-click on buttons
            widget_at_pos = self.childAt(event.pos())
            if widget_at_pos in [self.minimize_btn, self.maximize_btn, self.close_btn]:
                return
            
            # Toggle maximize/restore
            self.maximize_clicked.emit()
            event.accept()
    
    def resizeEvent(self, event):
        """Handle resize events to update element sizes"""
        super().resizeEvent(event)
        self.set_logo()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging window with boundary checking"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.window().setCursor(Qt.ArrowCursor)
            global_pos = event.globalPos()
            
            # If maximized, restore on drag and keep cursor position
            if self.window().isMaximized():
                restore_pos = global_pos
                local_pos = event.pos()

                # Wait for small drag before restoring for smoother feel
                if not self._restore_ready:
                    delta = restore_pos - self._press_pos
                    if abs(delta.y()) < 6:
                        return
                    self._restore_ready = True

                # Use the original press position ratio across the maximized width
                if self._restore_ratio is None:
                    max_width = max(1, self.window().width())
                    self._restore_ratio = min(0.95, max(0.05, self._press_local.x() / max_width))

                self.window().showNormal()
                restored_width = self.window().width()
                restored_height = self.window().height()
                offset_x = int(restored_width * self._restore_ratio)
                offset_y = min(self._press_local.y(), self.height())
                target_x = restore_pos.x() - offset_x
                target_y = restore_pos.y() - offset_y
                self.drag_position = QPoint(offset_x, offset_y)
                self.window().move(target_x, target_y)

            # Calculate new window position
            new_pos = global_pos - self.drag_position
            
            # Get screen geometry - prevent window from going above screen
            screen_geom = self.window().screen().availableGeometry()
            
            # Block window from going above screen top
            if new_pos.y() < screen_geom.top():
                new_pos.setY(screen_geom.top())
            
            self.window().move(new_pos)
            
            # Notify about drag position for snap preview
            self.drag_position_changed.emit(global_pos, True, False)
            
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release - trigger snap if preview was active"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Trigger snap first before notifying drag ended
            if hasattr(self.window(), 'snap_on_release'):
                self.window().snap_on_release()
            # Now notify drag ended
            self.drag_position_changed.emit(event.globalPos(), False, False)
            self.drag_position = None
            event.accept()
    
    def apply_styles(self):
        """Apply stylesheet for title bar"""
        self.setStyleSheet("""
            CustomTitleBar {
                background-color: transparent;
                border-bottom: 1px solid #0b3a55;
            }
            
            QLabel {
                color: #ffffff;
            }
            
            QPushButton {
                background-color: rgba(20, 30, 45, 0.6);
                border: 1px solid rgba(0, 212, 255, 0.2);
                border-radius: 6px;
                padding: 4px;
            }
            
            QPushButton:hover {
                background-color: rgba(30, 50, 70, 0.8);
                border: 1px solid rgba(0, 212, 255, 0.5);
                border-radius: 6px;
            }
            
            QPushButton:pressed {
                background-color: rgba(0, 212, 255, 0.3);
                border: 1px solid rgba(0, 255, 255, 0.8);
                border-radius: 6px;
            }
        """)
    
    def paintEvent(self, event):
        """Paint background gradient and decorative elements"""
        # Draw gradient background first
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#152839"))
        gradient.setColorAt(0.5, QColor("#0a1a2a"))
        gradient.setColorAt(1, QColor("#060f1c"))

        painter.fillRect(self.rect(), gradient)

        # Outer frame
        frame_pen = QPen(QColor("#2b6a86"))
        frame_pen.setWidth(1)
        painter.setPen(frame_pen)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        # Top highlight line (3D bevel)
        highlight_pen = QPen(QColor("#4fb7d6"))
        highlight_pen.setWidth(1)
        painter.setPen(highlight_pen)
        painter.drawLine(1, 1, self.width() - 2, 1)

        # Bottom shadow line (3D depth)
        shadow_pen = QPen(QColor("#062033"))
        shadow_pen.setWidth(1)
        painter.setPen(shadow_pen)
        painter.drawLine(1, self.height() - 2, self.width() - 2, self.height() - 2)

        painter.end()
        
        # Call parent paint to render widgets
        super().paintEvent(event)
        
        # Paint decorative elements on top
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        self.draw_grand_outer_trapezium(painter)
        self.draw_decorative_lines(painter, left_side=True)
        self.draw_status_trapezium(painter)
        self.draw_decorative_lines(painter, left_side=False)
        
        painter.end()
    
    def draw_grand_outer_trapezium(self, painter):
        """Draw a large outer trapezium that contains everything"""
        width = self.width()
        height = self.height()
        cx = width / 2
        cy = height / 2
        
        # Dimensions to encompass everything (Wings + Inner Trap)
        # Content width approx 480px (400 trap + 40 wing space each side)
        total_content_width = 520 
        outer_h = 40
        
        # Calculate trapezoid points (Wider at top, narrower at bottom)
        # Shape: /----\
        top_w = total_content_width
        bottom_w = total_content_width - 60 # Taper in
        
        top_left = QPointF(cx - top_w/2, cy - outer_h/2)
        top_right = QPointF(cx + top_w/2, cy - outer_h/2)
        bottom_right = QPointF(cx + bottom_w/2, cy + outer_h/2)
        bottom_left = QPointF(cx - bottom_w/2, cy + outer_h/2)
        
        path = QPainterPath()
        path.moveTo(top_left)
        path.lineTo(top_right)
        path.lineTo(bottom_right)
        path.lineTo(bottom_left)
        path.closeSubpath()
        
        # Style
        # Very dark transparent background
        painter.setBrush(QColor(0, 0, 0, 180))
        # Subtle border
        painter.setPen(QPen(QColor("#0b3a55"), 1))
        painter.drawPath(path)
        
        # Add a "tech" border effect? Maybe just simple for now.
    
    def draw_decorative_lines(self, painter, left_side=True):
        """Draw cascading waterfall-style horizontal lines around the trapezium"""
        width = self.width()
        height = self.height()
        
        trapezium_width = 400
        start_x = (width - trapezium_width) // 2
        center_y = height // 2
        
        line_spacing = 5
        num_lines = 5
        line_length = 25
        
        if left_side:
            base_x = start_x - 15
            for i in range(num_lines):
                y = center_y - (num_lines * line_spacing // 2) + (i * line_spacing)
                offset = i * 5
                
                if i == num_lines - 1:
                    pen = QPen()
                    pen.setColor(QColor("#FF8C00"))
                    pen.setWidth(4)
                    painter.setPen(pen)
                    painter.drawLine(base_x - line_length + offset, y, base_x + offset, y)
                else:
                    pen = QPen()
                    pen.setColor(QColor("#ffffff"))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.drawLine(base_x - line_length + offset, y, base_x + offset, y)
        else:
            base_x = start_x + trapezium_width + 15
            for i in range(num_lines):
                y = center_y - (num_lines * line_spacing // 2) + (i * line_spacing)
                offset = i * 5
                
                if i == num_lines - 1:
                    pen = QPen()
                    pen.setColor(QColor("#FF8C00"))
                    pen.setWidth(4)
                    painter.setPen(pen)
                    painter.drawLine(base_x - offset, y, base_x + line_length - offset, y)
                else:
                    pen = QPen()
                    pen.setColor(QColor("#ffffff"))
                    pen.setWidth(2)
                    painter.setPen(pen)
                    painter.drawLine(base_x - offset, y, base_x + line_length - offset, y)
    
    def draw_status_trapezium(self, painter):
        """Draw trapezium with 3D effect"""
        width = self.width()
        height = self.height()
        
        trapezium_width = 400
        trapezium_height = 25
        start_x = (width - trapezium_width) // 2
        start_y = (height - trapezium_height) // 2
        
        # Slim trapezium with narrower top and bottom
        offset_top = 15
        offset_bottom = 25
        
        top_left = QPoint(start_x + offset_top, start_y)
        top_right = QPoint(start_x + trapezium_width - offset_top, start_y)
        bottom_right = QPoint(start_x + trapezium_width - offset_bottom, start_y + trapezium_height)
        bottom_left = QPoint(start_x + offset_bottom, start_y + trapezium_height)
        
        points = [top_left, top_right, bottom_right, bottom_left]
        
        # Draw main trapezium with semi-transparent fill
        brush = QBrush(QColor(0, 150, 200, 40))
        painter.setBrush(brush)
        
        pen = QPen()
        pen.setColor(QColor("#00d4ff"))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawPolygon(points)
        
        # Draw top highlight (3D effect)
        highlight_pen = QPen()
        highlight_pen.setColor(QColor("#00ffff"))
        highlight_pen.setWidth(1)
        painter.setPen(highlight_pen)
        painter.drawLine(top_left, top_right)
        
        # Draw bottom shadow (3D effect)
        shadow_pen = QPen()
        shadow_pen.setColor(QColor("#004466"))
        shadow_pen.setWidth(1)
        painter.setPen(shadow_pen)
        painter.drawLine(bottom_left, bottom_right)
        
        # Draw orange accent lines at bottom edges
        accent_pen = QPen()
        accent_pen.setColor(QColor("#FF8C00"))
        accent_pen.setWidth(1)
        painter.setPen(accent_pen)
        painter.drawLine(bottom_left, QPoint(bottom_left.x() + 5, bottom_left.y() + 3))
        painter.drawLine(bottom_right, QPoint(bottom_right.x() - 5, bottom_right.y() + 3))

        # --- Draw Text (Centered) ---
        text = "ONLINE - SECURE - READY"
        painter.setPen(QColor("#ffffff"))
        font = QFont("Courier New", 10, QFont.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
        painter.setFont(font)
        
        # Draw centrally in the container
        # Use full width/height rect but with center alignment
        text_rect = QRect(start_x, start_y, trapezium_width, trapezium_height)
        painter.drawText(text_rect, Qt.AlignCenter, text)
