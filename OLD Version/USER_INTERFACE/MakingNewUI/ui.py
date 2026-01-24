import sys
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt5.QtGui import QPalette, QBrush, QPixmap, QPainter, QRadialGradient, QLinearGradient, QColor
from PyQt5.QtCore import Qt, QSize

class JarvisUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS UI")
        self.showFullScreen()

        # Create background widget
        self.bg_label = QLabel(self)
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        self.bg_label.lower()  # Ensure it stays behind

        # Paint all layers
        self.bg_label.paintEvent = self.paint_background

        # Optional: Force repaint on resize
        self.bg_label.resizeEvent = lambda event: self.bg_label.update()

    def paint_background(self, event):
        painter = QPainter(self.bg_label)
        painter.setRenderHint(QPainter.Antialiasing)

        # Step 1: Black Background
        painter.fillRect(self.bg_label.rect(), QColor(0, 0, 0))

        # Step 2: Linear Gradient (Top-Left to Bottom-Right)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0, QColor(31, 41, 55))     # from-gray-900
        grad.setColorAt(0.5, QColor(0, 0, 0))       # via-black
        grad.setColorAt(1, QColor(30, 58, 138, 51)) # to-blue-900/20
        painter.fillRect(self.bg_label.rect(), grad)

        # Step 3: Radial Gradient Glow (centered)
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = min(self.width(), self.height()) / 1.2
        radial = QRadialGradient(center_x, center_y, radius)
        radial.setColorAt(0, QColor(0, 255, 255, 25))   # cyan glow
        radial.setColorAt(0.5, Qt.transparent)
        radial.setColorAt(1, Qt.transparent)
        painter.fillRect(self.bg_label.rect(), radial)

        # Step 4: Circuit Overlay Image (if available)
        try:
            circuit = QPixmap("circuit.png").scaled(
                self.bg_label.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            painter.setOpacity(0.3)
            painter.drawPixmap(0, 0, circuit)
            painter.setOpacity(1.0)
        except Exception as e:
            print("Could not load circuit.png:", e)

        painter.end()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JarvisUI()
    window.show()
    sys.exit(app.exec_())


# import sys
# from PyQt5.QtWidgets import (
#     QApplication, QMainWindow, QLabel, QPushButton, QTextEdit, QWidget, QVBoxLayout, QHBoxLayout
# )
# from PyQt5.QtGui import QMovie, QFont, QPixmap
# from PyQt5.QtCore import Qt

#
# class JarvisUI(QMainWindow):
#     def __init__(self):
#         super().__init__()
#
#         self.setWindowTitle("J.A.R.V.I.S Interface")
#         self.setGeometry(100, 100, 1366, 768)
#         self.setFixedSize(1366, 768)
#
#         self.initUI()
#
#     def initUI(self):
#         # Set background color or image
#         self.setStyleSheet("background-color: black;")
#
#         # Central widget
#         self.central_widget = QWidget()
#         self.setCentralWidget(self.central_widget)
#
#         # MAIN LAYOUT
#         self.main_layout = QVBoxLayout(self.central_widget)
#
#         # TITLE + SUBTITLES
#         self.title = QLabel("J.A.R.V.I.S", self)
#         self.title.setFont(QFont("Arial", 32, QFont.Bold))
#         self.title.setStyleSheet("color: cyan;")
#         self.title.setAlignment(Qt.AlignCenter)
#
#         self.subtitle1 = QLabel("Just A Rather Very Intelligent System", self)
#         self.subtitle1.setFont(QFont("Arial", 14))
#         self.subtitle1.setStyleSheet("color: lightgray;")
#         self.subtitle1.setAlignment(Qt.AlignCenter)
#
#         self.subtitle2 = QLabel("STARK INDUSTRIES • MARK 52 INTERFACE", self)
#         self.subtitle2.setFont(QFont("Arial", 12))
#         self.subtitle2.setStyleSheet("color: gray;")
#         self.subtitle2.setAlignment(Qt.AlignCenter)
#
#         self.main_layout.addWidget(self.title)
#         self.main_layout.addWidget(self.subtitle1)
#         self.main_layout.addWidget(self.subtitle2)
#
#         # ARC REACTOR (Center GIF)
#         self.arc_label = QLabel(self)
#         self.arc_label.setAlignment(Qt.AlignCenter)
#         self.movie = QMovie("XDZT.gif")  # ← Add your .gif in the project folder
#         self.arc_label.setMovie(self.movie)
#         self.movie.start()
#         self.main_layout.addWidget(self.arc_label)
#
#         # STATUS INDICATORS
#         status_layout = QHBoxLayout()
#
#         for status_text in ["● ONLINE", "● SECURE", "● READY"]:
#             label = QLabel(status_text)
#             label.setStyleSheet("color: lime; font-weight: bold; font-size: 12px;")
#             status_layout.addWidget(label, alignment=Qt.AlignCenter)
#
#         self.main_layout.addLayout(status_layout)
#
#         # BOTTOM ROW LAYOUT
#         bottom_layout = QHBoxLayout()
#
#         # VOICE BUTTON (bottom-left)
#         self.voice_btn = QPushButton("🎙 Voice Command")
#         self.voice_btn.setFixedSize(150, 150)
#         self.voice_btn.setStyleSheet("""
#             QPushButton {
#                 background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,
#                                                   stop:0 cyan, stop:1 blue);
#                 color: white;
#                 font-size: 14px;
#                 font-weight: bold;
#                 border-radius: 75px;
#             }
#         """)
#         bottom_layout.addWidget(self.voice_btn, alignment=Qt.AlignLeft)
#
#         # CHAT PANEL (bottom-right)
#         self.chat_box = QTextEdit()
#         self.chat_box.setPlaceholderText("Chat Panel...")
#         self.chat_box.setFixedSize(400, 200)
#         self.chat_box.setStyleSheet("""
#             QTextEdit {
#                 background-color: #111;
#                 color: white;
#                 border: 2px solid cyan;
#                 font-family: Consolas;
#                 font-size: 12px;
#             }
#         """)
#         bottom_layout.addWidget(self.chat_box, alignment=Qt.AlignRight)
#
#         self.main_layout.addLayout(bottom_layout)
#
#
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = JarvisUI()
#     window.show()
#     sys.exit(app.exec_())
