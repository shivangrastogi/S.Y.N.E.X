# File: d:/New folder (2)/New-Jarvis-2.0/aeris/ui/dashboard/main_dashboard.py
from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget
from PyQt5.QtCore import Qt
from ui.dashboard.widgets.sidebar import Sidebar
from ui.dashboard.tabs.home_tab import HomeTab
from ui.dashboard.tabs.automation_tab import AutomationTab
from ui.dashboard.tabs.gallery_tab import GalleryTab
from ui.dashboard.tabs.settings_tab import SettingsTab

class DashboardWindow(QMainWindow):
    """
    Main A.E.R.I.S Management Dashboard.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("A.E.R.I.S Management Dashboard")
        self.resize(1100, 750)
        
        # Dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #111214;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel { color: #e0e0e0; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Sidebar
        self.sidebar = Sidebar(self)
        self.main_layout.addWidget(self.sidebar)

        # 2. Content Area (Stacked Widget)
        self.content_stack = QStackedWidget()
        self.main_layout.addWidget(self.content_stack)

        # Initialize Tabs
        self.home_tab = HomeTab()
        self.automation_tab = AutomationTab()
        self.gallery_tab = GalleryTab()
        self.settings_tab = SettingsTab()

        self.content_stack.addWidget(self.home_tab)       # Index 0
        self.content_stack.addWidget(self.automation_tab) # Index 1
        self.content_stack.addWidget(self.gallery_tab)    # Index 2
        self.content_stack.addWidget(self.settings_tab)   # Index 3

        # Connect Sidebar
        self.sidebar.tab_changed.connect(self.content_stack.setCurrentIndex)

    def show_dashboard(self):
        self.show()
        self.raise_()
        self.activateWindow()
