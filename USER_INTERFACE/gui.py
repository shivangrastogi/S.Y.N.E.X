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
#     window.show()
#     sys.exit(app.exec_())


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
