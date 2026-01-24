# --- BACKEND/CORE/Utils/DataPath.py (The definitive version for PyInstaller) ---
import os
import sys

def _get_base_path():
    """Returns the correct root path based on whether running in PyInstaller or development."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 1. PyInstaller: Path is the temporary extraction folder.
        return sys._MEIPASS
    else:
        # 2. Development: Path is calculated from the script location.
        # Navigates up three levels: Utils -> CORE -> BACKEND -> PROJECT_ROOT
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        return project_root


def get_data_file_path(sub_folder, filename):
    """
    Returns the absolute path to a file within the centralized DATA structure.
    """
    base_root = _get_base_path()

    # Determine the location of the DATA folder based on the mode.
    if getattr(sys, 'frozen', False):
        # In EXE: We will map the contents of BACKEND/DATA to the 'data' folder
        # Path: sys._MEIPASS/data
        data_path_root = os.path.join(base_root, "data")
    else:
        # In Dev: Path: PROJECT_ROOT/BACKEND/DATA
        data_path_root = os.path.join(base_root, "BACKEND", "DATA")

    # Combine: .../data/MODELS/NLU_MODELS/model-best or .../BACKEND/DATA/...
    return os.path.join(data_path_root, sub_folder, filename)

def get_model_path(model_type, model_name):
    # This remains correct, relying on the fixed get_data_file_path
    return os.path.join(get_data_file_path('MODELS', model_type), model_name)