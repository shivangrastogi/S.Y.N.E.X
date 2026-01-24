import sys
import os
import random

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QWidget, QVBoxLayout,
    QScrollBar, QLineEdit, QTextEdit, QGraphicsBlurEffect, QGraphicsDropShadowEffect
)
from PyQt5.QtGui import QFont, QIcon, QMovie, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, QRectF, QTimer

from NEW_UI.new_ui import Ui_MainWindow  # ✅ Make sure path is correct


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


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # self.voice_meter = VoiceLevelMeter(self.ui.voiceLevelMeterWidget)
        # self.ui.micBoxLayout.insertWidget(1, self.voice_meter)
        #
        # self.voice_level_timer = QTimer()
        # self.voice_level_timer.timeout.connect(lambda: self.voice_meter.setLevel(random.uniform(0, 1)))
        # self.voice_level_timer.start(80)

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

        self.mic_btn.setIcon(QIcon("assets/microphone.png"))
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
        self.input_line = self.ui.lineEdit
        self.send_button = self.ui.pushButton

        self.send_button.clicked.connect(self.send_chat_message)
        self.input_line.returnPressed.connect(self.send_chat_message)

    def toggle_mic_state(self):
        self.mic_active = not self.mic_active
        if self.mic_active:
            self.set_mic_status("LISTENING", "#4ade80")
            self.mic_scale_anim.setDirection(QPropertyAnimation.Forward)
        else:
            self.set_mic_status("STANDBY", "#9ca3af")
            self.mic_scale_anim.setDirection(QPropertyAnimation.Backward)
        self.mic_scale_anim.start()

    def set_mic_status(self, text, color):
        self.mic_status_text.setText(text)
        self.mic_status_text.setStyleSheet(f"color: {color}; background: transparent;")
        self.mic_status_dot.setStyleSheet(f"background-color: {color}; border-radius: 4px;")

    def send_chat_message(self):
        text = self.input_line.text().strip()
        if not text:
            return

        html = f'<div style="color:#aef1fc;font-family:\'Exo\';font-size:13px;">You: {text}</div>'
        self.chat_area.append(html)
        self.input_line.clear()
        self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum())


if __name__ == "__main__":
    window = MainApp()
    window.show()
    sys.exit(app.exec_())
