import os
import sys

def get_chromedriver_path():
    if getattr(sys, 'frozen', False):  # running from .exe
        base_path = sys._MEIPASS
        # Path inside the bundle — don't use ../..
        return os.path.join(base_path, 'DATA', 'JARVIS_DRIVER', 'chromedriver.exe')
    else:
        # Development mode — use relative to script
        base_path = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(base_path, '..', '..', 'DATA', 'JARVIS_DRIVER', 'chromedriver.exe')


# import os
# import sys
#
# def get_chromedriver_path():
#     if getattr(sys, 'frozen', False):  # if running from PyInstaller bundle
#         base_path = sys._MEIPASS
#     else:
#         base_path = os.path.abspath(os.path.dirname(__file__))
#
#     return os.path.join(base_path, '..', '..', 'DATA', 'JARVIS_DRIVER', 'chromedriver.exe')
