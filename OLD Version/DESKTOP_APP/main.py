# --- DESKTOP_APP/main.py ---
import sys
import os
import random
import threading
import time
import psutil
from datetime import timedelta

from PyQt5 import QtGui

from CORE.Utils.Firebase import log_uncertain_query
from CORE.Utils.resource_path import resource_path
from DATA.CONFIG.command_manifest import COMMAND_MANIFEST
from DATA.RESOURCES import responses

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QGraphicsDropShadowEffect, QSplashScreen, QDialog, QVBoxLayout,
    QTextBrowser
)
from PyQt5.QtGui import QFont, QIcon, QMovie, QColor, QPixmap
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QTimer, pyqtSignal, QObject

from DESKTOP_APP.GUI.new_ui import Ui_mainWindow
import MAIN.jarvis_backend_main as jarvis_backend

# Enable high DPI scaling
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# Global variables to store the last I/O counts for rate calculation
LAST_NET_IO = psutil.net_io_counters()
LAST_DISK_IO = psutil.disk_io_counters()
LAST_UPDATE_TIME = time.time()


class CommandListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("J.A.R.V.I.S. Command Reference")
        self.setFixedSize(650, 400)
        self.setStyleSheet("background-color: #0a0f1b; border: 1px solid #22d3ee; border-radius: 10px;")

        layout = QVBoxLayout(self)

        # 1. Title Label
        title_label = QLabel("J.A.R.V.I.S. Command Manifest")
        title_label.setStyleSheet("color: #67e8f9; font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label, 0, Qt.AlignCenter)

        # 2. Text Browser (Displaying the HTML List)
        self.text_browser = QTextBrowser()
        self.text_browser.setStyleSheet(
            "background-color: rgba(15, 23, 42, 0.7); border: none; color: #aef1fc; padding: 10px;"
        )
        self.text_browser.setHtml(format_command_list())  # Use your existing formatting function
        layout.addWidget(self.text_browser)

        # 3. Close Button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; border: none; padding: 5px 15px; border-radius: 5px; }")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)



class JarvisSplashScreen(QSplashScreen):
    def __init__(self, parent=None):
        # 1. Load the GIF/Image and static fallback FIRST.
        movie = QMovie(resource_path("assets/arc.gif"))

        static_image = QPixmap(resource_path("assets/img.png"))
        if static_image.isNull():
            # Create a small, dark placeholder image if static image is missing
            static_image = QPixmap(250, 250)
            static_image.fill(QColor("#0a0f1b"))

        # 🟢 CRITICAL FIX: Pass the QPixmap first, omitting the 'parent' argument
        # unless you specifically need it. QSplashScreen is usually parented to the desktop.
        super().__init__(static_image)  # ❌ WAS: super().__init__(QPixmap(), parent)
        # ✅ NOW: Pass the static_image QPixmap directly.

        # 2. Add a QLabel to host and center the QMovie
        self.movie_label = QLabel(self)
        self.movie_label.setMovie(movie)
        self.movie_label.setFixedSize(250, 250)
        self.movie_label.setAttribute(Qt.WA_TranslucentBackground)

        # Center the QLabel (the GIF) on the QSplashScreen
        # Assuming the base image size (static_image) is 250x250, this centers the GIF.
        self.movie_label.setGeometry(0, 0, 250, 250)

        # 3. Start the movie
        movie.start()

        # Style the splash screen
        self.setStyleSheet("background-color: #0a0f1b; border: 3px solid #22d3ee; border-radius: 12px;")

        # Important: Remove window decorations (title bar, border)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Optional: Add a simple message (This will overlay the GIF)
        self.showMessage("Initializing Systems...",
                         Qt.AlignBottom | Qt.AlignHCenter,
                         QColor("#67e8f9"))

    def showMessage(self, message, alignment=Qt.AlignHCenter, color=Qt.white):
        # Override showMessage to set custom font
        super().showMessage(message, alignment, color)
        font = QFont("Audiowide", 10)
        self.setFont(font)


# --- UPTIME FUNCTION (No changes) ---
def get_uptime_string():
    try:
        boot_timestamp = psutil.boot_time()
        uptime_seconds = time.time() - boot_timestamp
        td = timedelta(seconds=int(uptime_seconds))
        total_seconds = int(td.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{days:03d}:{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception as e:
        return "ERROR: OFFLINE"


# --- DESKTOP_APP/GUI/main.py (New Utility Function) ---

def format_command_list():
    """Formats the manifest data into an HTML list for the chat window."""
    html_list = '<div style="color:#67e8f9; font-size:14px; margin-bottom: 8px;">**J.A.R.V.I.S. Command List (Brain 1)**</div>'
    html_list += '<table style="width:100%; border-collapse: collapse;">'

    for intent, data in COMMAND_MANIFEST.items():
        # Display Name (Cyan)
        html_list += f'<tr><td style="color:#22d3ee; padding: 4px 0; font-weight: bold;">{data["name"]} ({intent})</td>'

        # Example (Gray/White)
        html_list += f'<td style="color:#aef1fc; padding: 4px 0;">Example: "{data["example"]}"</td></tr>'

    html_list += '</table>'
    return html_list

# --- WORKER THREAD and UTILITY CLASSES (No changes) ---

class JarvisWorker(QObject):
    update_mic_status_signal = pyqtSignal(str, str)
    append_chat_signal = pyqtSignal(str)
    update_nlu_confidence_signal = pyqtSignal(float)

    def __init__(self, speaker, main_app_instance, parent=None):
        super().__init__(parent)
        self.speaker = speaker
        self.running = True
        self.main_app = main_app_instance

    def run_jarvis_logic(self):
        jarvis_backend.main_loop_threaded(
            speaker_instance=self.speaker,
            update_mic_status_callback=self.update_mic_status_signal.emit,
            append_chat_callback=self.append_chat_signal.emit,
            update_nlu_confidence_callback=self.update_nlu_confidence_signal.emit,
            # Pass lambda that checks both running status and mic_enabled status
            is_running_check=lambda: self.running and self.main_app.mic_enabled
        )

    def stop(self):
        self.running = False


# --- (setup_animated_dot remains, VoiceLevelMeter class is REMOVED) ---
def setup_animated_dot(button: QPushButton, color: str):
    effect = QGraphicsDropShadowEffect(button)
    effect.setColor(QColor(color))
    effect.setOffset(0)
    effect.setBlurRadius(8)
    button.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"blurRadius")
    anim.setStartValue(7)
    anim.setEndValue(18)
    anim.setDuration(1100)
    anim.setLoopCount(-1)
    anim.setEasingCurve(QEasingCurve.InOutSine)
    anim.start()
    return anim


# --- 2. Main Application Class ---

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_mainWindow()
        self.ui.setupUi(self)

        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(resource_path("assets/chat.png")), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.ui.btnChatHeaderLogo.setIcon(icon1)

        # 2. Chat Close Button (assets/close.png)
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap(resource_path("assets/close.png")), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.ui.btnCloseChat.setIcon(icon2)

        # NEW STATE: Start with mic active.
        self.mic_enabled = True

        # --- J.A.R.V.I.S. Backend Setup ---
        self.jarvis_speaker = jarvis_backend.JarvisSpeaker()

        self.jarvis_thread = threading.Thread(target=self.start_jarvis_worker)
        self.jarvis_thread.daemon = True
        # Pass self (MainApp instance) to the worker
        self.worker = JarvisWorker(self.jarvis_speaker, self)
        self.worker.update_mic_status_signal.connect(self.set_mic_status)
        self.worker.append_chat_signal.connect(self.append_jarvis_response)
        self.worker.update_nlu_confidence_signal.connect(self.set_nlu_confidence_status)

        # --- CRITICAL FIX: Delay backend thread start to prevent crash ---
        QTimer.singleShot(500, self.start_delayed_backend)

        self.help_button = QPushButton(self.ui.mainCentralWidget)
        self.help_button.setText("HELP")

        # Style to match the theme (using the cyan glow)
        self.help_button.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22d3ee, stop:1 #3b82f6);
                        color: #0a0f1b; /* Dark text on bright background */
                        border: none;
                        border-radius: 8px;
                        padding: 6px 12px;
                        font-weight: bold;
                        letter-spacing: 0.5px;
                    }
                """)

        # 🟢 2. POSITION THE HELP BUTTON
        # Find the widget corresponding to the mic/voice command box for relative placement.
        # We'll place it near the header of the voice command section.
        mic_box_pos = self.ui.micBoxWidget.pos()
        mic_box_width = self.ui.micBoxWidget.width()

        # Set geometry (X, Y, Width, Height) - Adjust Y based on visual position desired
        self.help_button.setGeometry(
            mic_box_pos.x() + mic_box_width + 20,  # X position offset right of the mic box
            mic_box_pos.y() + 50,  # Y position (adjust 50px up from the box top)
            120, 30
        )

        # 🟢 3. CONNECT THE HANDLER
        self.help_button.clicked.connect(self.show_command_list)

        # --- VOICE METER SETUP (REMOVED) ---
        # self.voice_meter = VoiceLevelMeter(self.ui.micBoxWidget) # Removed
        # global_icon_pos = self.ui.MicIcon.mapToGlobal(self.ui.MicIcon.rect().topLeft()) # Removed
        # local_pos = self.ui.micBoxWidget.mapFromGlobal(global_icon_pos) # Removed
        # icon_size = self.ui.MicIcon.size() # Removed
        # self.voice_meter.setGeometry(local_pos.x(), local_pos.y(), icon_size.width(), icon_size.height()) # Removed
        # self.ui.MicIcon.raise_() # Kept this, but irrelevant without meter

        # --- Dynamic UPTIME & System Timers ---
        self.uptime_label = self.ui.lblFooterUptime
        self.update_uptime_display()
        self.uptime_timer = QTimer(self)
        self.uptime_timer.timeout.connect(self.update_uptime_display)
        self.uptime_timer.start(1000)

        # System Status Update Timer
        self.system_status_timer = QTimer(self)
        self.system_status_timer.timeout.connect(self.update_system_status)
        self.system_status_timer.start(500)
        self.set_nlu_confidence_status(1.0)  # Initial Brain Status setup

        # --- UI REFERENCES AND INITIALIZATION ---
        shadow = QGraphicsDropShadowEffect()
        shadow.setColor(QColor("#22d3ee"))
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 0)
        self.ui.widgetChatBox.setGraphicsEffect(shadow)

        self.mic_btn = self.ui.MicIcon
        self.mic_status_text = self.ui.belowMicText
        self.mic_status_dot = self.ui.belowMicDot

        self.mic_effect = QGraphicsDropShadowEffect(self)
        self.mic_effect.setBlurRadius(20)
        self.mic_effect.setColor(QColor("#22d3ee"))
        self.mic_effect.setOffset(0)
        self.mic_btn.setGraphicsEffect(self.mic_effect)

        self.mic_glow_anim = QPropertyAnimation(self.mic_effect, b"blurRadius")
        self.mic_glow_anim.setStartValue(20)
        self.mic_glow_anim.setEndValue(45)
        self.mic_glow_anim.setDuration(1800)
        self.mic_glow_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.mic_glow_anim.setLoopCount(-1)
        self.mic_glow_anim.start()

        # NOTE: Keeping mic_scale_anim defined but intentionally unused for clean toggle.
        self.mic_scale_anim = QPropertyAnimation(self.mic_btn, b"minimumSize")
        self.mic_scale_anim.setStartValue(self.mic_btn.size())
        self.mic_scale_anim.setEndValue(self.mic_btn.size() + QSize(8, 8))
        self.mic_scale_anim.setDuration(400)
        self.mic_scale_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.mic_btn.setIcon(QIcon(resource_path("assets/microphone.png")))
        self.mic_btn.setIconSize(self.mic_btn.iconSize())
        self.mic_btn.clicked.connect(self.voice_chat_trigger)

        # Initial status is set by the backend after the delay, but we set a default here
        self.set_mic_status("AWAITING WAKE WORD", "#4ade80")

        self.chat_area = self.ui.txtChatHistory
        self.chat_area.setReadOnly(True)  # <<< CRITICAL CHANGE

        self.input_line = self.ui.txtChatInput
        self.send_button = self.ui.btnChatSend

        self.send_button.clicked.connect(self.send_chat_message)
        self.input_line.returnPressed.connect(self.send_chat_message)

        self.dot1_anim = setup_animated_dot(self.ui.btnStatusNNDot, "#4ade80")
        self.dot2_anim = setup_animated_dot(self.ui.btnStatusNNDot_2, "#22d3ee")
        self.dot3_anim = setup_animated_dot(self.ui.btnStatusNNDot_3, "#60a5fa")
        self.dot4_anim = setup_animated_dot(self.ui.btnStatusNNDot_4, "#818cf8")
        self.dot5_anim = setup_animated_dot(self.ui.btnStatusNNDot_5, "#10b981")
        self.dot6_anim = setup_animated_dot(self.ui.btnStatusNNDot_6, "#facc15")

        # Hide the static dot buttons
        self.ui.btnStatusNNDot.hide()
        self.ui.btnStatusNNDot_2.hide()
        self.ui.btnStatusNNDot_3.hide()
        self.ui.btnStatusNNDot_4.hide()
        self.ui.btnStatusNNDot_5.hide()
        self.ui.btnStatusNNDot_6.hide()

        arc_gif_label = self.ui.lblArcReactor
        if arc_gif_label:
            arc_gif_label.setScaledContents(True)
            arc_movie = QMovie(resource_path("assets/arc.gif"))
            arc_movie.setScaledSize(arc_gif_label.size())

            def on_resize(event):
                arc_movie.setScaledSize(arc_gif_label.size())
                QLabel.resizeEvent(arc_gif_label, event)

            arc_gif_label.resizeEvent = on_resize
            arc_gif_label.setMovie(arc_movie)
            arc_movie.start()

        self.chat_area = self.ui.txtChatHistory
        self.input_line = self.ui.txtChatInput
        self.send_button = self.ui.btnChatSend

        self.send_button.clicked.connect(self.send_chat_message)
        self.input_line.returnPressed.connect(self.send_chat_message)

        # Initialize last network/disk status
        self.last_net_io = psutil.net_io_counters()
        self.last_disk_io = psutil.disk_io_counters()
        self.last_update_time = time.time()

    def show_command_list(self):
        """Displays the command reference list in a modal dialog."""
        dialog = CommandListDialog(self)
        dialog.exec_()  # Use exec_() to run the dialog modally (blocks until closed)

    # --- System Status Update Method (Logic remains the same) ---
    def update_system_status(self):
        global LAST_NET_IO, LAST_DISK_IO, LAST_UPDATE_TIME
        current_time = time.time()
        time_diff = current_time - LAST_UPDATE_TIME

        # --- Base Styles ---
        TITLE_STYLE = "color: #67e8f9; font-weight: bold;"  # Bright Cyan/Blue for Title
        VALUE_TEMPLATE = "<span style='color: {}'>●</span> <span style='color: {}'>{}{}</span>"
        GREEN = "#4ade80";
        YELLOW = "#facc15";
        RED = "#ef4444";
        CYAN = "#22d3ee";
        BLUE = "#60a5fa";
        PURPLE = "#818cf8";
        TEAL = "#10b981"

        # --- 1. CPU Usage (Slot 1) ---
        cpu_percent = psutil.cpu_percent(interval=None)
        self.ui.lblStatusNNTitle.setText("CPU ACTIVITY")
        self.ui.lblStatusNNTitle.setStyleSheet(TITLE_STYLE)

        if cpu_percent < 50:
            dot_color, text_color = GREEN, GREEN
        elif cpu_percent < 80:
            dot_color, text_color = YELLOW, YELLOW
        else:
            dot_color, text_color = RED, RED

        self.ui.lblStatusNNValue.setText(
            VALUE_TEMPLATE.format(dot_color, text_color, f"{cpu_percent:.1f}", "%")
        )

        # --- 2. RAM Usage (Slot 2) ---
        ram_percent = psutil.virtual_memory().percent
        self.ui.lblStatusNNTitle_2.setText("MEMORY USAGE")
        self.ui.lblStatusNNTitle_2.setStyleSheet(TITLE_STYLE)

        if ram_percent < 65:
            dot_color, text_color = CYAN, CYAN
        elif ram_percent < 85:
            dot_color, text_color = YELLOW, YELLOW
        else:
            dot_color, text_color = RED, RED

        self.ui.lblStatusNNValue_2.setText(
            VALUE_TEMPLATE.format(dot_color, text_color, f"{ram_percent:.1f}", "%")
        )

        # --- 3. Network I/O (Slot 3) ---
        current_net_io = psutil.net_io_counters()
        net_recv_rate = (current_net_io.bytes_recv - LAST_NET_IO.bytes_recv) / time_diff / 1024
        net_sent_rate = (current_net_io.bytes_sent - LAST_NET_IO.bytes_sent) / time_diff / 1024
        total_net_rate = net_recv_rate + net_sent_rate

        self.ui.Operation_3.setText("INTERNET SPEED")
        self.ui.Operation_3.setStyleSheet(TITLE_STYLE)

        dot_color, text_color = (BLUE, BLUE) if total_net_rate < 500 else (YELLOW, YELLOW)

        self.ui.lblStatusNNValue_3.setText(
            VALUE_TEMPLATE.format(dot_color, text_color, f"R:{net_recv_rate:.0f} S:{net_sent_rate:.0f}", " KB/s")
        )
        LAST_NET_IO = current_net_io

        # --- 4. Disk I/O (Slot 4) ---
        current_disk_io = psutil.disk_io_counters()
        disk_read_rate = (current_disk_io.read_bytes - LAST_DISK_IO.read_bytes) / time_diff / (1024 * 1024)
        disk_write_rate = (current_disk_io.write_bytes - LAST_DISK_IO.write_bytes) / time_diff / (1024 * 1024)
        total_disk_rate = disk_read_rate + disk_write_rate

        self.ui.lblStatusNNTitle_3.setText("HARD DRIVE")
        self.ui.lblStatusNNTitle_3.setStyleSheet(TITLE_STYLE)

        dot_color, text_color = (PURPLE, PURPLE) if total_disk_rate < 20 else (YELLOW, YELLOW)

        self.ui.lblStatusNNValue_4.setText(
            VALUE_TEMPLATE.format(dot_color, text_color, f"R:{disk_read_rate:.1f} W:{disk_write_rate:.1f}", " MB/s")
        )
        LAST_DISK_IO = current_disk_io

        # --- 5. SWAP Memory / Virtual Memory (Slot 5) ---
        swap_percent = psutil.swap_memory().percent
        self.ui.lblStatusNNTitle_4.setText("VIRTUAL MEMORY")
        self.ui.lblStatusNNTitle_4.setStyleSheet(TITLE_STYLE)

        dot_color, text_color = (TEAL, TEAL) if swap_percent < 50 else (YELLOW, YELLOW)

        self.ui.lblStatusNNValue_5.setText(
            VALUE_TEMPLATE.format(dot_color, text_color, f"{swap_percent:.1f}", "% Used")
        )

        # --- 6. Battery / Power Status (Slot 6) ---
        self.ui.lblStatusNNTitle_5.setText("SYSTEM HEALTH")
        self.ui.lblStatusNNTitle_5.setStyleSheet(TITLE_STYLE)

        if hasattr(psutil, 'sensors_battery') and psutil.sensors_battery() is not None:
            battery = psutil.sensors_battery()

            if battery.power_plugged:
                status_text = f"{battery.percent:.1f}% Charging"
                dot_color, text_color = GREEN, GREEN
            elif battery.percent > 20:
                status_text = f"{battery.percent:.1f}% Discharge"
                dot_color, text_color = YELLOW, YELLOW
            else:
                status_text = f"{battery.percent:.1f}% LOW!"
                dot_color, text_color = RED, RED

            self.ui.lblStatusNNTitle_5.setText("POWER STATUS")
        else:
            status_text = "ALL SYSTEMS GO"
            dot_color, text_color = GREEN, GREEN

        self.ui.lblStatusNNValue_6.setText(
            VALUE_TEMPLATE.format(dot_color, text_color, status_text, "")
        )

        # Update the time marker for rate calculation
        LAST_UPDATE_TIME = current_time

    # --- NLU Confidence Status Method (Brain Status Logic remains the same) ---
    def set_nlu_confidence_status(self, confidence: float):
        """
        Translates the NLU confidence score (0.0 to 1.0) into a layman-friendly BRAIN STATUS
        and updates the bottom-right footer label (lblFooterThreat).
        """
        confidence_percent = confidence * 100

        # --- Logic for Layman's Status ---
        if confidence >= jarvis_backend.CONFIDENCE_THRESHOLD:
            status_level = "UNDERSTOOD"
            status_color = "#4ade80"
        elif confidence >= (jarvis_backend.CONFIDENCE_THRESHOLD - 0.15):
            status_level = "UNCERTAIN"
            status_color = "#facc15"
        else:
            status_level = "CONFUSED"
            status_color = "#ef4444"

        # Update the footer label with the new BRAIN STATUS
        self.ui.lblFooterThreat.setText(
            f"BRAIN STATUS: {status_level} ({confidence_percent:.1f}%)"
        )

        # Apply the color style
        self.ui.lblFooterThreat.setStyleSheet(
            f"color: {status_color}; font-family: 'Audiowide'; letter-spacing: 0.5px;"
        )

    # --- Mute/Unmute/Mic Status Methods (FIXED) ---
    def voice_chat_trigger(self):
        """Toggles the self.mic_enabled state and updates UI status immediately."""

        # 🟢 FIX 1: Immediately stop any scale animation to prevent stuttering/jitter
        if self.mic_scale_anim.state() == QPropertyAnimation.Running:
            self.mic_scale_anim.stop()

        self.mic_enabled = not self.mic_enabled

        if not self.mic_enabled:
            # Mic is disabled/muted: Visually show MUTED. Backend thread will pause.
            self.set_mic_status("MUTED (Chat Only)", "#facc15")
        else:
            # Mic is enabled: Visually show listening is expected. Backend thread will resume.
            self.set_mic_status("AWAITING WAKE WORD", "#4ade80")

    def set_mic_status(self, text, color):
        QTimer.singleShot(0, lambda: self._update_mic_ui(text, color))

    def _update_mic_ui(self, text, color):
        self.mic_status_text.setText(text)
        self.mic_status_text.setStyleSheet(f"color: {color}; background: transparent;")
        self.mic_status_dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")

    def append_jarvis_response(self, text):
        # FIX: Reverted color to intended theme color
        html = f'<div style="color:#67e8f9;font-family:\'Exo\';font-size:13px; margin-top: 5px;">J.A.R.V.I.S.: {text}</div>'
        self.chat_area.append(html)
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())

    def send_chat_message(self):
        text = self.input_line.text().strip()
        if not text:
            return

        html = f'<div style="color:#aef1fc;font-family:\'Exo\';font-size:13px; margin-top: 5px;">You: {text}</div>'
        self.chat_area.append(html)
        self.input_line.clear()
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())
        threading.Thread(target=self.process_chat_command, args=(text,)).start()

    def update_uptime_display(self):
        new_uptime_str = get_uptime_string()
        self.uptime_label.setText(f"UPTIME: {new_uptime_str}")

    def start_delayed_backend(self):
        print("Starting Jarvis backend thread after GUI delay...")
        self.jarvis_thread.start()

    def start_jarvis_worker(self):
        self.worker.run_jarvis_logic()

    def closeEvent(self, event):
        print("Stopping Jarvis worker...")
        self.worker.stop()
        self.jarvis_thread.join(timeout=1.0)
        event.accept()

    def process_chat_command(self, command):
        """
        Handles command input from the text chat interface.
        It performs NLU, logs uncertain queries to Firebase, and ensures J.A.R.V.I.S. speaks
        a contextual response for both actions and conversations, explicitly handling voice output.
        """
        self.set_mic_status("PROCESSING", "#60a5fa")

        intent, entities, confidence = jarvis_backend.get_intent(command)
        spoken_text = ""
        action_result = True  # Default to True so the loop continues

        # 1. Determine Status Level for Logging and UI
        if confidence >= jarvis_backend.CONFIDENCE_THRESHOLD:
            status_level = "UNDERSTOOD"
        elif confidence >= (jarvis_backend.CONFIDENCE_THRESHOLD - 0.15):
            status_level = "UNCERTAIN"
        else:
            status_level = "CONFUSED"

        # 🟢 NEW: Update NLU confidence immediately (updates BRAIN STATUS UI)
        self.set_nlu_confidence_status(confidence)

        # --- LOGGING FOR ACTIVE LEARNING (Firebase) ---
        if status_level != "UNDERSTOOD":
            log_data = {
                'user_query': command,
                'nlu_confidence': confidence,
                'intent_guess': intent if intent else 'NONE',
                'user_source': 'GUI_Chat_Input'
            }
            # 🟢 PUSH UNCERTAIN/CONFUSED DATA TO FIREBASE
            log_uncertain_query(log_data, status_level)

        # Define conversational intents that skip the direct action handler
        CONVERSATIONAL_INTENTS = ["ask_question", "chit_chat", "greet"]

        # --- Decision Point ---
        # 2. High Confidence AND Action Intent: Execute Action.
        if confidence > jarvis_backend.CONFIDENCE_THRESHOLD and intent not in CONVERSATIONAL_INTENTS:

            # --- ACTION EXECUTION ---
            # Note: action_result will be True (success, keeps running), False (goodbye/error, stop running), or a string (result text).
            action_result = jarvis_backend.handle_action(
                speaker=self.jarvis_speaker,
                command=command,
                intent=intent,
                entities=entities
            )

            if isinstance(action_result, str):
                # Action returned a string result (e.g., check_time). We use this for chat display.
                # CRITICAL ASSUMPTION: The action function *must* have called speaker.speak(action_result) already.
                spoken_text = action_result
                self.append_jarvis_response(spoken_text)

            elif action_result is True:
                # Action executed successfully (e.g., open_item). Speech and chat output already handled inside handle_action.
                pass

            elif action_result is False:
                # Goodbye intent or hard failure. handle_action spoke the goodbye message.
                # This signals the main thread (if running) to stop, but in chat mode, it just means log the goodbye.
                # No need to append or speak here as handle_action did it.
                pass

        else:
            # 3. CONVERSATIONAL/Q&A or LOW CONFIDENCE FALLBACK
            if confidence <= jarvis_backend.CONFIDENCE_THRESHOLD:
                # Log low confidence to local console for developer visibility
                print(f"NLU_LOW_CONF in chat mode | '{command}' | guessed {intent} ({confidence:.2f})")

            # Get the appropriate fallback response text
            if intent == "greet":
                spoken_text = random.choice(responses.GREET_RESPONSES)
            elif intent in ["ask_question", "chit_chat"]:
                # Placeholder for your future Generative Core
                spoken_text = "This feature is UPCOMING !"
            else:
                # Generic fallback for unhandled or low-confidence non-action intent
                spoken_text = responses.get_response(intent)

                # CRITICAL FIX: Explicitly speak and append the conversational/fallback response
            if spoken_text:
                self.jarvis_speaker.speak(spoken_text)
                self.append_jarvis_response(spoken_text)

        # --- FINAL STATUS UPDATE ---

        # Reset status based on system state
        if self.mic_enabled and action_result is not False:
            self.set_mic_status("AWAITING WAKE WORD", "#4ade80")
        elif not self.mic_enabled and action_result is not False:
            self.set_mic_status("MUTED (Chat Only)", "#facc15")
        else:  # action_result is False (Goodbye)
            self.set_mic_status("STANDBY", "#9ca3af")

# --- PC SOFTWARE/GUI_MAKING/NEW_UI/main.py (if __name__ == "__main__") ---

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)

    # 🟢 STEP 1: SHOW SPLASH SCREEN IMMEDIATELY
    splash = JarvisSplashScreen()
    splash.show()

    # Process events to ensure the splash screen is drawn instantly
    app.processEvents()

    # -----------------------------------------------------------
    # 🟢 CRITICAL FIX: Introduce a small delay to guarantee GIF starts drawing.
    # This forces the OS/GUI thread to handle the animation loop before the CPU heavy load starts.
    time.sleep(0.1)  # 100 milliseconds is enough time for the GIF engine to start
    # -----------------------------------------------------------

    # 🟢 STEP 2: LOAD MAIN WINDOW AND HEAVY COMPONENTS
    # Time-consuming initializations start here
    window = MainApp()

    # 🟢 STEP 3: CLOSE SPLASH SCREEN
    window.show()
    splash.finish(window)

    sys.exit(app.exec_())