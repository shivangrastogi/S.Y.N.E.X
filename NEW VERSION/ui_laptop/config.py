# Application Configuration
import os

# Project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS_PATH = os.path.join(PROJECT_ROOT, 'assets')

# Image paths
LOGO_PATH = os.path.join(ASSETS_PATH, 'aeris_logo.png')
MINIMIZE_ICON_PATH = os.path.join(ASSETS_PATH, 'minimize_logo.png')
MAXIMIZE_ICON_PATH = os.path.join(ASSETS_PATH, 'maximize_logo.png')
CLOSE_ICON_PATH = os.path.join(ASSETS_PATH, 'close_logo.png')

# Image dimensions (original)
LOGO_WIDTH = 1262
LOGO_HEIGHT = 332

BUTTON_WIDTH = 381  # minimize width
BUTTON_HEIGHT = 291  # minimize height

# Title bar configuration
TITLE_BAR_HEIGHT = 50
BUTTON_SIZE = 35  # Size when scaled down for title bar
