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
#     window.show()
#     sys.exit(app.exec_())


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
