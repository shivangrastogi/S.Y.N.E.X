import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QRadialGradient, QBrush, QConicalGradient

class ArcReactorWidget(QWidget):
    """
    ARC REACTOR MK-II: High-Fidelity Stark HUD Component.
    Optimized 2D Vector Graphics with Cinematic Glows.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self._angle = 0
        self._inner_angle = 0
        self._pulse = 0
        self._pulse_dir = 1
        self._intensity = 0.0 # Driven by voice
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)
        self.timer.start(16)

    def _update_animation(self):
        # Variable speeds for cinematic feel
        self._angle = (self._angle + 1.2) % 360
        self._inner_angle = (self._inner_angle - 0.8) % 360
        
        # Smooth pulse
        self._pulse += 0.03 * self._pulse_dir
        if self._pulse > 1.0 or self._pulse < 0:
            self._pulse_dir *= -1
        
        # Decay intensity slowly
        self._intensity = max(0, self._intensity - 0.05)
        self.update()

    def set_intensity(self, val):
        self._intensity = max(self._intensity, val)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        cx, cy = self.width() / 2, self.height() / 2
        radius = min(cx, cy) * 0.75
        
        # --- 1. AMBIENT FIELD GLOW ---
        field_r = radius * 1.6
        field_grad = QRadialGradient(cx, cy, field_r)
        glow_alpha = int(30 + (40 * self._intensity))
        field_grad.setColorAt(0, QColor(0, 242, 255, glow_alpha))
        field_grad.setColorAt(0.7, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), QBrush(field_grad))

        # --- 2. OUTER TECHNICAL RINGS ---
        painter.setPen(QPen(QColor(0, 242, 255, 40), 1))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)
        painter.drawEllipse(QPointF(cx, cy), radius * 1.05, radius * 1.05)

        # --- 3. ROTATING SEGMENTS (OUTER) ---
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._angle)
        pen = QPen(QColor(0, 242, 255, 180), 6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        # 4 Bold Arcs
        for i in range(4):
            rect = QRectF(-radius*0.85, -radius*0.85, radius*1.7, radius*1.7)
            painter.drawArc(rect, i*90*16 + 10*16, 70*16)
        painter.restore()

        # --- 4. INNER ROTATING CORE (MK-II) ---
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._inner_angle)
        
        # Drawing 8 Core "Vents"
        vent_r = radius * 0.45
        for i in range(8):
            painter.rotate(45)
            # Vent block
            painter.setBrush(QColor(0, 242, 255, 100))
            painter.setPen(Qt.NoPen)
            painter.drawRect(int(vent_r*0.8), -4, int(vent_r*0.3), 8)
            # Glowing filament
            painter.setBrush(QColor(255, 255, 255, 200))
            painter.drawRect(int(vent_r*0.9), -1, int(vent_r*0.1), 2)
        painter.restore()

        # --- 5. THE SINGULARITY (THE CENTER) ---
        core_r = radius * 0.3 * (1.0 + 0.3 * self._intensity)
        core_grad = QRadialGradient(cx, cy, core_r)
        core_grad.setColorAt(0, QColor(255, 255, 255, 255))
        core_grad.setColorAt(0.4, QColor(0, 242, 255, 255))
        core_grad.setColorAt(1, QColor(0, 100, 150, 0))
        
        painter.setBrush(QBrush(core_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)
        
        # Concentric Interference Rings
        for i in range(1, 4):
            ring_alpha = int(100 / i)
            painter.setPen(QPen(QColor(255, 255, 255, ring_alpha), 1))
            painter.drawEllipse(QPointF(cx, cy), core_r * (1 + i*0.2), core_r * (1 + i*0.2))

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QVBoxLayout
    app = QApplication(sys.argv)
    window = QWidget()
    window.setStyleSheet("background-color: #05070a;")
    layout = QVBoxLayout(window)
    reactor = ArcReactorWidget()
    layout.addWidget(reactor)
    window.show()
    sys.exit(app.exec_())
