<<<<<<< HEAD
# gui.py
import os, sys, threading
import pathlib
import platform
from dotenv import dotenv_values
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QFrame
)
from PyQt5.QtGui import QMovie, QFont, QColor, QPixmap, QTextCharFormat
from PyQt5.QtCore import Qt, QSize, QTimer

from FUNCTION.LOGGER.logger import clear_chat_log
from MAIN.main import jarvis
from UTILS.path import resource_path

# ─── Environment & Paths ─────────────────────────────────────────
env = dotenv_values(".env")
Assistantname = env.get("Assistantname", "Assistant")

# TMP = resource_path("../MAIN/Files")
# def TD(fname): return os.path.join(TMP, fname)
GFX = resource_path("Graphics")


# Create per-user writeable path (cross-platform)
if platform.system() == "Windows":
    USER_DATA = os.path.join(os.getenv("APPDATA"), "Jarvis")
else:
    USER_DATA = os.path.join(os.path.expanduser("~"), ".jarvis")

os.makedirs(USER_DATA, exist_ok=True)

def TD(fname): return os.path.join(USER_DATA, fname)

def GD(fname): return os.path.join(GFX, fname)

# ─── File I/O (Safe) ─────────────────────────────────────────────
def write_file(path, txt):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
    except Exception as e:
        print(f"[Write Error] {path}: {e}")

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

# ─── Status Helpers ──────────────────────────────────────────────
def SetMicrophoneStatus(v): write_file(TD("Mic.data"), v)
def GetAssistantStatus():   return read_file(TD("Status.data"))
def SetAssistantStatus(v):  write_file(TD("Status.data"), v)
def MicButtonInit():        SetMicrophoneStatus("False")
def MicButtonClose():       SetMicrophoneStatus("True")

# ─── Chat Section ────────────────────────────────────────────────
class ChatSection(QWidget):
    def __init__(self):
        super().__init__()
        clear_chat_log()
        self.last_line_count = 0
        self.old_session = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 40, 10, 10)

        self.editor = QTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setFrameStyle(QFrame.NoFrame)
        self.editor.setFont(QFont("Segoe UI", 13))
        self.editor.setStyleSheet("background:black; color:white;")
        layout.addWidget(self.editor)

        self.gif = QLabel()
        if os.path.exists(GD("Jarvis.gif")):
            movie = QMovie(GD("Jarvis.gif"))
            movie.setScaledSize(QSize(480, 270))
            self.gif.setMovie(movie)
            movie.start()
        layout.addWidget(self.gif, alignment=Qt.AlignRight)

        self.status_label = QLabel("", alignment=Qt.AlignRight)
        self.status_label.setStyleSheet("color:white; font-size:16px;")
        layout.addWidget(self.status_label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(500)

    def update(self):
        content = read_file(TD("Responses.data"))
        all_lines = content.splitlines()

        # Detect new session based on header
        if all_lines and all_lines[0] != self.old_session:
            self.old_session = all_lines[0]  # Update to new session
            self.editor.clear()  # Clear GUI view
            self.last_line_count = 0  # Reset count to show from beginning

        if len(all_lines) > self.last_line_count:
            new_lines = all_lines[self.last_line_count:]
            for line in new_lines:
                self._add_line(line, QColor("white"))
            self.last_line_count = len(all_lines)

        self.status_label.setText(GetAssistantStatus())

    def _add_line(self, txt, color):
        cursor = self.editor.textCursor()
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.setCharFormat(fmt)
        cursor.insertText(txt + "\n")
        self.editor.setTextCursor(cursor)


# ─── Initial Home Screen ─────────────────────────────────────────
class InitialScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 80)

        screen = QApplication.desktop().screenGeometry()
        gif = QLabel(alignment=Qt.AlignCenter)
        if os.path.exists(GD("Jarvis.gif")):
            movie = QMovie(GD("Jarvis.gif"))
            movie.setScaledSize(QSize(screen.width(), screen.width() * 9 // 16))
            gif.setMovie(movie)
            movie.start()
        layout.addWidget(gif)

        self.icon = QLabel(alignment=Qt.AlignCenter)
        self.icon.setFixedSize(150, 150)
        self.toggled = True
        self._toggle_icon()
        self.icon.mousePressEvent = lambda e: self._toggle_icon()
        layout.addWidget(self.icon)

        self.status_text = QLabel("", alignment=Qt.AlignCenter)
        self.status_text.setStyleSheet("color:white; font-size:16px;")
        layout.addWidget(self.status_text)

        self.setStyleSheet("background-color:black;")
        self.setFixedSize(screen.width(), screen.height())

        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.status_text.setText(GetAssistantStatus()))
        self.timer.start(500)

    def _load_icon(self, name):
        icon_path = GD(name)
        if os.path.exists(icon_path):
            px = QPixmap(icon_path)
            self.icon.setPixmap(px.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _toggle_icon(self):
        if self.toggled:
            self._load_icon("Mic_on.png")
            MicButtonInit()
            threading.Thread(target=self._start_jarvis, daemon=True).start()
        else:
            self._load_icon("Mic_off.png")
            MicButtonClose()
        self.toggled = not self.toggled

    def _start_jarvis(self):
        # try:
        #     from MAIN.main import jarvis
        jarvis()
        # except Exception as e:
        #     print(f"[Jarvis Error]: {e}")

# ─── Chat Screen ─────────────────────────────────────────────────
class MessageScreen(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(ChatSection())
        self.setStyleSheet("background:black;")

# ─── Top Navigation Bar ──────────────────────────────────────────
class CustomTopBar(QWidget):
    def __init__(self, parent, stack):
        super().__init__(parent)
        self.stack = stack
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 5, 20, 5)
        layout.setSpacing(15)

        title = QLabel(f"{Assistantname} AI")
        title.setStyleSheet("color:white;font-size:20px;font-weight:bold;")
        layout.addWidget(title)
        layout.addStretch()

        def nav_btn(name, idx=None, danger=False):
            btn = QPushButton(name)
            base = "background:#444;color:white;border:none;padding:6px 14px;border-radius:8px;"
            if danger:
                base += "background:#B22222;"
            btn.setStyleSheet(base)
            if idx is not None:
                btn.clicked.connect(lambda: self.stack.setCurrentIndex(idx))
            else:
                btn.clicked.connect(parent.close)
            return btn

        layout.addWidget(nav_btn("Home", 0))
        layout.addWidget(nav_btn("Chat", 1))
        layout.addWidget(nav_btn("✕", None, danger=True))

        self.setFixedHeight(50)
        self.setStyleSheet("background:#222;border-bottom:2px solid #444;")

# ─── Main Window ─────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        screen = QApplication.desktop().screenGeometry()
        self.setGeometry(0, 0, screen.width(), screen.height())

        self.stack = QStackedWidget()
        self.stack.addWidget(InitialScreen())
        self.stack.addWidget(MessageScreen())

        layout = QVBoxLayout()
        layout.addWidget(CustomTopBar(self, self.stack))
        layout.addWidget(self.stack)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.setStyleSheet("background:black;")

# ─── Entry Point ─────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget {
            background-color: #121212;
            color: white;
            font-family: 'Segoe UI', sans-serif;
        }
    """)
    w = MainWindow()
    w.showFullScreen()
    sys.exit(app.exec_())


# from PyQt5.QtWidgets import (
#     QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
#     QScrollArea, QTextEdit, QSizePolicy, QGraphicsDropShadowEffect
# )
# from PyQt5.QtGui import QMovie, QFont, QColor
# from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QObject
# import pyautogui as gui
# import os, sys
# import threading
# from MAIN.main import jarvis  # Your actual Jarvis logic
#
# class JarvisUI(QWidget):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("Jarvis UI")
#         self.setGeometry(100, 100, 1200, 700)
#         self.setAttribute(Qt.WA_TranslucentBackground)
#         self.setWindowFlag(Qt.FramelessWindowHint)
#
#         self.chat_history = []
#
#         self.init_ui()
#
#     def init_ui(self):
#         # Outer layout
#         main_layout = QHBoxLayout(self)
#         main_layout.setContentsMargins(30, 30, 30, 30)
#         main_layout.setSpacing(20)
#
#         # ===== LEFT: Chat Area =====
#         self.chat_area = QVBoxLayout()
#         self.chat_area.setSpacing(10)
#
#         scroll_widget = QWidget()
#         scroll_widget.setLayout(self.chat_area)
#
#         scroll_area = QScrollArea()
#         scroll_area.setWidgetResizable(True)
#         scroll_area.setWidget(scroll_widget)
#         scroll_area.setStyleSheet("""
#             QScrollArea {
#                 background-color: rgba(255, 255, 255, 0.05);
#                 border-radius: 15px;
#             }
#         """)
#
#         main_layout.addWidget(scroll_area, stretch=3)
#
#         # ===== RIGHT: GIF Area =====
#         self.gif_label = QLabel(self)
#         self.gif_label.setFixedSize(500, 500)
#         self.add_gif_to_label(self.gif_label, size=QSize(500, 500))
#
#         gif_layout = QVBoxLayout()
#         gif_layout.addWidget(self.gif_label, alignment=Qt.AlignCenter)
#
#         main_layout.addLayout(gif_layout, stretch=2)
#
#     def add_gif_to_label(self, label, size):
#         base_dir = os.path.dirname(os.path.abspath(__file__))
#         gif_path = os.path.abspath(os.path.join(base_dir, '..', 'USER_INTERFACE', 'XDZT.gif'))
#
#         movie = QMovie(gif_path)
#         movie.setScaledSize(size)
#         label.setMovie(movie)
#         movie.start()
#
#         shadow = QGraphicsDropShadowEffect()
#         shadow.setBlurRadius(20)
#         shadow.setOffset(0, 0)
#         shadow.setColor(QColor(0, 0, 0, 160))
#         label.setGraphicsEffect(shadow)
#
#     def add_chat_message(self, message, sender="User"):
#         msg_label = QLabel(f"<b>{sender}:</b> {message}")
#         msg_label.setWordWrap(True)
#         msg_label.setStyleSheet("""
#             QLabel {
#                 background-color: rgba(255,255,255,0.07);
#                 color: white;
#                 padding: 10px;
#                 border-radius: 10px;
#                 font-size: 14px;
#             }
#         """)
#         msg_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
#         self.chat_area.addWidget(msg_label)
#
#     def handle_response(self, response):
#         self.add_chat_message(response, sender="Jarvis")
#
#     def handle_user_input(self, user_msg):
#         self.add_chat_message(user_msg, sender="You")
#         threading.Thread(target=self.fake_jarvis_response, args=(user_msg,)).start()
#
#     def fake_jarvis_response(self, user_msg):
#         # Simulate thinking
#         QTimer.singleShot(800, lambda: self.handle_response("Here's my response to: " + user_msg))
#
#     def keyPressEvent(self, event):
#         if event.key() == Qt.Key_Space:  # Simulate interaction on space press
#             self.handle_user_input("What’s the weather today?")
#
#
# if __name__ == "__main__":
#     gui.hotkey("win", "d")
#     app = QApplication([])
#
#     jarvis_ui = JarvisUI()
#     jarvis_ui.showFullScreen()
#
#     app.exec_()
#
#     app.setStyleSheet("""
#         QWidget {
#             background-color: #121212;
#             color: white;
#             font-family: 'Segoe UI', sans-serif;
#         }
#     """)
#
#     window = JarvisUI()
=======
import os
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect, QGraphicsBlurEffect
)
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor, QMovie, QPainter, QPen
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QTimer, QThread, QRectF

from MAIN.main import jarvis
from UTILS.ui_signal import ui_signals

# Import your modules
from BRAIN.MAIN_BRAIN.BRAIN.brain import brain_cmd
from FUNCTION.JARVIS_LISTEN.listen import listen
from UTILS.tts_singleton import speak
from USER_INTERFACE.new_ui import Ui_MainWindow

# Enable high DPI scaling
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# Initialize application
app = QApplication(sys.argv)
font = QFont("Segoe UI")
font.setPointSize(10)
app.setFont(font)

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

class VoiceLevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0.0
        self.ring_color = QColor("#22d3ee")
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.pulse)
        self.pulse_phase = 0.0
        self.animation_timer.start(30)

    def setLevel(self, level):
        self.level = max(0.0, min(level, 1.0))
        self.update()

    def pulse(self):
        self.pulse_phase = (self.pulse_phase + 0.03) % 1.0
        pulse_color = QColor.fromHsvF((0.54 + 0.12 * self.pulse_phase) % 1, 1, 1)
        self.ring_color = pulse_color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(6, 6, self.width() - 12, self.height() - 12)

        glow_pen = QPen(QColor(self.ring_color))
        glow_pen.setWidth(20)
        glow_pen.setColor(self.ring_color.lighter(150))
        painter.setPen(glow_pen)
        painter.drawArc(rect, 0, 360 * 16)

        pen = QPen(QColor("#222f3e"), 10)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        pen.setColor(self.ring_color)
        pen.setWidth(8)
        painter.setPen(pen)
        painter.drawArc(rect, 90 * 16, int(-360 * 16 * self.level))

class JarvisThread(QThread):
    def run(self):

        jarvis()


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.dragging = False
        self.drag_position = None
        self.snapping = False
        self._restore_mouse_offset = None

        # Setup central widget
        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Add your custom title bar
        title_bar = self.create_custom_title_bar()
        central_layout.addWidget(title_bar)

        # Load UI from Qt Designer
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # You MUST add the loaded UI's central widget if it's not already
        central_layout.addWidget(self.ui.centralwidget)

        self.setCentralWidget(central_widget)

        # Set app icon and title
        self.setWindowIcon(QIcon("assets/logo.png"))
        self.setWindowTitle("J.A.R.V.I.S - AI Assistant")

        # Blur effect
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(22)
        self.ui.chatBoxWrapper.setGraphicsEffect(blur)

        # Optional neon shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setColor(QColor("#22d3ee"))
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 0)
        self.ui.chatBoxWrapper.setGraphicsEffect(shadow)

        # setting up chat logo
        self.ui.chatBoxLogo.setIcon(QIcon(r"assets\chat.png"))

        # Mic animation & references
        self.mic_btn = self.ui.MicIcon
        self.mic_label_heading = self.ui.MicLabelHeading
        self.mic_label_subheading = self.ui.MicLabelSubheading
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

        self.mic_scale_anim = QPropertyAnimation(self.mic_btn, b"minimumSize")
        self.mic_scale_anim.setStartValue(self.mic_btn.size())
        self.mic_scale_anim.setEndValue(self.mic_btn.size() + QSize(8, 8))
        self.mic_scale_anim.setDuration(400)
        self.mic_scale_anim.setEasingCurve(QEasingCurve.OutQuad)

        self.mic_btn.setIcon(QIcon(r"assets\microphone.png"))
        self.mic_btn.setIconSize(self.mic_btn.iconSize())
        self.mic_btn.clicked.connect(self.toggle_mic_state)

        self.mic_active = False
        self.set_mic_status("STANDBY", "#9ca3af")

        # Dot animation setup (fixed)
        self.dot1_anim = setup_animated_dot(self.ui.Dot_Operation_1, "#4ade80")
        self.dot2_anim = setup_animated_dot(self.ui.Dot_Operation_2, "#22d3ee")
        self.dot3_anim = setup_animated_dot(self.ui.Dot_Operation_3, "#60a5fa")
        self.dot4_anim = setup_animated_dot(self.ui.Dot_Operation_4, "#818cf8")
        self.dot5_anim = setup_animated_dot(self.ui.Dot_Operation_5, "#10b981")
        self.dot6_anim = setup_animated_dot(self.ui.Dot_Operation_6, "#facc15")

        # GIF arc logo
        arc_gif_label = self.ui.arc_react_image_background
        if arc_gif_label:
            arc_gif_label.setScaledContents(True)
            arc_movie = QMovie("assets/arc.gif")
            arc_movie.setScaledSize(arc_gif_label.size())

            def on_resize(event):
                arc_movie.setScaledSize(arc_gif_label.size())
                QLabel.resizeEvent(arc_gif_label, event)

            arc_gif_label.resizeEvent = on_resize
            arc_gif_label.setMovie(arc_movie)
            arc_movie.start()

        self.chat_area = self.ui.chatArea
        ui_signals.chatbox.connect(self.append_ui_chat_msg)
        self.input_line = self.ui.lineEdit
        self.send_button = self.ui.pushButton

        self.send_button.clicked.connect(self.send_chat_message)
        self.input_line.returnPressed.connect(self.send_chat_message)
        self.start_jarvis()

    def append_ui_chat_msg(self, sender, message):
        # Format differently for user and Jarvis
        if sender.lower().startswith("user"):
            html = f"""
            <div style='display:flex; flex-direction: row-reverse; margin:12px 0 14px 0; align-items: flex-end;'>
                <div style="width:34px; height:34px; background:linear-gradient(100deg, #67e8f9,#4ade80); border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow: 2px 2px 11px #22d3ee44; font-size:16px; color:#0a0f1b; margin-left:9px;">
                    <span>🧑</span>
                </div>
                <div style="background:linear-gradient(87deg,#22d3ee 10%, #4ade80 90%); color:#fff; border-radius:16px 2.5em 16px 16px; box-shadow: 0 2px 24px #22d3ee33; padding:14px 20px; font-family:'Segoe UI',sans-serif; font-size:15px; letter-spacing:.01em; max-width:67%;">
                    {message}
                </div>
            </div>
            """
        else:
            html = f"""
            <div style='display:flex; flex-direction: row; margin:12px 0 14px 0; align-items: flex-end;'>
                <div style="width:34px; height:34px; background:linear-gradient(120deg, #94a3b8,#22d3ee); border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow: 2px 2px 11px #1e293b55; font-size:16px; color:#fff; margin-right:9px;">
                    <span>🤖</span>
                </div>
                <div style="background:linear-gradient(95deg, #1e293b 20%, #0a0f1b 100%); color:#aef1fc; border-radius:2.5em 16px 16px 16px; box-shadow: 0 1.5px 15px #22d3ee22; padding:14px 20px; font-family:'Segoe UI',sans-serif; font-size:15px; letter-spacing:.01em; max-width:67%;">
                    {message}
                </div>
            </div>
            """

        self.chat_area.append(html)
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())
        self.chat_area.setReadOnly(True)


    def toggle_mic_state(self):
        self.mic_active = not self.mic_active
        if self.mic_active:
            self.set_mic_status("LISTENING", "#4ade80")
            self.mic_scale_anim.setDirection(QPropertyAnimation.Forward)
            self.listen_and_process()
        else:
            self.set_mic_status("STANDBY", "#9ca3af")
            self.mic_scale_anim.setDirection(QPropertyAnimation.Backward)
        self.mic_scale_anim.start()

    def listen_and_process(self):
        user_text = listen()
        if user_text:
            self.input_line.setText(user_text)
            self.send_chat_message()

    def set_mic_status(self, text, color):
        self.mic_status_text.setText(text)
        self.mic_status_text.setStyleSheet(f"color: {color}; background: transparent;")
        self.mic_status_dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")

    def send_chat_message(self):
        text = self.input_line.text().strip()
        if not text:
            return

        # Show user's message on right side
        user_html = f"""
                <div style='text-align: right;'>
                    <div style="display:inline-block; background-color:#22d3ee; padding:8px 12px;
                                border-radius: 10px; color:white; font-family:'Segoe UI'; font-size:13px;
                                margin: 4px 0;">
                        {text}
                    </div>
                </div>
                """
        self.chat_area.append(user_html)
        self.input_line.clear()
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())
        self.ui.chatArea.setReadOnly(True)

        # Process input and show Jarvis response
        QTimer.singleShot(100, lambda: self.get_jarvis_response(text))

    def start_jarvis(self):
        self.jarvis_thread = JarvisThread()
        self.jarvis_thread.start()

    def get_jarvis_response(self, user_text):
        try:
            # You can pass `user_text` to brain if needed
            response = brain_cmd(user_text)

            # Speak out the response
            speak(response)

            # Show JARVIS response on left side
            jarvis_html = f"""
                    <div style='text-align: left;'>
                        <div style="display:inline-block; background-color:#1e293b; padding:8px 12px;
                                    border-radius: 10px; color:#aef1fc; font-family:'Segoe UI'; font-size:13px;
                                    margin: 4px 0;">
                            {response}
                        </div>
                    </div>
                    """
            self.chat_area.append(jarvis_html)
            self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())

        except Exception as e:
            print("Error in get_jarvis_response:", e)
            self.chat_area.append("<div style='color:red;'>Error in JARVIS response.</div>")


    def create_custom_title_bar(self):
        bar = QWidget()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(30)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(QPixmap("assets/logo.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setStyleSheet("background:transparent;")
        layout.addWidget(logo)
        title = QLabel("J.A.R.V.I.S - AI Assistant")
        title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background:transparent;")
        layout.addWidget(title)
        layout.addStretch()

        # Minimize
        min_btn = QPushButton()
        min_btn.setIcon(QIcon("assets/minimize-sign.png"))
        min_btn.setIconSize(QSize(9, 9))
        min_btn.setFixedSize(32, 32)
        min_btn.clicked.connect(self.showMinimized)

        # Maximize/Restore
        self.maximize_btn = QPushButton()
        self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
        self.maximize_btn.setIconSize(QSize(9, 9))
        self.maximize_btn.setFixedSize(32, 32)
        self.maximize_btn.clicked.connect(self.toggle_max_restore)

        # Close
        close_btn = QPushButton()
        close_btn.setIcon(QIcon("assets/close.png"))
        close_btn.setIconSize(QSize(9, 9))
        close_btn.setFixedSize(32, 32)
        close_btn.clicked.connect(self.close)
        layout.addWidget(min_btn)
        layout.addWidget(self.maximize_btn)
        layout.addWidget(close_btn)

        bar.setStyleSheet("""
                QWidget#titleBar { background-color: #222; border-bottom: 1px solid #444; }
                QPushButton { background-color: transparent; border: none; }
                QPushButton:hover { background-color: #444; }
            """)
        return bar


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 40:
            self._maybe_drag = True
            self._drag_start_pos = event.globalPos()
            self.dragging = False  # Only true when actual drag detected
            event.accept()
        else:
            super().mousePressEvent(event)


    def mouseMoveEvent(self, event):
        if hasattr(self, "_maybe_drag") and self._maybe_drag and not self.dragging:
            if (event.globalPos() - self._drag_start_pos).manhattanLength() > QApplication.startDragDistance():
                self.dragging = True
                self._maybe_drag = False
                # If maximized, restore and adjust drag position as before
                if self.isMaximized():
                    click_x = event.globalX()
                    width = self.width()
                    ratio = click_x / width if width else 0.5
                    self.showNormal()
                    self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
                    new_width = self.width()
                    new_x = int(event.globalX() - new_width * ratio)
                    new_y = event.globalY() - 20  # a bit below mouse for natural drag feel
                    self.move(new_x, new_y)
                    self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                else:
                    self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
        if self.dragging:
            # Existing drag code for move, including snapping logic
            self.move(event.globalPos() - self.drag_position)
            screen_top = QApplication.primaryScreen().availableGeometry().top()
            if event.globalPos().y() <= screen_top + 10:
                if not self.snapping:
                    self.snapping = True
                    if not hasattr(self, "preview_frame"):
                        self.preview_frame = QFrame(self)
                        self.preview_frame.setGeometry(QApplication.primaryScreen().availableGeometry())
                        self.preview_frame.setStyleSheet(
                            "background-color: rgba(34,211,238,0.15); border: 2px solid #22d3ee;")
                        self.preview_frame.show()
            else:
                if self.snapping:
                    self.snapping = False
                if hasattr(self, "preview_frame"):
                    self.preview_frame.hide()
                    self.preview_frame.deleteLater()
                    del self.preview_frame
            event.accept()
        else:
            super().mouseMoveEvent(event)


    def mouseReleaseEvent(self, event):
        self._maybe_drag = False
        if hasattr(self, "preview_frame"):
            self.preview_frame.hide()
            self.preview_frame.deleteLater()
            del self.preview_frame
        if self.dragging:
            screen_top = QApplication.primaryScreen().availableGeometry().top()
            if event.globalPos().y() <= screen_top + 10:
                self.showMaximized()
                self.maximize_btn.setIcon(QIcon("assets/minimize.png"))
            self.dragging = False
        self.drag_position = None
        self.snapping = False
        event.accept()
        super().mouseReleaseEvent(event)


    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 40:
            self.toggle_max_restore()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


    def toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
            self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
            # After restore, ensure the window is not above the screen's top
            geo = self.geometry()
            if geo.top() < 0:
                self.move(geo.x(), 0)
        else:
            self.showMaximized()
            self.maximize_btn.setIcon(QIcon("assets/minimize.png"))

        # All your JARVIS functionality methods


    def toggle_mic_state(self):
        self.mic_active = not self.mic_active
        if self.mic_active:
            self.set_mic_status("LISTENING", "#4ade80")
            self.mic_scale_anim.setDirection(QPropertyAnimation.Forward)
            self.listen_and_process()
        else:
            self.set_mic_status("STANDBY", "#9ca3af")
            self.mic_scale_anim.setDirection(QPropertyAnimation.Backward)
        self.mic_scale_anim.start()


    def listen_and_process(self):
        user_text = listen()
        if user_text:
            self.input_line.setText(user_text)
            self.send_chat_message()


    def set_mic_status(self, text, color):
        self.mic_status_text.setText(text)
        self.mic_status_text.setStyleSheet(f"color: {color}; background: transparent;")
        self.mic_status_dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")



if __name__ == "__main__":
    window = MainApp()
    window.show()
    sys.exit(app.exec_())

# import sys
# from PyQt5.QtWidgets import (
#     QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect
# )
# from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor, QPen, QPainter
# from PyQt5.QtCore import Qt, QSize, QThread, QRectF, QPropertyAnimation, QEasingCurve, QTimer
#
#
# def setup_animated_dot(button: QPushButton, color: str):
#     effect = QGraphicsDropShadowEffect(button)
#     effect.setColor(QColor(color))
#     effect.setOffset(0)
#     effect.setBlurRadius(8)
#     button.setGraphicsEffect(effect)
#
#     anim = QPropertyAnimation(effect, b"blurRadius")
#     anim.setStartValue(7)
#     anim.setEndValue(18)
#     anim.setDuration(1100)
#     anim.setLoopCount(-1)
#     anim.setEasingCurve(QEasingCurve.InOutSine)
#     anim.start()
#     return anim
#
#
# class VoiceLevelMeter(QWidget):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.level = 0.0
#         self.ring_color = QColor("#22d3ee")
#         self.animation_timer = QTimer(self)
#         self.animation_timer.timeout.connect(self.pulse)
#         self.pulse_phase = 0.0
#         self.animation_timer.start(30)
#
#     def setLevel(self, level):
#         self.level = max(0.0, min(level, 1.0))
#         self.update()
#
#     def pulse(self):
#         self.pulse_phase = (self.pulse_phase + 0.03) % 1.0
#         pulse_color = QColor.fromHsvF((0.54 + 0.12 * self.pulse_phase) % 1, 1, 1)
#         self.ring_color = pulse_color
#         self.update()
#
#     def paintEvent(self, event):
#         painter = QPainter(self)
#         painter.setRenderHint(QPainter.Antialiasing)
#         rect = QRectF(6, 6, self.width() - 12, self.height() - 12)
#
#         glow_pen = QPen(QColor(self.ring_color))
#         glow_pen.setWidth(20)
#         glow_pen.setColor(self.ring_color.lighter(150))
#         painter.setPen(glow_pen)
#         painter.drawArc(rect, 0, 360 * 16)
#
#         pen = QPen(QColor("#222f3e"), 10)
#         painter.setPen(pen)
#         painter.drawArc(rect, 0, 360 * 16)
#
#         pen.setColor(self.ring_color)
#         pen.setWidth(8)
#         painter.setPen(pen)
#         painter.drawArc(rect, 90 * 16, int(-360 * 16 * self.level))
#
# class JarvisThread(QThread):
#     def run(self):
#         pass
#         # jarvis()
#
# class MainApp(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.setWindowFlags(Qt.FramelessWindowHint)
#         self.setAttribute(Qt.WA_TranslucentBackground)
#         self.dragging = False
#         self.drag_position = None
#         self.snapping = False
#         self._restore_mouse_offset = None
#
#         # Set up UI
#         central_widget = QWidget()
#         central_layout = QVBoxLayout(central_widget)
#         central_layout.setContentsMargins(0, 0, 0, 0)
#         central_layout.setSpacing(0)
#         self.setCentralWidget(central_widget)
#
#         title_bar = self.create_custom_title_bar()
#         central_layout.addWidget(title_bar)
#
# main_content = QLabel("Main UI Goes Here", alignment=Qt.AlignCenter)
# main_content.setStyleSheet("background: #181c2f; color: #22d3ee; font-size: 18px;")
# central_layout.addWidget(main_content)
#
#         self.setMinimumSize(600, 400)
#         self.setWindowTitle("J.A.R.V.I.S - AI Assistant")
#         self.setWindowIcon(QIcon("assets/logo.png"))  # Adjust path as needed
#
#     def create_custom_title_bar(self):
#         bar = QWidget()
#         bar.setObjectName("titleBar")
#         bar.setFixedHeight(40)
#         layout = QHBoxLayout(bar)
#         layout.setContentsMargins(10, 0, 10, 0)
#         layout.setSpacing(10)
#
#         logo = QLabel()
#         logo.setPixmap(QPixmap("assets/logo.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
#         layout.addWidget(logo)
#         title = QLabel("J.A.R.V.I.S - AI Assistant")
#         title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background:transparent;")
#         layout.addWidget(title)
#         layout.addStretch()
#
#         # Minimize
#         min_btn = QPushButton()
#         min_btn.setIcon(QIcon("assets/minimize-sign.png"))
#         min_btn.setIconSize(QSize(16, 16))
#         min_btn.setFixedSize(32, 32)
#         min_btn.clicked.connect(self.showMinimized)
#
#         # Maximize/Restore
#         self.maximize_btn = QPushButton()
#         self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
#         self.maximize_btn.setIconSize(QSize(16, 16))
#         self.maximize_btn.setFixedSize(32, 32)
#         self.maximize_btn.clicked.connect(self.toggle_max_restore)
#
#         # Close
#         close_btn = QPushButton()
#         close_btn.setIcon(QIcon("assets/close.png"))
#         close_btn.setIconSize(QSize(16, 16))
#         close_btn.setFixedSize(32, 32)
#         close_btn.clicked.connect(self.close)
#         layout.addWidget(min_btn)
#         layout.addWidget(self.maximize_btn)
#         layout.addWidget(close_btn)
#
#         bar.setStyleSheet("""
#             QWidget#titleBar { background-color: #222; border-bottom: 1px solid #444; }
#             QPushButton { background-color: transparent; border: none; }
#             QPushButton:hover { background-color: #444; }
#         """)
#         return bar
#
#     def mousePressEvent(self, event):
#         if event.button() == Qt.LeftButton and event.pos().y() <= 40:
#             self._maybe_drag = True
#             self._drag_start_pos = event.globalPos()
#             self.dragging = False  # Only true when actual drag detected
#             event.accept()
#         else:
#             super().mousePressEvent(event)
#
#     def mouseMoveEvent(self, event):
#         if hasattr(self, "_maybe_drag") and self._maybe_drag and not self.dragging:
#             if (event.globalPos() - self._drag_start_pos).manhattanLength() > QApplication.startDragDistance():
#                 self.dragging = True
#                 self._maybe_drag = False
#                 # If maximized, restore and adjust drag position as before
#                 if self.isMaximized():
#                     click_x = event.globalX()
#                     width = self.width()
#                     ratio = click_x / width if width else 0.5
#                     self.showNormal()
#                     self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
#                     new_width = self.width()
#                     new_x = int(event.globalX() - new_width * ratio)
#                     new_y = event.globalY() - 20  # a bit below mouse for natural drag feel
#                     self.move(new_x, new_y)
#                     self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
#                 else:
#                     self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
#         if self.dragging:
#             # === Your existing drag code for move, INCLUDING snapping logic ===
#             self.move(event.globalPos() - self.drag_position)
#             screen_top = QApplication.primaryScreen().availableGeometry().top()
#             if event.globalPos().y() <= screen_top + 10:
#                 if not self.snapping:
#                     self.snapping = True
#                     if not hasattr(self, "preview_frame"):
#                         self.preview_frame = QFrame(self)
#                         self.preview_frame.setGeometry(QApplication.primaryScreen().availableGeometry())
#                         self.preview_frame.setStyleSheet(
#                             "background-color: rgba(34,211,238,0.15); border: 2px solid #22d3ee;")
#                         self.preview_frame.show()
#             else:
#                 if self.snapping:
#                     self.snapping = False
#                 if hasattr(self, "preview_frame"):
#                     self.preview_frame.hide()
#                     self.preview_frame.deleteLater()
#                     del self.preview_frame
#             event.accept()
#         else:
#             super().mouseMoveEvent(event)
#
#     def mouseReleaseEvent(self, event):
#         self._maybe_drag = False
#         if hasattr(self, "preview_frame"):
#             self.preview_frame.hide()
#             self.preview_frame.deleteLater()
#             del self.preview_frame
#         if self.dragging:
#             screen_top = QApplication.primaryScreen().availableGeometry().top()
#             if event.globalPos().y() <= screen_top + 10:
#                 self.showMaximized()
#                 self.maximize_btn.setIcon(QIcon("assets/minimize.png"))
#             self.dragging = False
#         self.drag_position = None
#         self.snapping = False
#         event.accept()
#         super().mouseReleaseEvent(event)
#
#     def mouseDoubleClickEvent(self, event):
#         if event.button() == Qt.LeftButton and event.pos().y() <= 40:
#             self.toggle_max_restore()
#             event.accept()
#         else:
#             super().mouseDoubleClickEvent(event)
#
#     def toggle_max_restore(self):
#         if self.isMaximized():
#             self.showNormal()
#             self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
#             # After restore, ensure the window is not above the screen's top
#             geo = self.geometry()
#             if geo.top() < 0:
#                 self.move(geo.x(), 0)
#         else:
#             self.showMaximized()
#             self.maximize_btn.setIcon(QIcon("assets/minimize.png"))
#
#
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     font = QFont("Segoe UI", 10)
#     app.setFont(font)
#     window = MainApp()
#     window.show()
#     sys.exit(app.exec_())

#     WORKING BASE UI
# import sys
# from PyQt5.QtWidgets import (
#     QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
# )
# from PyQt5.QtGui import QFont, QIcon, QPixmap
# from PyQt5.QtCore import Qt, QSize
#
# class MainApp(QMainWindow):
#     def __init__(self):
#         super().__init__()
#         self.setWindowFlags(Qt.FramelessWindowHint)
#         self.setAttribute(Qt.WA_TranslucentBackground)
#         self.dragging = False
#         self.drag_position = None
#         self.snapping = False
#         self._restore_mouse_offset = None
#
#         # Set up UI
#         central_widget = QWidget()
#         central_layout = QVBoxLayout(central_widget)
#         central_layout.setContentsMargins(0, 0, 0, 0)
#         central_layout.setSpacing(0)
#         self.setCentralWidget(central_widget)
#
#         title_bar = self.create_custom_title_bar()
#         central_layout.addWidget(title_bar)
#
#         main_content = QLabel("Main UI Goes Here", alignment=Qt.AlignCenter)
#         main_content.setStyleSheet("background: #181c2f; color: #22d3ee; font-size: 18px;")
#         central_layout.addWidget(main_content)
#
#         self.setMinimumSize(600, 400)
#         self.setWindowTitle("Custom Frameless Max/Restore Demo")
#         self.setWindowIcon(QIcon("assets/logo.png"))  # Adjust path as needed
#
#     def create_custom_title_bar(self):
#         bar = QWidget()
#         bar.setObjectName("titleBar")
#         bar.setFixedHeight(40)
#         layout = QHBoxLayout(bar)
#         layout.setContentsMargins(10, 0, 10, 0)
#         layout.setSpacing(10)
#
#         logo = QLabel()
#         logo.setPixmap(QPixmap("assets/logo.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
#         layout.addWidget(logo)
#         title = QLabel("JARVIS Demo")
#         title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background:transparent;")
#         layout.addWidget(title)
#         layout.addStretch()
#
#         # Minimize
#         min_btn = QPushButton()
#         min_btn.setIcon(QIcon("assets/minimize-sign.png"))
#         min_btn.setIconSize(QSize(16, 16))
#         min_btn.setFixedSize(32, 32)
#         min_btn.clicked.connect(self.showMinimized)
#
#         # Maximize/Restore
#         self.maximize_btn = QPushButton()
#         self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
#         self.maximize_btn.setIconSize(QSize(16, 16))
#         self.maximize_btn.setFixedSize(32, 32)
#         self.maximize_btn.clicked.connect(self.toggle_max_restore)
#
#         # Close
#         close_btn = QPushButton()
#         close_btn.setIcon(QIcon("assets/close.png"))
#         close_btn.setIconSize(QSize(16, 16))
#         close_btn.setFixedSize(32, 32)
#         close_btn.clicked.connect(self.close)
#         layout.addWidget(min_btn)
#         layout.addWidget(self.maximize_btn)
#         layout.addWidget(close_btn)
#
#         bar.setStyleSheet("""
#             QWidget#titleBar { background-color: #222; border-bottom: 1px solid #444; }
#             QPushButton { background-color: transparent; border: none; }
#             QPushButton:hover { background-color: #444; }
#         """)
#         return bar
#
#     def mousePressEvent(self, event):
#         if event.button() == Qt.LeftButton and event.pos().y() <= 40:
#             self._maybe_drag = True
#             self._drag_start_pos = event.globalPos()
#             self.dragging = False  # Only true when actual drag detected
#             event.accept()
#         else:
#             super().mousePressEvent(event)
#
#     def mouseMoveEvent(self, event):
#         if hasattr(self, "_maybe_drag") and self._maybe_drag and not self.dragging:
#             if (event.globalPos() - self._drag_start_pos).manhattanLength() > QApplication.startDragDistance():
#                 self.dragging = True
#                 self._maybe_drag = False
#                 # If maximized, restore and adjust drag position as before
#                 if self.isMaximized():
#                     click_x = event.globalX()
#                     width = self.width()
#                     ratio = click_x / width if width else 0.5
#                     self.showNormal()
#                     self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
#                     new_width = self.width()
#                     new_x = int(event.globalX() - new_width * ratio)
#                     new_y = event.globalY() - 20  # a bit below mouse for natural drag feel
#                     self.move(new_x, new_y)
#                     self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
#                 else:
#                     self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
#         if self.dragging:
#             # === Your existing drag code for move, INCLUDING snapping logic ===
#             self.move(event.globalPos() - self.drag_position)
#             screen_top = QApplication.primaryScreen().availableGeometry().top()
#             if event.globalPos().y() <= screen_top + 10:
#                 if not self.snapping:
#                     self.snapping = True
#                     if not hasattr(self, "preview_frame"):
#                         self.preview_frame = QFrame(self)
#                         self.preview_frame.setGeometry(QApplication.primaryScreen().availableGeometry())
#                         self.preview_frame.setStyleSheet(
#                             "background-color: rgba(34,211,238,0.15); border: 2px solid #22d3ee;")
#                         self.preview_frame.show()
#             else:
#                 if self.snapping:
#                     self.snapping = False
#                 if hasattr(self, "preview_frame"):
#                     self.preview_frame.hide()
#                     self.preview_frame.deleteLater()
#                     del self.preview_frame
#             event.accept()
#         else:
#             super().mouseMoveEvent(event)
#
#     def mouseReleaseEvent(self, event):
#         self._maybe_drag = False
#         if hasattr(self, "preview_frame"):
#             self.preview_frame.hide()
#             self.preview_frame.deleteLater()
#             del self.preview_frame
#         if self.dragging:
#             screen_top = QApplication.primaryScreen().availableGeometry().top()
#             if event.globalPos().y() <= screen_top + 10:
#                 self.showMaximized()
#                 self.maximize_btn.setIcon(QIcon("assets/minimize.png"))
#             self.dragging = False
#         self.drag_position = None
#         self.snapping = False
#         event.accept()
#         super().mouseReleaseEvent(event)
#
#     def mouseDoubleClickEvent(self, event):
#         if event.button() == Qt.LeftButton and event.pos().y() <= 40:
#             self.toggle_max_restore()
#             event.accept()
#         else:
#             super().mouseDoubleClickEvent(event)
#
#     def toggle_max_restore(self):
#         if self.isMaximized():
#             self.showNormal()
#             self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
#             # After restore, ensure the window is not above the screen's top
#             geo = self.geometry()
#             if geo.top() < 0:
#                 self.move(geo.x(), 0)
#         else:
#             self.showMaximized()
#             self.maximize_btn.setIcon(QIcon("assets/minimize.png"))
#
#
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     font = QFont("Segoe UI", 10)
#     app.setFont(font)
#     window = MainApp()
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)
#     window.show()
#     sys.exit(app.exec_())


<<<<<<< HEAD
# from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
# from PyQt5.QtGui import QMovie
# from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QObject
# import threading
# import subprocess
# import os,sys
# import pyautogui as gui
# from MAIN.main import jarvis
#
#
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#
# class SizeAnimator(QObject):
#     sizeChanged = pyqtSignal(QSize)
#
#     def animate(self, size, delay=0):
#         QTimer.singleShot(delay, lambda: self.sizeChanged.emit(size))
#
# class JarvisUI(QWidget):
#     def __init__(self):
#         super().__init__()
#
#         self.init_ui()
#
#     def init_ui(self):
#         self.setWindowTitle("Jarvis UI")
#         self.setGeometry(80,80,400,400)
#
#         self.setAttribute(Qt.WA_TranslucentBackground)
#         self.setWindowFlag(Qt.FramelessWindowHint)
#
#         self.mic_label = QLabel(self)
#
#         base_dir = os.path.dirname(os.path.abspath(__file__))
#         gif_path = os.path.abspath(os.path.join(base_dir, '..', 'USER_INTERFACE', 'XDZT.gif'))
#
#         self.add_gif_to_label(self.mic_label, gif_path, size=QSize(720, 720), alignment=Qt.AlignCenter)
#
#         self.mic_label.setAlignment(Qt.AlignCenter)
#         self.mic_label.mousePressEvent = self.start_listening
#
#         main_layout = QVBoxLayout(self)
#         main_layout.addWidget(self.mic_label , alignment=Qt.AlignCenter)
#
#         main_layout.setContentsMargins(20,20,20,20)
#         main_layout.setSpacing(20)
#
#         self.process = None
#         self.is_listening = False
#         self.size_animator = SizeAnimator()
#         self.size_animator.sizeChanged.connect(self.mic_label.setFixedSize)
#
#     def add_gif_to_label(self,label,gif_path, size=None, alignment=None):
#         movie = QMovie(gif_path)
#         label.setMovie(movie)
#         self.movie = movie
#         movie.start()
#
#         if size:
#             label.setFixedSize(size)
#         if alignment:
#             label.setAlignment(alignment)
#
#         shadow = QGraphicsDropShadowEffect()
#         shadow.setBlurRadius(15)
#         label.setGraphicsEffect(shadow)
#
#     def start_listening(self, event):
#         if not self.is_listening:
#             self.is_listening = True
#             subprocess_thread = threading.Thread(target=self.run_main_file)
#             subprocess_thread.start()
#
#     def run_main_file(self):
#         try:
#             jarvis()
#             self.is_listening = False
#         except Exception as e:
#             print(f"Error running jarvis(): {e}")
#
#     def handle_output(self, output):
#         if output.strip():
#             self.size_animator.animate(QSize(900,280))
#             self.size_animator.animate(QSize(720, 220) , delay=500)
#
#         else:
#             self.size_animator.animate(QSize(900,280))
#
# if __name__ == "__main__":
#     gui.hotkey("win","d")
#     app = QApplication([])
#
#     jarvis_ui = JarvisUI()
#     jarvis_ui.showFullScreen()
#
#     app.exec_()
#
#
=======
# import sys
# import os
# import random
#
# from PyQt5.QtWidgets import (
#     QApplication, QMainWindow, QPushButton, QLabel, QWidget, QVBoxLayout,
#     QScrollBar, QLineEdit, QTextEdit, QGraphicsBlurEffect, QGraphicsDropShadowEffect, QHBoxLayout
# )
# from PyQt5.QtGui import QFont, QIcon, QMovie, QPainter, QPen, QColor, QPixmap
# from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QRectF, QTimer
#
# from BRAIN.MAIN_BRAIN.BRAIN.brain import brain_cmd
# from FUNCTION.JARVIS_LISTEN.listen import listen
# from FUNCTION.JARVIS_SPEAK.speak import speak
#
# import sys
# from PyQt5.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget
# from PyQt5.QtCore import QThread, pyqtSignal
#
# from MAIN.main import jarvis
# from new_ui import Ui_MainWindow  # your .ui converted to .py
#
#
# # Enable high DPI scaling
# os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
# QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
# QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
#
## Initialize application
# app = QApplication(sys.argv)
# font = QFont("Segoe UI")
# font.setPointSize(10)
# app.setFont(font)
#
#
# def setup_animated_dot(button: QPushButton, color: str):
#     effect = QGraphicsDropShadowEffect(button)
#     effect.setColor(QColor(color))
#     effect.setOffset(0)
#     effect.setBlurRadius(8)
#     button.setGraphicsEffect(effect)
#
#     anim = QPropertyAnimation(effect, b"blurRadius")
#     anim.setStartValue(7)
#     anim.setEndValue(18)
#     anim.setDuration(1100)
#     anim.setLoopCount(-1)
#     anim.setEasingCurve(QEasingCurve.InOutSine)
#     anim.start()
#     return anim
#
#
# class VoiceLevelMeter(QWidget):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.level = 0.0
#         self.ring_color = QColor("#22d3ee")
#         self.animation_timer = QTimer(self)
#         self.animation_timer.timeout.connect(self.pulse)
#         self.pulse_phase = 0.0
#         self.animation_timer.start(30)
#
#     def setLevel(self, level):
#         self.level = max(0.0, min(level, 1.0))
#         self.update()
#
#     def pulse(self):
#         self.pulse_phase = (self.pulse_phase + 0.03) % 1.0
#         pulse_color = QColor.fromHsvF((0.54 + 0.12 * self.pulse_phase) % 1, 1, 1)
#         self.ring_color = pulse_color
#         self.update()
#
#     def paintEvent(self, event):
#         painter = QPainter(self)
#         painter.setRenderHint(QPainter.Antialiasing)
#         rect = QRectF(6, 6, self.width() - 12, self.height() - 12)
#
#         glow_pen = QPen(QColor(self.ring_color))
#         glow_pen.setWidth(20)
#         glow_pen.setColor(self.ring_color.lighter(150))
#         painter.setPen(glow_pen)
#         painter.drawArc(rect, 0, 360 * 16)
#
#         pen = QPen(QColor("#222f3e"), 10)
#         painter.setPen(pen)
#         painter.drawArc(rect, 0, 360 * 16)
#
#         pen.setColor(self.ring_color)
#         pen.setWidth(8)
#         painter.setPen(pen)
#         painter.drawArc(rect, 90 * 16, int(-360 * 16 * self.level))
#
# class JarvisThread(QThread):
#     def run(self):
#         pass
#         # jarvis()
#
# class MainApp(QMainWindow):
#     def __init__(self):
#         super(MainApp, self).__init__()
#
#         self.setWindowFlags(Qt.FramelessWindowHint)
#         self.setAttribute(Qt.WA_TranslucentBackground)
#         self.is_maximized = False
#         self.in_move_resize = False
#         self.dragging = False
#         self.drag_position = None
#         self.snapping = False
#
#     # Setup central widget
#     central_widget = QWidget()
#     central_layout = QVBoxLayout(central_widget)
#     central_layout.setContentsMargins(0, 0, 0, 0)
#     central_layout.setSpacing(0)
#
#     # Add your custom title bar
#     title_bar = self.create_custom_title_bar()
#     central_layout.addWidget(title_bar)
#
#     # Load UI from Qt Designer
#     self.ui = Ui_MainWindow()
#     self.ui.setupUi(self)
#
#     # You MUST add the loaded UI's central widget if it's not already
#     central_layout.addWidget(self.ui.centralwidget)
#
#     self.setCentralWidget(central_widget)
#
#     # Set app icon and title
#     self.setWindowIcon(QIcon("assets/logo.png"))
#     self.setWindowTitle("J.A.R.V.I.S - AI Assistant")
#
#     # Blur effect
#     blur = QGraphicsBlurEffect()
#     blur.setBlurRadius(22)
#     self.ui.chatBoxWrapper.setGraphicsEffect(blur)
#
#     # Optional neon shadow
#     shadow = QGraphicsDropShadowEffect()
#     shadow.setColor(QColor("#22d3ee"))
#     shadow.setBlurRadius(32)
#     shadow.setOffset(0, 0)
#     self.ui.chatBoxWrapper.setGraphicsEffect(shadow)
#
#     #setting up chat logo
#     self.ui.chatBoxLogo.setIcon(QIcon(r"assets\chat.png"))
#
#
#     # Mic animation & references
#     self.mic_btn = self.ui.MicIcon
#     self.mic_label_heading = self.ui.MicLabelHeading
#     self.mic_label_subheading = self.ui.MicLabelSubheading
#     self.mic_status_text = self.ui.belowMicText
#     self.mic_status_dot = self.ui.belowMicDot
#
#     self.mic_effect = QGraphicsDropShadowEffect(self)
#     self.mic_effect.setBlurRadius(20)
#     self.mic_effect.setColor(QColor("#22d3ee"))
#     self.mic_effect.setOffset(0)
#     self.mic_btn.setGraphicsEffect(self.mic_effect)
#
#     self.mic_glow_anim = QPropertyAnimation(self.mic_effect, b"blurRadius")
#     self.mic_glow_anim.setStartValue(20)
#     self.mic_glow_anim.setEndValue(45)
#     self.mic_glow_anim.setDuration(1800)
#     self.mic_glow_anim.setEasingCurve(QEasingCurve.InOutQuad)
#     self.mic_glow_anim.setLoopCount(-1)
#     self.mic_glow_anim.start()
#
#     self.mic_scale_anim = QPropertyAnimation(self.mic_btn, b"minimumSize")
#     self.mic_scale_anim.setStartValue(self.mic_btn.size())
#     self.mic_scale_anim.setEndValue(self.mic_btn.size() + QSize(8, 8))
#     self.mic_scale_anim.setDuration(400)
#     self.mic_scale_anim.setEasingCurve(QEasingCurve.OutQuad)
#
#     self.mic_btn.setIcon(QIcon(r"assets\microphone.png"))
#     self.mic_btn.setIconSize(self.mic_btn.iconSize())
#     self.mic_btn.clicked.connect(self.toggle_mic_state)
#
#     self.mic_active = False
#     self.set_mic_status("STANDBY", "#9ca3af")
#
#     # Dot animation setup (fixed)
#     self.dot1_anim = setup_animated_dot(self.ui.Dot_Operation_1, "#4ade80")
#     self.dot2_anim = setup_animated_dot(self.ui.Dot_Operation_2, "#22d3ee")
#     self.dot3_anim = setup_animated_dot(self.ui.Dot_Operation_3, "#60a5fa")
#     self.dot4_anim = setup_animated_dot(self.ui.Dot_Operation_4, "#818cf8")
#     self.dot5_anim = setup_animated_dot(self.ui.Dot_Operation_5, "#10b981")
#     self.dot6_anim = setup_animated_dot(self.ui.Dot_Operation_6, "#facc15")
#
#     # GIF arc logo
#     arc_gif_label = self.ui.arc_react_image_background
#     if arc_gif_label:
#         arc_gif_label.setScaledContents(True)
#         arc_movie = QMovie("assets/arc.gif")
#         arc_movie.setScaledSize(arc_gif_label.size())
#
#         def on_resize(event):
#             arc_movie.setScaledSize(arc_gif_label.size())
#             QLabel.resizeEvent(arc_gif_label, event)
#
#         arc_gif_label.resizeEvent = on_resize
#         arc_gif_label.setMovie(arc_movie)
#         arc_movie.start()
#
#     self.chat_area = self.ui.chatArea
#     self.input_line = self.ui.lineEdit
#     self.send_button = self.ui.pushButton
#
#     self.send_button.clicked.connect(self.send_chat_message)
#     self.input_line.returnPressed.connect(self.send_chat_message)
#
# def toggle_mic_state(self):
#     self.mic_active = not self.mic_active
#     if self.mic_active:
#         self.set_mic_status("LISTENING", "#4ade80")
#         self.mic_scale_anim.setDirection(QPropertyAnimation.Forward)
#         self.listen_and_process()
#     else:
#         self.set_mic_status("STANDBY", "#9ca3af")
#         self.mic_scale_anim.setDirection(QPropertyAnimation.Backward)
#     self.mic_scale_anim.start()
#
# def listen_and_process(self):
#     user_text = listen()
#     if user_text:
#         self.input_line.setText(user_text)
#         self.send_chat_message()
#
# def set_mic_status(self, text, color):
#     self.mic_status_text.setText(text)
#     self.mic_status_text.setStyleSheet(f"color: {color}; background: transparent;")
#     self.mic_status_dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
#
# def send_chat_message(self):
#     text = self.input_line.text().strip()
#     if not text:
#         return
#
#     # Show user's message on right side
#     user_html = f"""
#     <div style='text-align: right;'>
#         <div style="display:inline-block; background-color:#22d3ee; padding:8px 12px;
#                     border-radius: 10px; color:white; font-family:'Segoe UI'; font-size:13px;
#                     margin: 4px 0;">
#             {text}
#         </div>
#     </div>
#     """
#     self.chat_area.append(user_html)
#     self.input_line.clear()
#     self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())
#     self.ui.chatArea.setReadOnly(True)
#
#     # Process input and show Jarvis response
#     QTimer.singleShot(100, lambda: self.get_jarvis_response(text))
#
# def start_jarvis(self):
#     self.jarvis_thread = JarvisThread()
#     self.jarvis_thread.start()
#
# def get_jarvis_response(self, user_text):
#     try:
#         # You can pass `user_text` to brain if needed
#         response = brain_cmd(user_text)
#
#         # Speak out the response
#         speak(response)
#
#         # Show JARVIS response on left side
#         jarvis_html = f"""
#         <div style='text-align: left;'>
#             <div style="display:inline-block; background-color:#1e293b; padding:8px 12px;
#                         border-radius: 10px; color:#aef1fc; font-family:'Segoe UI'; font-size:13px;
#                         margin: 4px 0;">
#                 {response}
#             </div>
#         </div>
#         """
#         self.chat_area.append(jarvis_html)
#         self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())
#
#     except Exception as e:
#         print("Error in get_jarvis_response:", e)
#         self.chat_area.append("<div style='color:red;'>Error in JARVIS response.</div>")

#     def create_custom_title_bar(self):
#         title_bar = QWidget()
#         title_bar.setObjectName("titleBar")
#         title_bar.setFixedHeight(40)
#
#         # Layout
#         layout = QHBoxLayout(title_bar)
#         layout.setContentsMargins(10, 0, 10, 0)
#         layout.setSpacing(10)
#
#         # Logo
#         logo = QLabel()
#         logo.setPixmap(QPixmap("assets/logo.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
#         logo.setStyleSheet("background:transparent;")
#         layout.addWidget(logo)
#
#         # Title
#         title = QLabel("My JARVIS")
#         title.setStyleSheet("color: white; font-weight: bold; font-size: 14px;background:transparent;")
#         layout.addWidget(title)
#
#         layout.addStretch()
#
#         # Minimize
#         minimize_btn = QPushButton()
#         minimize_btn.setIcon(QIcon("assets/minimize-sign.png"))
#         minimize_btn.setIconSize(QSize(9, 9))
#         minimize_btn.setFixedSize(32, 32)
#         minimize_btn.clicked.connect(self.showMinimized)
#
#         # Maximize/Restore
#         self.maximize_btn = QPushButton()
#         self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
#         self.maximize_btn.setIconSize(QSize(9, 9))
#         self.maximize_btn.setFixedSize(32, 32)
#         self.maximize_btn.clicked.connect(self.toggle_max_restore)
#
#         # Close
#         close_btn = QPushButton()
#         close_btn.setIcon(QIcon("assets/close.png"))
#         close_btn.setIconSize(QSize(9, 9))
#         close_btn.setFixedSize(32, 32)
#         close_btn.clicked.connect(self.close)
#
#         layout.addWidget(minimize_btn)
#         layout.addWidget(self.maximize_btn)  # <- ADD THIS
#         layout.addWidget(close_btn)
#
#         # Apply styles
#         title_bar.setStyleSheet("""
#             QWidget#titleBar {
#                 background-color: #222;  /* Dark background */
#                 border-bottom: 1px solid #444;
#             }
#             QPushButton {
#                 background-color: transparent;
#                 color: white;
#                 font-size: 12px;
#                 border: none;
#             }
#             QPushButton:hover {
#                 background-color: #444;
#             }
#         """)
#
#         return title_bar
#
#     # ---- DRAGGING AND MAXIMIZE/SNAP ----
#     def mousePressEvent(self, event):
#         if event.button() == Qt.LeftButton and event.pos().y() <= 40:
#             self.dragging = True
#             self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
#             self.snapping = False
#             # --- Only restore ONCE, at drag start! ---
#             if self.isMaximized():
#                 self.showNormal()
#                 self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
#             event.accept()
#         else:
#             super().mousePressEvent(event)
#
#     def mouseMoveEvent(self, event):
#         if event.buttons() == Qt.LeftButton and self.dragging:
#             self.move(event.globalPos() - self.drag_position)
#             screen_top = QApplication.primaryScreen().availableGeometry().top()
#             # preview frame if near top
#             if event.globalPos().y() <= screen_top + 10:
#                 if not self.snapping:
#                     self.snapping = True
#                     if not hasattr(self, "preview_frame"):
#                         self.preview_frame = QFrame(self)
#                         self.preview_frame.setGeometry(QApplication.primaryScreen().availableGeometry())
#                         self.preview_frame.setStyleSheet(
#                             "background-color: rgba(34,211,238,0.15); border: 2px solid #22d3ee;")
#                         self.preview_frame.show()
#             else:
#                 if self.snapping:
#                     self.snapping = False
#                 if hasattr(self, "preview_frame"):
#                     self.preview_frame.hide()
#                     self.preview_frame.deleteLater()
#                     del self.preview_frame
#             event.accept()
#         else:
#             super().mouseMoveEvent(event)
#
#     def mouseReleaseEvent(self, event):
#         # remove preview always
#         if hasattr(self, "preview_frame"):
#             self.preview_frame.hide()
#             self.preview_frame.deleteLater()
#             del self.preview_frame
#         if self.dragging:
#             screen_top = QApplication.primaryScreen().availableGeometry().top()
#             if event.globalPos().y() <= screen_top + 10:
#                 self.showMaximized()
#                 self.maximize_btn.setIcon(QIcon("assets/minimize.png"))
#             self.dragging = False
#         self.drag_position = None
#         self.snapping = False
#         event.accept()
#         super().mouseReleaseEvent(event)
#
#     def mouseDoubleClickEvent(self, event):
#         if event.button() == Qt.LeftButton and event.pos().y() <= 40:
#             self.toggle_max_restore()
#             event.accept()
#         else:
#             super().mouseDoubleClickEvent(event)
#
#     def toggle_max_restore(self):
#         if self.isMaximized():
#             self.showNormal()
#             self.maximize_btn.setIcon(QIcon("assets/maximize.png"))
#         else:
#             self.showMaximized()
#             self.maximize_btn.setIcon(QIcon("assets/minimize.png"))
#
# if __name__ == "__main__":
#     window = MainApp()
#     window.show()
#     sys.exit(app.exec_())
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)
