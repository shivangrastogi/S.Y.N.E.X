import sys
import os
import threading
import time

# Set UTF-8 encoding for output
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))

# Use queue-based input for backend when running from GUI
os.environ["SYNEX_INPUT_MODE"] = "queue"

# Add project root to sys.path
sys.path.append(project_root)

# Change working directory to project root so backend can find DATA/
os.chdir(project_root)

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import Qt, QRect, QPoint, QEvent, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QCursor, QKeySequence, QShortcut, QPainter, QColor
from ui_laptop.title_bar import CustomTitleBar
from ui_laptop.center_content import CenterContent
from ui_laptop.voice_input import VoiceInputWidget
from BACKEND.main import Synex


class BackendThread(QThread):
    response_received = pyqtSignal(str)
    heard_received = pyqtSignal(str)
    gesture_status_received = pyqtSignal(bool, str, float)
    gesture_frame_received = pyqtSignal(object)
    gesture_event_received = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_requested = False
        # Not a daemon thread - will be properly stopped
        self.setTerminationEnabled(True)

    def run(self):
        """Run the backend in a separate thread"""
        try:
            self.synex = Synex()
            self.synex.set_response_callback(self.response_received.emit)
            self.synex.set_heard_callback(self.heard_received.emit)
            self.synex.set_gesture_status_callback(self.gesture_status_received.emit)
            self.synex.set_gesture_frame_callback(self.gesture_frame_received.emit)
            self.synex.set_gesture_event_callback(self.gesture_event_received.emit)
            self.synex.run()
        except Exception as e:
            print(f"Backend thread error: {e}")

    def submit_text(self, text: str):
        if hasattr(self, "synex") and not self._stop_requested:
            self.synex.submit_text(text)

    def start_voice_listening(self):
        if hasattr(self, "synex") and not self._stop_requested:
            self.synex.start_voice_listening()

    def stop_voice_listening(self):
        if hasattr(self, "synex") and not self._stop_requested:
            self.synex.stop_voice_listening()

    def shutdown(self):
        """Gracefully shutdown the backend thread"""
        self._stop_requested = True
        if hasattr(self, "synex"):
            try:
                self.synex.shutdown()
            except Exception as e:
                print(f"Shutdown error: {e}")

    def set_gesture_allowed(self, allowed: bool):
        """Enable/disable gesture mode from UI toggle"""
        if hasattr(self, "synex"):
            self.synex.set_gesture_allowed(allowed)


class SnapPreviewOverlay(QWidget):
    """Fullscreen preview overlay shown during drag-to-snap"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setVisible(False)
    
    def paintEvent(self, event):
        """Paint semi-transparent overlay with border"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Semi-transparent cyan fill
        painter.fillRect(self.rect(), QColor(0, 212, 255, 30))
        
        # Bright border
        painter.setPen(QColor(0, 212, 255, 200))
        painter.drawRect(self.rect().adjusted(2, 2, -2, -2))
        
        # Inner glow effect
        painter.setPen(QColor(0, 255, 255, 150))
        painter.drawRect(self.rect().adjusted(4, 4, -4, -4))
        
        painter.end()


class JARVISWindow(QMainWindow):
    """Main application window with custom title bar"""
    
    RESIZE_MARGIN = 10  # Pixels from edge to enable resizing
    MIN_WIDTH = 400
    MIN_HEIGHT = 300
    SNAP_THRESHOLD = 20  # Pixels from top edge to trigger snap preview
    
    def __init__(self):
        super().__init__()
        self.is_resizing = False
        self.resize_direction = None
        self.resize_start_pos = None
        self.resize_start_geometry = None
        self.snap_preview = SnapPreviewOverlay()
        self.is_snap_preview_active = False
        self.drag_start_pos = None  # Track drag start for threshold
        self.drag_threshold_met = False  # Whether drag threshold was met
        self.setup_ui()
        self.setup_window()

        # Start backend thread
        self.backend_thread = BackendThread()
        self.backend_thread.gesture_status_received.connect(self.on_gesture_status)
        self.backend_thread.gesture_frame_received.connect(self.on_gesture_frame)
        self.backend_thread.gesture_event_received.connect(self.on_gesture_event)
        self.backend_thread.response_received.connect(self.on_backend_response)
        self.backend_thread.heard_received.connect(self.on_voice_heard)
        self.backend_thread.start()
        
        # Pass backend thread to center_content for gesture toggle
        self.center_content._backend_thread = self.backend_thread

        # Watchdog to keep listening active when mic is on
        self.listening_watchdog = QTimer(self)
        self.listening_watchdog.timeout.connect(self._ensure_listening)
        self.listening_watchdog.start(2000)
    
    def setup_window(self):
        """Configure main window properties"""
        self.setWindowTitle("JARVIS - Personal Assistant")
        self.setGeometry(100, 100, 1200, 700)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True)  # Enable mouse tracking for cursor updates
        self.installEventFilter(self)
        
        # Apply main window styling with cyberpunk theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0a1628;
                color: #ffffff;
            }
        """)
    
    def setup_ui(self):
        """Setup the user interface"""
        # Create central widget and main layout
        central_widget = QWidget()
        central_widget.setMouseTracking(True)
        central_widget.installEventFilter(self)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create and add custom title bar
        self.title_bar = CustomTitleBar()
        self.title_bar.setMouseTracking(True)
        self.title_bar.installEventFilter(self)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self.toggle_maximize)
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.drag_position_changed.connect(self.on_drag_position_changed)
        main_layout.addWidget(self.title_bar)
        
        # Content area with trapezium and decorative elements
        self.center_content = CenterContent()
        self.center_content.setMouseTracking(True)
        self.center_content.installEventFilter(self)
        main_layout.addWidget(self.center_content, 1)
        
        # Voice input at the bottom
        self.voice_input = VoiceInputWidget()
        self.voice_input.send_clicked.connect(self.on_voice_input_send)
        self.voice_input.listening_changed.connect(self.center_content.set_listening)
        self.voice_input.listening_changed.connect(self.on_listening_changed)
        main_layout.addWidget(self.voice_input, 0)
        
        self.setCentralWidget(central_widget)
        self.setup_shortcuts()
    
    def on_voice_input_send(self, text):
        """Handle voice input send event"""
        print(f"User input: {text}")
        self.center_content.add_chat_message(text, "user")
        if hasattr(self, "backend_thread") and self.backend_thread.isRunning():
            self.backend_thread.submit_text(text)

    def on_backend_response(self, text: str):
        self.center_content.add_chat_message(text, "bot")

    def on_voice_heard(self, text: str):
        self.center_content.add_chat_message(text, "user")
        if hasattr(self, "voice_input"):
            self.voice_input.set_heard_text(text)

    def on_gesture_status(self, active: bool, gesture: str, fps: float):
        self.center_content.update_gesture_status(active, gesture, fps)

    def on_gesture_frame(self, frame):
        """Throttle frame updates to reduce flickering"""
        # Only update if enough time has passed (limit to ~15 FPS for preview)
        current_time = time.time()
        if not hasattr(self, '_last_frame_time'):
            self._last_frame_time = 0
        
        if current_time - self._last_frame_time >= 0.066:  # ~15 FPS (66ms)
            self._last_frame_time = current_time
            self.center_content.update_gesture_preview(frame)

    def on_gesture_event(self, gesture: str):
        self.center_content.update_gesture_event(gesture)

    def on_listening_changed(self, is_listening: bool):
        if hasattr(self, "backend_thread") and self.backend_thread.isRunning():
            if is_listening:
                self.backend_thread.start_voice_listening()
            else:
                self.backend_thread.stop_voice_listening()

    def _ensure_listening(self):
        if hasattr(self, "backend_thread") and self.backend_thread.isRunning():
            if self.voice_input.is_listening:
                self.backend_thread.start_voice_listening()

    def closeEvent(self, event):
        """Properly cleanup threads before closing"""
        if hasattr(self, "backend_thread") and self.backend_thread.isRunning():
            # Shutdown backend gracefully
            self.backend_thread.shutdown()
            # Wait for thread to finish (max 3 seconds)
            self.backend_thread.wait(3000)
            if self.backend_thread.isRunning():
                # Force terminate if still running
                self.backend_thread.terminate()
                self.backend_thread.wait(1000)
        
        # Stop any timers
        if hasattr(self, "listening_watchdog"):
            self.listening_watchdog.stop()
        
        super().closeEvent(event)

    def setup_shortcuts(self):
        """Setup Win+Arrow shortcuts for snapping"""
        shortcuts = [
            ("Meta+Left", self.snap_left),
            ("Meta+Right", self.snap_right),
            ("Meta+Up", self.snap_maximize),
            ("Meta+Down", self.snap_restore),
            ("Alt+Left", self.snap_left),
            ("Alt+Right", self.snap_right),
            ("Alt+Up", self.snap_maximize),
            ("Alt+Down", self.snap_restore),
            ("Ctrl+Alt+Left", self.snap_left),
            ("Ctrl+Alt+Right", self.snap_right),
            ("Ctrl+Alt+Up", self.snap_maximize),
            ("Ctrl+Alt+Down", self.snap_restore),
        ]
        for seq, handler in shortcuts:
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(handler)
    
    def toggle_maximize(self):
        """Toggle between maximized and normal state"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def on_drag_position_changed(self, global_pos, is_dragging, is_drag_start=False):
        """Handle drag position changes from title bar"""
        if not is_dragging:
            # Hide preview when drag ends
            if self.snap_preview.isVisible():
                self.snap_preview.hide()
            self.is_snap_preview_active = False
            self.drag_start_pos = None
            self.drag_threshold_met = False
            return
        
        # Track drag start position
        if is_drag_start:
            self.drag_start_pos = global_pos
            self.drag_threshold_met = False
            return
        
        # Don't show preview if already maximized
        if self.isMaximized():
            return
        
        # Check if drag threshold is met (10 pixels movement)
        if not self.drag_threshold_met and self.drag_start_pos is not None:
            delta_y = abs(global_pos.y() - self.drag_start_pos.y())
            delta_x = abs(global_pos.x() - self.drag_start_pos.x())
            if delta_y < 10 and delta_x < 10:
                # Not enough movement yet
                return
            self.drag_threshold_met = True
        
        # Get screen geometry
        screen = self.screen()
        screen_geom = screen.availableGeometry()
        
        # Check if cursor is near top edge
        if global_pos.y() <= screen_geom.top() + self.SNAP_THRESHOLD:
            # Show fullscreen preview
            if not self.snap_preview.isVisible():
                self.snap_preview.setGeometry(screen_geom)
                self.snap_preview.show()
                self.is_snap_preview_active = True
        else:
            # Hide preview when moved away from top
            if self.snap_preview.isVisible():
                self.snap_preview.hide()
                self.is_snap_preview_active = False
    
    def snap_on_release(self):
        """Snap window to maximized if preview was active"""
        if self.is_snap_preview_active:
            self.snap_preview.hide()
            self.is_snap_preview_active = False
            self.showMaximized()

    def snap_maximize(self):
        if not self.isMaximized():
            self.showMaximized()
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def snap_restore(self):
        if self.isMaximized():
            self.showNormal()
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def snap_left(self):
        screen = self.screen()
        if screen is None:
            return
        geom = screen.availableGeometry()
        if self.isMaximized():
            self.showNormal()
        self.setGeometry(geom.left(), geom.top(), geom.width() // 2, geom.height())

    def snap_right(self):
        screen = self.screen()
        if screen is None:
            return
        geom = screen.availableGeometry()
        if self.isMaximized():
            self.showNormal()
        half = geom.width() // 2
        self.setGeometry(geom.left() + half, geom.top(), half, geom.height())
    
    def get_resize_direction(self, pos):
        """Determine resize direction based on cursor position"""
        if self.isMaximized():
            return None
        x = pos.x()
        y = pos.y()
        width = self.width()
        height = self.height()
        
        at_left = x < self.RESIZE_MARGIN
        at_right = x > width - self.RESIZE_MARGIN
        at_top = y < self.RESIZE_MARGIN
        at_bottom = y > height - self.RESIZE_MARGIN
        
        if at_top and at_left:
            return "top-left"
        elif at_top and at_right:
            return "top-right"
        elif at_bottom and at_left:
            return "bottom-left"
        elif at_bottom and at_right:
            return "bottom-right"
        elif at_left:
            return "left"
        elif at_right:
            return "right"
        elif at_top:
            return "top"
        elif at_bottom:
            return "bottom"
        return None
    
    def update_cursor(self, pos):
        """Update cursor based on position"""
        if self.isMaximized():
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        direction = self.get_resize_direction(pos)
        
        cursor_map = {
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top-left": Qt.CursorShape.SizeFDiagCursor,
            "bottom-right": Qt.CursorShape.SizeFDiagCursor,
            "top-right": Qt.CursorShape.SizeBDiagCursor,
            "bottom-left": Qt.CursorShape.SizeBDiagCursor,
        }
        
        new_cursor = cursor_map.get(direction, Qt.CursorShape.ArrowCursor)
        self.setCursor(new_cursor)
    
    def mousePressEvent(self, event):
        """Handle mouse press for resizing"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.isMaximized():
                self.setCursor(Qt.CursorShape.ArrowCursor)
                return
            direction = self.get_resize_direction(event.pos())
            if direction:
                self.is_resizing = True
                self.resize_direction = direction
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geometry = self.geometry()
                event.accept()
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for resizing and cursor updates"""
        # Always update cursor to show resize directions
        if not self.is_resizing and not self.isMaximized():
            self.update_cursor(event.pos())
        
        if self.is_resizing and self.resize_direction:
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            new_geometry = QRect(self.resize_start_geometry)
            
            direction = self.resize_direction
            
            # Handle left edge
            if "left" in direction:
                new_geometry.setLeft(new_geometry.left() + delta.x())
            # Handle right edge
            if "right" in direction:
                new_geometry.setRight(new_geometry.right() + delta.x())
            # Handle top edge
            if "top" in direction:
                new_geometry.setTop(new_geometry.top() + delta.y())
            # Handle bottom edge
            if "bottom" in direction:
                new_geometry.setBottom(new_geometry.bottom() + delta.y())
            
            # Enforce minimum window size
            if new_geometry.width() >= self.MIN_WIDTH and new_geometry.height() >= self.MIN_HEIGHT:
                self.setGeometry(new_geometry)
            
            event.accept()
        else:
            event.ignore()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release for resizing"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_resizing = False
            self.resize_direction = None
            self.resize_start_pos = None
            self.resize_start_geometry = None
            if not self.isMaximized():
                self.update_cursor(self.mapFromGlobal(QCursor.pos()))
            event.accept()
    
    def leaveEvent(self, event):
        """Handle mouse leaving window - reset cursor"""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.HoverMove):
            global_pos = event.globalPosition().toPoint()
            local_pos = self.mapFromGlobal(global_pos)
            if self.is_resizing and self.resize_direction:
                delta = global_pos - self.resize_start_pos
                new_geometry = QRect(self.resize_start_geometry)
                direction = self.resize_direction
                if "left" in direction:
                    new_geometry.setLeft(new_geometry.left() + delta.x())
                if "right" in direction:
                    new_geometry.setRight(new_geometry.right() + delta.x())
                if "top" in direction:
                    new_geometry.setTop(new_geometry.top() + delta.y())
                if "bottom" in direction:
                    new_geometry.setBottom(new_geometry.bottom() + delta.y())
                if new_geometry.width() >= self.MIN_WIDTH and new_geometry.height() >= self.MIN_HEIGHT:
                    self.setGeometry(new_geometry)
                return True
            else:
                if not self.isMaximized():
                    self.update_cursor(local_pos)
        elif event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if self.isMaximized():
                return super().eventFilter(obj, event)
            global_pos = event.globalPosition().toPoint()
            local_pos = self.mapFromGlobal(global_pos)
            direction = self.get_resize_direction(local_pos)
            if direction:
                self.is_resizing = True
                self.resize_direction = direction
                self.resize_start_pos = global_pos
                self.resize_start_geometry = self.geometry()
                return True
        elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self.is_resizing:
                self.is_resizing = False
                self.resize_direction = None
                self.resize_start_pos = None
                self.resize_start_geometry = None
                if not self.isMaximized():
                    self.update_cursor(self.mapFromGlobal(QCursor.pos()))
                return True
        elif event.type() == QEvent.Type.Leave:
            if not self.is_resizing:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().eventFilter(obj, event)


def main():
    """Main application entry point"""
    app = QApplication.instance()  # Get existing instance if available
    if app is None:
        app = QApplication(sys.argv)
    
    window = JARVISWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
