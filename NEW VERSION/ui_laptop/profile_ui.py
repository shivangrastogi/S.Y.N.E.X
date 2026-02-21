# Path: d:\New folder (2) - JARVIS\ui_laptop\profile_ui.py
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QWidget, QMenu, QInputDialog, QMessageBox, QRubberBand)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPoint, QRect, QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QIcon, QAction, QRegion, QBrush, QPen
import os
import json

# Define persistence path (relative to app root, or could be absolute)
# We'll use a local file for simplicity
PROFILE_DATA_PATH = "user_profile.json"

class ImageCropDialog(QDialog):
    """Dialog to crop an image to a square aspect ratio."""
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop Avatar")
        self.setModal(True)
        self.resize(500, 500)
        
        self.original_pixmap = QPixmap(image_path)
        if self.original_pixmap.isNull():
            # Fallback or error
            pass
            
        self.layout = QVBoxLayout(self)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not self.original_pixmap.isNull():
             # Basic scaling for display
            self.image_label.setPixmap(self.original_pixmap.scaled(400, 400, Qt.AspectRatioMode.KeepAspectRatio))
        self.image_label.setStyleSheet("border: 1px solid #00d4ff;")
        self.layout.addWidget(self.image_label)
        
        self.instructions = QLabel("Image will be center-cropped to square automatically.")
        self.instructions.setStyleSheet("color: #888;")
        self.layout.addWidget(self.instructions)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton("Save Crop")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        self.layout.addLayout(btns)
        
        self.cropped_pixmap = None
        
        # Style
        self.setStyleSheet("""
            QDialog { background-color: #0a1628; color: white; }
            QPushButton { background: #00d4ff; color: black; border-radius: 4px; padding: 6px; }
            QPushButton:hover { background: #00ffff; }
        """)

    def accept(self):
        # Auto-center crop logic
        if self.original_pixmap.isNull():
             super().reject()
             return

        w = self.original_pixmap.width()
        h = self.original_pixmap.height()
        size = min(w, h)
        
        x = (w - size) // 2
        y = (h - size) // 2
        
        self.cropped_pixmap = self.original_pixmap.copy(x, y, size, size)
        super().accept()

class UserAvatarWidget(QWidget):
    """Circular user avatar with context menu for interaction."""
    
    avatar_changed = pyqtSignal(str) # Emits new path
    
    def __init__(self, parent=None, size=64):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.avatar_path = None
        self.username = "User"
        self.default_avatar = None
        
        # Load from persistence
        self.load_profile()
        
    def set_default_icon(self, icon_path):
        if os.path.exists(icon_path):
            self.default_avatar = QPixmap(icon_path)
            self.update()
        
    def load_profile(self):
        if os.path.exists(PROFILE_DATA_PATH):
            try:
                with open(PROFILE_DATA_PATH, 'r') as f:
                    data = json.load(f)
                    self.username = data.get("username", "User")
                    path = data.get("avatar_path")
                    if path and os.path.exists(path):
                        self.avatar_path = path
            except Exception as e:
                print(f"Error loading profile: {e}")
        self.update()

    def save_profile(self):
        data = {
            "username": self.username,
            "avatar_path": self.avatar_path
        }
        try:
            with open(PROFILE_DATA_PATH, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving profile: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.show_context_menu(event.globalPosition().toPoint())
            
    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #0a1628; border: 1px solid #00d4ff; color: white; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #00d4ff; color: black; }
        """)
        
        update_action = menu.addAction("Update Picture")
        remove_action = menu.addAction("Remove Picture")
        remove_action.setEnabled(self.avatar_path is not None)
        
        menu.addSeparator()
        set_name_action = menu.addAction("Set Username")
        
        action = menu.exec(pos)
        
        if action == update_action:
            self.change_picture()
        elif action == remove_action:
            self.remove_picture()
        elif action == set_name_action:
            self.set_username()
            
    def change_picture(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Avatar", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            dlg = ImageCropDialog(path, self)
            if dlg.exec() and dlg.cropped_pixmap:
                # Save cropped
                import shutil
                
                # Use a specific local dir
                save_dir = "user_data"
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                    
                target = os.path.join(save_dir, "avatar.png")
                dlg.cropped_pixmap.save(target)
                
                self.avatar_path = target
                # We save relative path or absolute? Let's use relative if possible, or abs
                self.avatar_path = os.path.abspath(target)
                
                self.avatar_changed.emit(self.avatar_path)
                self.save_profile()
                self.update()
                
    def remove_picture(self):
        self.avatar_path = None
        self.avatar_changed.emit("")
        self.save_profile()
        self.update()
        
    def set_username(self):
        text, ok = QInputDialog.getText(self, "Set Username", "Enter new username:", text=self.username)
        if ok and text:
            self.username = text
            self.save_profile()
            self.update()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        w, h = self.width(), self.height()
        rect = self.rect()
        
        # 1. Outer Glow/Ring
        # Draw a soft outer glow
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Draw main cinematic border
        border_pen = QPen(QColor("#00d4ff"), 2)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(2, 2, w-4, h-4)
        
        # Inner thin ring for tech look
        painter.setPen(QPen(QColor("#00d4ff"), 0.5))
        painter.drawEllipse(6, 6, w-12, h-12)

        # 2. Avatar Content
        # Clip to inner circle
        path = QPainterPath()
        # Clip slightly inside the border
        margin = 8
        path.addEllipse(margin, margin, w - margin*2, h - margin*2)
        painter.setClipPath(path)
        
        # Determine image source
        pixmap_to_draw = None
        if self.avatar_path and os.path.exists(self.avatar_path):
             loaded = QPixmap(self.avatar_path)
             if not loaded.isNull():
                 pixmap_to_draw = loaded
        elif self.default_avatar and not self.default_avatar.isNull():
             pixmap_to_draw = self.default_avatar
             
        if pixmap_to_draw:
             # Scale with high quality
             # We scale to the cropped area size
             target_size = QSize(w - margin*2, h - margin*2)
             scaled = pixmap_to_draw.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
             
             # Center align
             x = (w - scaled.width()) // 2
             y = (h - scaled.height()) // 2
             painter.drawPixmap(x, y, scaled)
        else:
             # Fallback placeholder
             painter.setBrush(QColor(20, 40, 60))
             painter.drawRect(rect)
             # Draw generic user symbol
             painter.setPen(QPen(QColor("#00d4ff"), 2))
             cx, cy = self.width()//2, self.height()//2
             # Head
             painter.drawEllipse(QPoint(cx, cy-8), 10, 10)
             # Body curve
             painter.drawArc(cx-15, cy+5, 30, 20, 0, 180*16)
        
        # Reset clipping for any top-layer gloss (optional)
        painter.setClipping(False)
