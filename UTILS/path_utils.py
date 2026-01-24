# FILE: UTILS/path_utils.py
import os
import platform

if platform.system() == "Windows":
    USER_DATA = os.path.join(os.getenv("APPDATA"), "Jarvis")
else:
    USER_DATA = os.path.join(os.path.expanduser("~"), ".jarvis")

os.makedirs(USER_DATA, exist_ok=True)

def TD(fname): return os.path.join(USER_DATA, fname)
