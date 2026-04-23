from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
from aeris.ui_laptop.widgets.settings_page import SettingsPage

class SettingsManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.settings_page = SettingsPage(self)
        self.layout.addWidget(self.settings_page)

    def set_settings(self, settings):
        self.settings_page.set_settings(settings)

    def update_google_status(self, connected, email=""):
        self.settings_page.update_google_status(connected, email)

    def set_available_voices(self, voices):
        self.settings_page.set_available_voices(voices)

    def update_install_progress(self, model_name, progress):
        self.settings_page.update_install_progress(model_name, progress)
