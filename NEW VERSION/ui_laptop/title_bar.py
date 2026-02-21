from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtGui import QPixmap, QIcon, QFont, QPainter, QPen, QColor, QBrush, QLinearGradient
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint, QRect
from PyQt6.QtCore import QTimer
from ui_laptop.config import (
    LOGO_PATH, MINIMIZE_ICON_PATH, MAXIMIZE_ICON_PATH, CLOSE_ICON_PATH,
    TITLE_BAR_HEIGHT, BUTTON_SIZE, LOGO_WIDTH, LOGO_HEIGHT
)


class CustomTitleBar(QWidget):
    """Custom title bar with logo and window control buttons"""
    
    # Signals for window control
    minimize_clicked = pyqtSignal()
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
        layout.setContentsMargins(10, 5, 15, 5)
        layout.setSpacing(15)
        
        # Logo
        self.logo_label = QLabel()
        self.set_logo()
        layout.addWidget(self.logo_label)
        
        # Spacer (stretch to center the status text)
        layout.addStretch()
        
        # Status text (ONLINE - SECURE - READY) - CENTERED
        self.status_label = QLabel("ONLINE - SECURE - READY")
        self.update_status_font()
        self.status_label.setStyleSheet("""
            color: #ffffff;
            font-family: 'Courier New', monospace;
            text-transform: uppercase;
            letter-spacing: 1px;
        """)
        layout.addWidget(self.status_label)
        
        # Spacer (stretch to push buttons to right)
        layout.addStretch()
        
        # Minimize button
        self.minimize_btn = self.create_button(MINIMIZE_ICON_PATH, "Minimize")
        self.minimize_btn.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self.minimize_btn)
        
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
        """Load and scale logo based on available height"""
        try:
            pixmap = QPixmap(LOGO_PATH)
            if not pixmap.isNull():
                height = max(30, self.height() - 10)
                scaled_pixmap = pixmap.scaledToHeight(
                    height,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.logo_label.setPixmap(scaled_pixmap)
                self.logo_label.setMinimumWidth(scaled_pixmap.width())
            else:
                self.logo_label.setText("JARVIS")
        except Exception as e:
            print(f"Error loading logo: {e}")
            self.logo_label.setText("JARVIS")
    
    def create_button(self, icon_path, tooltip):
        """Create a styled button with icon"""
        btn = QPushButton()
        btn.setToolTip(tooltip)
        icon_size = max(18, BUTTON_SIZE - 10)
        btn.setFixedSize(icon_size + 6, icon_size + 6)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        try:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaledToWidth(
                    BUTTON_SIZE - 10,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon = QIcon(scaled_pixmap)
                btn.setIcon(icon)
                btn.setIconSize(QSize(icon_size, icon_size))
        except Exception as e:
            print(f"Error loading icon: {e}")
        
        return btn
    
    def update_status_font(self):
        """Update status label font size based on available space"""
        font_size = max(8, min(12, self.height() // 4))
        font = QFont("Courier New", font_size, QFont.Weight.Bold)
        self.status_label.setFont(font)
    
    def on_maximize_clicked(self):
        """Toggle maximize/restore"""
        self.is_maximized = not self.is_maximized
        self.maximize_clicked.emit()
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._press_local = event.position().toPoint()
            self._restore_ready = False
            self._restore_ratio = None
            self.drag_position = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            # Emit drag start
            self.drag_position_changed.emit(event.globalPosition().toPoint(), True, True)
            event.accept()
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to maximize/restore"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Don't process double-click on buttons
            widget_at_pos = self.childAt(event.position().toPoint())
            if widget_at_pos in [self.minimize_btn, self.maximize_btn, self.close_btn]:
                return
            
            # Toggle maximize/restore
            self.maximize_clicked.emit()
            event.accept()
    
    def resizeEvent(self, event):
        """Handle resize events to update element sizes"""
        super().resizeEvent(event)
        self.set_logo()
        self.update_status_font()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging window with boundary checking"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.window().setCursor(Qt.CursorShape.ArrowCursor)
            global_pos = event.globalPosition().toPoint()
            
            # If maximized, restore on drag and keep cursor position
            if self.window().isMaximized():
                restore_pos = global_pos
                local_pos = event.position().toPoint()

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
            self.drag_position_changed.emit(event.globalPosition().toPoint(), False, False)
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
                background-color: transparent;
                border: none;
                padding: 0px;
            }
            
            QPushButton:hover {
                background-color: rgba(0, 212, 255, 40);
                border-radius: 4px;
            }
            
            QPushButton:pressed {
                background-color: rgba(0, 153, 204, 60);
                border-radius: 4px;
            }
        """)
    
    def paintEvent(self, event):
        """Paint background gradient and decorative elements"""
        # Draw gradient background first
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self.draw_decorative_lines(painter, left_side=True)
        self.draw_status_trapezium(painter)
        self.draw_decorative_lines(painter, left_side=False)
        
        painter.end()
    
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
