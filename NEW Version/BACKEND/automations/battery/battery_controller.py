# BACKEND/automations/battery/battery_controller.py
from BACKEND.automations.battery.battery_monitor import BatteryMonitor
from BACKEND.automations.battery.battery_status import speak_battery_percentage
from BACKEND.automations.battery.battery_plug import speak_plug_status


class BatteryController:
    def __init__(self, speaker):
        self.speaker = speaker
        self.monitor = BatteryMonitor(speaker)
        # Monitoring is started by the main app to avoid duplicate threads

    def handle(self, intent: str):
        try:
            if intent == "check_battery_percentage":
                return speak_battery_percentage(self.speaker)

            if intent == "check_battery_plug":
                return speak_plug_status(self.speaker)

        except Exception:
            return "I faced an issue while checking battery."

        return None
