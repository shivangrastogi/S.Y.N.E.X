# --- BACKEND/CORE/Utils/resource_path.py (Updated) ---

import os
import sys


def resource_path(relative_path):
    """
    Get absolute path to resource, works for development (source)
    and for PyInstaller (bundled executable).
    """
    if hasattr(sys, '_MEIPASS'):
        # 1. PyInstaller (Bundled Executable) Path:
        # Assets are extracted to the root of the temporary _MEIPASS folder.
        base_path = sys._MEIPASS
    else:
        # 2. Development (Local Run) Path Fix:

        # We need to calculate the path back to the project root and then forward to the assets.
        # Current location of this script: /BACKEND/CORE/Utils/
        # Target location of the base asset folder: /DESKTOP_APP/GUI/

        # Determine the location of the running script (resource_path.py)
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Navigate UP three levels to the Project Root: Utils -> CORE -> BACKEND -> PROJECT_ROOT
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))

        # Navigate DOWN into the GUI folder containing the assets folder
        # Path structure: PROJECT_ROOT/DESKTOP_APP/GUI/
        base_path = os.path.join(project_root, "DESKTOP_APP", "GUI")

    # Combine the calculated base path with the requested relative path (e.g., "assets/microphone.png")
    return os.path.join(base_path, relative_path)