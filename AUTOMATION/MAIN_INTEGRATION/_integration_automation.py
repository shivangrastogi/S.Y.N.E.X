from AUTOMATION.COMMON_AUTOMATION.common_integration import *
from AUTOMATION.JARVIS_GOOGLE_AUTOMATION.google_integration_main import *
from AUTOMATION.JARVIS_BATTERY_AUTOMATION.battery_integration_main import *
from AUTOMATION.JARVIS_YOUTUBE_AUTOMATION.integration_main import *

def Automation(text):
    youtube_cmd(text)  # This will run first
    battery_cmd(text)  # This will run second
    common_cmd(text)  # This will run third
    google_cmd(text)  # This will run last

