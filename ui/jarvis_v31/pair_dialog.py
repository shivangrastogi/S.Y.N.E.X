"""In-app phone-pairing popup — shows the QR + instructions.

Replaces the old ``os.startfile(qr.png)`` (which dumped the QR into the OS
image viewer, disconnected from AERIS). When the user says "phone pair
karo", the bridge_pair skill returns a ``[pair_qr]<path>`` sentinel; the
main window catches it and shows this dialog on the GUI thread.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QDialog, QLabel, QPushButton, QVBoxLayout, QWidget, QHBoxLayout,
)

from ui.jarvis_v31.tokens import J, inter, mono


class PairDialog(QDialog):
    """Frameless glass popup with the pairing QR + step-by-step hints."""

    def __init__(self, qr_path: str, pid_prefix: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pair your phone")
        self.setModal(False)
        self.setMinimumWidth(360)
        self.setStyleSheet(f"QDialog {{ background: {J.BG.name()}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        # Header
        title = QLabel("Pair AERIS Remote")
        title.setFont(inter(17, 800))
        title.setStyleSheet(f"color: {J.CYAN.name()}; ")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        sub = QLabel("Scan this with the AERIS Remote app.\n"
                     "Ek baar scan — phir kahin se bhi connected.")
        sub.setFont(inter(10, 400))
        sub.setStyleSheet(f"color: {J.TEXT_MUT.name()};")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        root.addWidget(sub)

        # QR image on a white card (scanners want light background + quiet zone)
        qr_card = QWidget()
        qr_card.setStyleSheet("background: white; border-radius: 12px;")
        qr_lay = QVBoxLayout(qr_card)
        qr_lay.setContentsMargins(16, 16, 16, 16)
        qr_label = QLabel()
        pix = QPixmap(qr_path)
        if not pix.isNull():
            pix = pix.scaled(240, 240, Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
            qr_label.setPixmap(pix)
        else:
            qr_label.setText("QR load nahi hua\n" + qr_path)
            qr_label.setStyleSheet("color: #c00;")
        qr_label.setAlignment(Qt.AlignCenter)
        qr_lay.addWidget(qr_label)
        root.addWidget(qr_card, alignment=Qt.AlignCenter)

        # Steps
        steps = QLabel(
            "1.  Phone pe AERIS Remote kholo\n"
            "2.  Scan button dabao, ye QR dikhaao\n"
            "3.  Ho gaya — laptop control ready"
        )
        steps.setFont(mono(9, 400))
        steps.setStyleSheet(f"color: {J.TEXT_PRI.name()}; line-height: 150%;")
        root.addWidget(steps)

        if pid_prefix:
            pid_lbl = QLabel(f"pair id: {pid_prefix}…   ·   E2E encrypted")
            pid_lbl.setFont(mono(8, 400))
            pid_lbl.setStyleSheet(f"color: {J.TEXT_MUT.name()};")
            pid_lbl.setAlignment(Qt.AlignCenter)
            root.addWidget(pid_lbl)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        done = QPushButton("Done")
        done.setCursor(Qt.PointingHandCursor)
        done.setFont(inter(10, 700))
        done.setStyleSheet(
            f"QPushButton {{ background: {J.CYAN.name()}; color: #04121a; "
            f"border: none; border-radius: 8px; padding: 8px 22px; }}"
        )
        done.clicked.connect(self.accept)
        btn_row.addWidget(done)
        root.addLayout(btn_row)

    @staticmethod
    def show_for(qr_path: str, pid_prefix: str = "", parent=None) -> "PairDialog":
        dlg = PairDialog(qr_path, pid_prefix, parent)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return dlg
