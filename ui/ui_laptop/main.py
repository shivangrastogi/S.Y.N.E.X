# Path: d:\New folder (2) - JARVIS\ui_laptop\main.py
# File: ui_laptop/main.py

import sys
import os
import threading
import time

# Set UTF-8 encoding for output
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Workspace paths handled by absolute imports in aeris package

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QSystemTrayIcon, QMenu, QMessageBox, QShortcut, QAction
)
from PyQt5.QtCore import Qt, QRect, QPoint, QEvent, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QCursor, QKeySequence, QPainter, QColor, QIcon
from aeris.ui_laptop.title_bar import CustomTitleBar
from aeris.ui_laptop.center_content import CenterContent
from aeris.ui_laptop.voice_input import VoiceInputWidget
from aeris.ui_laptop.splash_screen import SplashWindow

from aeris.ui.event_bridge import ui_bridge
from aeris.core.event_bus import event_bus
from aeris.core.brain_router import brain_router
from aeris.core.state_manager import state_manager, AssistantState
from aeris.memory.storage import storage
from aeris.utils.logger import logger

class SnapPreviewOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setVisible(False)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 212, 255, 30))
        painter.setPen(QColor(0, 212, 255, 200))
        painter.drawRect(self.rect().adjusted(2, 2, -2, -2))
        painter.setPen(QColor(0, 255, 255, 150))
        painter.drawRect(self.rect().adjusted(4, 4, -4, -4))
        painter.end()


class JARVISWindow(QMainWindow):
    RESIZE_MARGIN = 10
    MIN_WIDTH = 400
    MIN_HEIGHT = 300
    SNAP_THRESHOLD = 20
    
    def __init__(self):
        super().__init__()
        self.is_resizing = False
        self.resize_direction = None
        self.resize_start_pos = None
        self.resize_start_geometry = None
        self.snap_preview = SnapPreviewOverlay()
        self.is_snap_preview_active = False
        self.drag_start_pos = None
        self.drag_threshold_met = False
        self.setup_ui()
        self.setup_window()

        self._connect_signals()
        self.setup_tray_icon()
        
        # We cannot connect these here because voice_input is deferred
        # Connection logic is moved to _add_voice_input()

    def _connect_signals(self):
        ui_bridge.state_changed.connect(self.on_state_changed)
        ui_bridge.text_heard.connect(self.on_voice_heard)
        ui_bridge.partial_text_heard.connect(self.on_partial_text_heard)
        ui_bridge.gesture_status.connect(self.on_gesture_status)
        ui_bridge.gesture_frame.connect(self.on_gesture_frame)
        ui_bridge.gesture_event.connect(self.on_gesture_event)
        ui_bridge.user_profile.connect(self.on_user_profile)
        ui_bridge.lock_state.connect(self.on_lock_state)
        ui_bridge.settings_received.connect(self.on_settings_received)
        ui_bridge.mobile_notification.connect(self.on_mobile_notification)
        ui_bridge.device_status.connect(self.on_device_status)
        ui_bridge.incoming_call.connect(self.on_incoming_call)
        ui_bridge.google_status.connect(self.center_content.settings_page.update_google_status)
        ui_bridge.voice_list.connect(self.center_content.settings_page.set_available_voices)
        ui_bridge.download_progress.connect(self.center_content.settings_page.update_install_progress)
        ui_bridge.image_started.connect(self.center_content.on_image_generation_started)
        ui_bridge.image_finished.connect(self.center_content.on_image_generation_finished)
        ui_bridge.image_progress.connect(self.center_content.on_image_generation_progress)
        ui_bridge.task_started.connect(self._on_task_started)
        ui_bridge.task_completed.connect(self._on_task_completed)
        ui_bridge.task_cancelled.connect(self._on_task_cancelled)

    def on_state_changed(self, new_state: str):
        self.center_content.set_assistant_state(new_state)
        if hasattr(self, "voice_input"):
            self.voice_input.set_assistant_state(new_state)
            # Update indicator visibility if needed
            self.voice_input.listening_label.setVisible(new_state == "LISTENING")
            if new_state == "LISTENING":
                self.voice_input.waveform_animation.start_animation()
            else:
                self.voice_input.waveform_animation.stop_animation()

    def _on_listening_toggle_requested(self, should_listen: bool):
        from aeris.voice.stt_worker import stt_worker
        if should_listen:
            stt_worker.start()
            logger.info("UI: Mic enabled (STT started).")
        else:
            stt_worker.stop()
            logger.info("UI: Mic disabled (STT stopped).")

    def _on_task_started(self, payload: dict):
        self.center_content.add_chat_message(f"Executing: {payload.get('intent')}", "bot")

    def _on_task_completed(self, payload: dict):
        # Already handled by individual responses, but can show status
        pass

    def _on_task_cancelled(self, reason: str):
        self.center_content.add_chat_message(f"Task Cancelled: {reason}", "bot")

    def on_partial_text_heard(self, text: str):
        # Laptop UI doesn't seem to have a dedicated partial text area.
        pass
    
    def setup_window(self):
        self.setWindowTitle("JARVIS - Personal Assistant")
        self.setGeometry(100, 100, 1200, 700)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        self.installEventFilter(self)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0a1628;
                color: #ffffff;
            }
        """)
    
    def setup_ui(self):
        central_widget = QWidget()
        central_widget.setMouseTracking(True)
        central_widget.installEventFilter(self)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.title_bar = CustomTitleBar()
        self.title_bar.setMouseTracking(True)
        self.title_bar.installEventFilter(self)
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        # self.title_bar.tray_clicked.connect(self.hide_to_tray) # Removed as per user request
        self.title_bar.maximize_clicked.connect(self.toggle_maximize)
        self.title_bar.close_clicked.connect(self.close)
        self.title_bar.drag_position_changed.connect(self.on_drag_position_changed)
        main_layout.addWidget(self.title_bar)
        # Hide the tray button in the title bar
        self.title_bar.tray_btn.setVisible(False)
        
        self.center_content = CenterContent()
        self.center_content.setMouseTracking(True)
        self.center_content.installEventFilter(self)
        main_layout.addWidget(self.center_content, 1)
        
        self.voice_input = None
        self.setCentralWidget(central_widget)
        self.setup_shortcuts()
        
        # Defer construction of the heavy mic widget to allow window to paint first
        QTimer.singleShot(50, self._add_voice_input)
        
    def _add_voice_input(self):
        self.voice_input = VoiceInputWidget()
        self.voice_input.send_clicked.connect(self.on_voice_input_send)
        self.voice_input.listening_changed.connect(self.on_listening_changed)
        self.voice_input.create_profile_requested.connect(self.on_create_profile_requested)
        self.voice_input.login_requested.connect(self.on_login_requested)
        self.voice_input.logout_requested.connect(self.on_logout_requested)
        self.voice_input.avatar_change_requested.connect(self.on_avatar_change_requested)
        self.voice_input.lock_toggle_requested.connect(self.on_lock_toggle_requested)
        
        self.voice_input.is_listening = False
        self.voice_input.listening_label.setVisible(False)
        self.voice_input.waveform_animation.stop_animation()
        
        # Add to the layout we created in setup_ui()
        central_widget = self.centralWidget()
        if central_widget and central_widget.layout():
            central_widget.layout().addWidget(self.voice_input, 0)
    
    def on_voice_input_send(self, text):
        self.center_content.add_chat_message(text, "user")
        # Route directly to brain router with text source to bypass wake-word logic
        brain_router.process_input(text, source="text")

    def on_backend_response(self, text: str):
        self.center_content.add_chat_message(text, "bot")

    def on_excerpt_limit_changed(self, limit: int):
        if hasattr(self.center_content, "communication_panel"):
            self.center_content.communication_panel.excerpt_limit = limit

    def on_voice_heard(self, text: str):
        self.center_content.add_chat_message(text, "user")

    def on_gesture_status(self, active: bool, gesture: str, fps: float):
        if hasattr(self.center_content, "update_gesture_status"):
            self.center_content.update_gesture_status(active, gesture, fps)

    def on_gesture_frame(self, frame):
        # Throttle preview updates
        current_time = time.time()
        if not hasattr(self, '_last_frame_time'):
            self._last_frame_time = 0
        if current_time - self._last_frame_time >= 0.066:
            self._last_frame_time = current_time
            if hasattr(self.center_content, "update_gesture_preview"):
                self.center_content.update_gesture_preview(frame)

    def on_gesture_event(self, gesture: str):
        if hasattr(self.center_content, "update_gesture_event"):
            self.center_content.update_gesture_event(gesture)

    def on_user_profile(self, profile: dict):
        if hasattr(self, "voice_input"):
            self.voice_input.set_user_profile(profile)

    def on_lock_state(self, locked: bool):
        if hasattr(self, "voice_input"):
            self.voice_input.set_lock_state(locked)

    def on_settings_received(self, settings: dict):
        if hasattr(self.center_content, "apply_settings"):
            self.center_content.apply_settings(settings)

    def on_mobile_notification(self, app, title, text):
        if hasattr(self.center_content, "update_mobile_notification"):
            self.center_content.update_mobile_notification(app, title, text)

    def on_device_status(self, connected, name, device_id, ip):
        if hasattr(self.center_content, "update_mobile_status"):
            self.center_content.update_mobile_status(connected, name, device_id, ip)

    def on_create_profile_requested(self, payload: dict):
        # We don't have a direct "create user" event yet, but we can update profile
        storage.set_profile_value("user_name", payload.get("username", "User"))
        if payload.get("avatar_path"):
            storage.set_profile_value("avatar_path", payload.get("avatar_path"))
        # Emit update
        event_bus.emit("system.user_profile", storage.get_all_profile_values())

    def on_login_requested(self, payload: dict):
        # Simple local login simulation for now
        logger.info(f"Login requested for {payload.get('username')}")
        event_bus.emit("system.user_profile", {"username": payload.get("username"), "logged_in": True})

    def on_logout_requested(self):
        event_bus.emit("system.user_profile", {"logged_in": False})

    def on_avatar_change_requested(self, avatar_path):
        storage.set_profile_value("avatar_path", avatar_path)
        event_bus.emit("system.user_profile", storage.get_all_profile_values())

    def on_lock_toggle_requested(self):
        is_locked = storage.get_profile_value("locked", False)
        storage.set_profile_value("locked", not is_locked)
        event_bus.emit("system.lock_state", {"locked": not is_locked})

    def on_listening_changed(self, is_listening: bool):
        if is_listening:
            state_manager.transition_to(AssistantState.LISTENING)
        else:
            state_manager.transition_to(AssistantState.IDLE)

    def _ensure_listening(self):
        pass

    def closeEvent(self, event):
        # Hide tray icon immediately so user knows it's closing
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
            
        # Signal shutdown to core
        event_bus.emit("system.shutdown_requested", {})
        super().closeEvent(event)

    def setup_shortcuts(self):
        shortcuts = [
            ("Meta+Left", self.snap_left),
            ("Meta+Right", self.snap_right),
            ("Meta+Up", self.snap_maximize),
            ("Meta+Down", self.snap_restore),
        ]
        for seq, handler in shortcuts:
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(handler)
    
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.setCursor(Qt.ArrowCursor)
    
    def on_drag_position_changed(self, global_pos, is_dragging, is_drag_start=False):
        if not is_dragging:
            if self.snap_preview.isVisible():
                self.snap_preview.hide()
            if self.is_snap_preview_active:
                self.showMaximized()
            self.is_snap_preview_active = False
            self.drag_start_pos = None
            self.drag_threshold_met = False
            return
        
        if is_drag_start:
            self.drag_start_pos = global_pos
            self.drag_threshold_met = False
            return
        
        if self.isMaximized():
            return
        
        if not self.drag_threshold_met and self.drag_start_pos is not None:
            delta_y = abs(global_pos.y() - self.drag_start_pos.y())
            delta_x = abs(global_pos.x() - self.drag_start_pos.x())
            if delta_y < 10 and delta_x < 10:
                return
            self.drag_threshold_met = True
        
        screen = self.screen()
        screen_geom = screen.availableGeometry()
        
        if global_pos.y() <= screen_geom.top() + self.SNAP_THRESHOLD:
            if not self.snap_preview.isVisible():
                self.snap_preview.setGeometry(screen_geom)
                self.snap_preview.show()
                self.is_snap_preview_active = True
        else:
            if self.snap_preview.isVisible():
                self.snap_preview.hide()
                self.is_snap_preview_active = False
                
    def snap_maximize(self):
        if not self.isMaximized():
            self.showMaximized()
        self.setCursor(Qt.ArrowCursor)

    def snap_restore(self):
        if self.isMaximized():
            self.showNormal()
        self.setCursor(Qt.ArrowCursor)

    def snap_left(self):
        screen = self.screen()
        if screen is None: return
        geom = screen.availableGeometry()
        if self.isMaximized(): self.showNormal()
        self.setGeometry(geom.left(), geom.top(), geom.width() // 2, geom.height())

    def snap_right(self):
        screen = self.screen()
        if screen is None: return
        geom = screen.availableGeometry()
        if self.isMaximized(): self.showNormal()
        half = geom.width() // 2
        self.setGeometry(geom.left() + half, geom.top(), half, geom.height())
    
    def get_resize_direction(self, pos):
        if self.isMaximized():
            return None
        x, y = pos.x(), pos.y()
        width, height = self.width(), self.height()
        
        at_left = x < self.RESIZE_MARGIN
        at_right = x > width - self.RESIZE_MARGIN
        at_top = y < self.RESIZE_MARGIN
        at_bottom = y > height - self.RESIZE_MARGIN
        
        if at_top and at_left: return "top-left"
        elif at_top and at_right: return "top-right"
        elif at_bottom and at_left: return "bottom-left"
        elif at_bottom and at_right: return "bottom-right"
        elif at_left: return "left"
        elif at_right: return "right"
        elif at_top: return "top"
        elif at_bottom: return "bottom"
        return None
    
    def update_cursor(self, pos):
        if self.isMaximized():
            self.setCursor(Qt.ArrowCursor)
            return
        direction = self.get_resize_direction(pos)
        cursor_map = {
            "top": Qt.SizeVerCursor, "bottom": Qt.SizeVerCursor,
            "left": Qt.SizeHorCursor, "right": Qt.SizeHorCursor,
            "top-left": Qt.SizeFDiagCursor, "bottom-right": Qt.SizeFDiagCursor,
            "top-right": Qt.SizeBDiagCursor, "bottom-left": Qt.SizeBDiagCursor,
        }
        self.setCursor(cursor_map.get(direction, Qt.ArrowCursor))
    
    def on_incoming_call(self, caller, number, status):
        """Show call popup and update mobile panel"""
        if hasattr(self, "center_content"):
            self.center_content.update_mobile_call(caller, number, status)

        if status == "ended":
            if hasattr(self, "call_popup") and self.call_popup:
                self.call_popup.hide()
                self.call_popup.deleteLater()
                self.call_popup = None
            return

        if not hasattr(self, "call_popup") or not self.call_popup:
            try:
                from aeris.ui_laptop.widgets.call_popup import CallPopup
                self.call_popup = CallPopup(self)
                self.call_popup.accepted.connect(lambda: self.on_call_action("answer"))
                self.call_popup.declined.connect(lambda: self.on_call_action("decline"))
            except ImportError:
                logger.warning("CallPopup widget not found.")
                return
        
        self.call_popup.show_call(caller, number)
        self.call_popup.update_status(status)
        
        if not self.call_popup.isVisible():
            screen_geo = self.screen().geometry()
            popup_geo = self.call_popup.geometry()
            x = (screen_geo.width() - popup_geo.width()) // 2
            y = (screen_geo.height() - popup_geo.height()) // 2
            self.call_popup.move(x, y)
            self.call_popup.show()
        
    def on_call_action(self, action):
        if action == "answer":
            event_bus.emit("mobile.command", {"command": "answer_call"})
        elif action == "decline":
            event_bus.emit("mobile.command", {"command": "decline_call"})
            
        if hasattr(self, "call_popup") and self.call_popup:
            self.call_popup.close()

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        from aeris.ui_laptop.config import LOGO_PATH
        if os.path.exists(LOGO_PATH):
            self.tray_icon.setIcon(QIcon(LOGO_PATH))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(QSystemTrayIcon.SP_ComputerIcon))
            
        tray_menu = QMenu()
        show_action = QAction("Show JARVIS", self)
        show_action.triggered.connect(self.restore_from_tray)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.force_exit)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_from_tray()

    def hide_to_tray(self):
        self.hide()

    def restore_from_tray(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.activateWindow()

    def force_exit(self):
        self.tray_icon.hide()
        self.close()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseMove, QEvent.HoverMove):
            global_pos = QCursor.pos()
            local_pos = self.mapFromGlobal(global_pos)
            if self.is_resizing and self.resize_direction:
                delta = global_pos - self.resize_start_pos
                new_geometry = QRect(self.resize_start_geometry)
                direction = self.resize_direction
                if "left" in direction: new_geometry.setLeft(new_geometry.left() + delta.x())
                if "right" in direction: new_geometry.setRight(new_geometry.right() + delta.x())
                if "top" in direction: new_geometry.setTop(new_geometry.top() + delta.y())
                if "bottom" in direction: new_geometry.setBottom(new_geometry.bottom() + delta.y())
                if new_geometry.width() >= self.MIN_WIDTH and new_geometry.height() >= self.MIN_HEIGHT:
                    self.setGeometry(new_geometry)
                return True
            else:
                if not self.isMaximized():
                    self.update_cursor(local_pos)
        elif event.type() == QEvent.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if self.isMaximized(): return super().eventFilter(obj, event)
            global_pos = event.globalPos()
            local_pos = self.mapFromGlobal(global_pos)
            direction = self.get_resize_direction(local_pos)
            if direction:
                self.is_resizing = True
                self.resize_direction = direction
                self.resize_start_pos = global_pos
                self.resize_start_geometry = self.geometry()
                return True
        elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self.is_resizing:
                self.is_resizing = False
                self.resize_direction = None
                self.resize_start_pos = None
                self.resize_start_geometry = None
                if not self.isMaximized():
                    self.update_cursor(self.mapFromGlobal(QCursor.pos()))
                return True
        elif event.type() == QEvent.Leave:
            if not self.is_resizing:
                self.setCursor(Qt.ArrowCursor)
        return super().eventFilter(obj, event)


def main():
    # This main() is now a stub because aeris/main.py drives the boot sequence.
    # We will instantiate JARVISWindow from there.
    pass


if __name__ == "__main__":
    import qasync
    import asyncio
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = JARVISWindow()
    window.show()
    with loop:
        loop.run_forever()
