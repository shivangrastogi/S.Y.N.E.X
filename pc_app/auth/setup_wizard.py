# auth/setup_wizard.py
import os
import sys
import requests
import zipfile
from io import BytesIO
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QProgressBar, QLabel, QPushButton, QStackedWidget, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt

# --- !!! IMPORTANT !!! ---
# Host your Vosk model (the whole .zip file) somewhere.
# You can use GitHub Releases, Google Drive, etc.
MODEL_URL = "https://drive.google.com/drive/folders/1MEOl8FE1XelwBNd6QoA-ClP6HJhFUJMv?usp=sharing"

# This is the standard, safe place to store app data on Windows
# It resolves to C:\Users\<Username>\AppData\Roaming\JARVIS
MODEL_PATH = os.path.join(os.environ['APPDATA'], "JARVIS_MODELS")
VOSK_MODEL_PATH = os.path.join(MODEL_PATH, "vosk-model-small-en-us-0.15")


class DownloadThread(QThread):
    """Worker thread to download the model without freezing the UI"""
    download_progress = pyqtSignal(int)
    download_finished = pyqtSignal(bool, str)  # Success (bool), Message (str)

    def run(self):
        try:
            # 1. Ensure the target directory exists
            os.makedirs(MODEL_PATH, exist_ok=True)

            # 2. Download the file
            self.download_progress.emit(0)
            response = requests.get(MODEL_URL, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with BytesIO() as f_bytes:
                for chunk in response.iter_content(chunk_size=8192):
                    downloaded_size += len(chunk)
                    f_bytes.write(chunk)
                    if total_size > 0:
                        progress = int((downloaded_size / total_size) * 100)
                        self.download_progress.emit(progress)

                self.download_progress.emit(100)

                # 3. Unzip the file
                with zipfile.ZipFile(f_bytes) as z:
                    z.extractall(MODEL_PATH)

            self.download_finished.emit(True, "Models downloaded successfully!")

        except Exception as e:
            self.download_finished.emit(False, f"Error: {e}")


class SetupWizard(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JARVIS Setup")
        self.setGeometry(400, 300, 500, 200)

        # Page 1: Welcome
        self.welcome_page = QWidget()
        welcome_layout = QVBoxLayout()
        welcome_label = QLabel(
            "Welcome to JARVIS Setup.\n\nThis wizard will download the required AI models (approx. 50MB).")
        next_button = QPushButton("Next")
        next_button.clicked.connect(self.start_download)
        welcome_layout.addWidget(welcome_label)
        welcome_layout.addWidget(next_button)
        self.welcome_page.setLayout(welcome_layout)

        # Page 2: Download
        self.download_page = QWidget()
        download_layout = QVBoxLayout()
        self.download_label = QLabel("Downloading models...")
        self.progress_bar = QProgressBar()
        download_layout.addWidget(self.download_label)
        download_layout.addWidget(self.progress_bar)
        self.download_page.setLayout(download_layout)

        # Page 3: Finish
        self.finish_page = QWidget()
        finish_layout = QVBoxLayout()
        finish_label = QLabel("Setup is complete. You can now close this window and start JARVIS.")
        finish_button = QPushButton("Finish")
        finish_button.clicked.connect(self.close)  # Just close the setup wizard
        finish_layout.addWidget(finish_label)
        finish_layout.addWidget(finish_button)
        self.finish_page.setLayout(finish_layout)

        self.addWidget(self.welcome_page)
        self.addWidget(self.download_page)
        self.addWidget(self.finish_page)

        self.download_thread = DownloadThread()
        self.download_thread.download_progress.connect(self.set_progress)
        self.download_thread.download_finished.connect(self.on_download_finished)

    def start_download(self):
        self.setCurrentWidget(self.download_page)
        self.download_thread.start()

    def set_progress(self, value):
        self.progress_bar.setValue(value)

    def on_download_finished(self, success, message):
        if success:
            self.setCurrentWidget(self.finish_page)
        else:
            QMessageBox.critical(self, "Download Failed", message)
            self.setCurrentWidget(self.welcome_page)  # Go back to try again