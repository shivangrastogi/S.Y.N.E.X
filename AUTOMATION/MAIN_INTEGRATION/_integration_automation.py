from AUTOMATION.COMMON_AUTOMATION.common_integration import *
from AUTOMATION.JARVIS_GOOGLE_AUTOMATION.google_integration_main import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_integration_main import *
from AUTOMATION.JARVIS_YOUTUBE_AUTOMATION.integration_main import *

def Automation(text):
    common_cmd(text)   # Handle open/close app commands first
    google_cmd(text)   # Handle browser-specific and website commands
    youtube_cmd(text)  # Handle YouTube-specific commands
    battery_cmd(text)  # Handle battery-related commands
