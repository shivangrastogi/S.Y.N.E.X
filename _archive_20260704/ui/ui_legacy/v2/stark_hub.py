from PyQt5.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QVBoxLayout, QLabel, QFrame
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from ui.v2.widgets.sidebar import StarkSidebar
from ui.v2.widgets.arc_reactor import ArcReactorWidget

class StarkHubWindow(QMainWindow):
    """
    A.E.R.I.S v2.0 - Stark Hub Command Center.
    High-Fidelity FUI (Futuristic User Interface) for Desktop.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("A.E.R.I.S Stark Hub")
        self.resize(1200, 800)
        
        # High-Fidelity Glassmorphic Theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #05070a;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLabel#HubTitle {
                color: #00f2ff;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 4px;
                padding-bottom: 20px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Sidebar (FUI Style)
        self.sidebar = StarkSidebar(self)
        self.sidebar.tab_changed.connect(self._switch_tab)
        self.main_layout.addWidget(self.sidebar)

        # 2. Content Container (With Glass Edge)
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border-left: 1px solid rgba(0, 242, 255, 30);
            }
        """)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.content_stack = QStackedWidget()
        self.content_layout.addWidget(self.content_stack)
        self.main_layout.addWidget(self.content_frame)

        # 3. Component Bridge (Voice/State)
        from ui.event_bridge import EventBridge
        self.bridge = EventBridge()
        self.bridge.state_changed.connect(self._on_system_state_changed)
        self.bridge.audio_level.connect(self._on_audio_level)

        # Tab Register
        self._tabs = {} 
        self._switch_tab(0)

    def _switch_tab(self, index):
        if index not in self._tabs:
            self._load_tab(index)
        
        # Smooth fade transition (simplified)
        self.content_stack.setCurrentWidget(self._tabs[index])

    def _load_tab(self, index):
        if index == 0: tab = self._create_home_tab()
        elif index == 1: tab = self._create_automation_tab()
        elif index == 2: tab = self._create_gallery_tab()
        elif index == 3: tab = self._create_settings_tab()
        else: tab = QWidget()
            
        self._tabs[index] = tab
        self.content_stack.addWidget(tab)

    def _create_home_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(40, 40, 40, 40)
        
        title = QLabel("SYSTEM CORE INTERFACE // AERIS_OS.V2")
        title.setObjectName("HubTitle")
        layout.addWidget(title, alignment=Qt.AlignTop | Qt.AlignCenter)
        
        layout.addStretch()
        self.reactor = ArcReactorWidget()
        layout.addWidget(self.reactor, alignment=Qt.AlignCenter)
        layout.addStretch()
        
        # Status Bar
        status_bar = QHBoxLayout()
        for stat in ["CPU: 2.1%", "RAM: 45MB", "NET: STABLE", "AI: IDLE"]:
            lbl = QLabel(stat)
            lbl.setStyleSheet("color: #444; font-size: 10px; font-family: monospace; padding: 10px;")
            status_bar.addWidget(lbl)
        layout.addLayout(status_bar)
        
        return tab

    def _create_automation_tab(self):
        from PyQt5.QtWidgets import QFrame
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(60, 60, 60, 60)
        
        card = QFrame()
        card.setStyleSheet("background-color: #11141a; border: 1px solid #333; border-radius: 15px; padding: 40px;")
        l = QVBoxLayout(card)
        t = QLabel("AUTOMATION ENGINE")
        t.setStyleSheet("color: #00f2ff; font-size: 24px; font-weight: bold;")
        l.addWidget(t)
        l.addWidget(QLabel("Task Scheduling and Background Workflows will appear here in Phase 11.2."))
        
        layout.addWidget(card)
        layout.addStretch()
        return tab

    def _create_gallery_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("IMAGE ASSET REPOSITORY - OPTIMIZING..."), alignment=Qt.AlignCenter)
        return tab

    def _create_settings_tab(self):
        from ui.v2.tabs.settings_tab import SettingsTab
        return SettingsTab()

    def _on_system_state_changed(self, state):
        # Could update status bars or neon accents
        pass

    def _on_audio_level(self, level):
        if hasattr(self, 'reactor') and self.reactor:
            self.reactor.set_intensity(level * 3.5)

    def show_hub(self):
        self.show()
        self.raise_()
        self.activateWindow()
