# BACKEND/AUTOMATION/Modules/BatteryAutomation.py

import time
import random
import threading
import psutil
from CORE.TTS_Control import speak
from DATA.JARVIS_DLG_DATASET.DLG import low_b, last_low, full_battery, plug_in, plug_out


class BatteryAutomation(threading.Thread):
    def __init__(self, check_interval=300):
        super().__init__(daemon=True)
        self.check_interval = check_interval
        self.running = True
        self.last_level = None
        self.last_plug_state = None

    def stop(self):
        self.running = False

    def run(self):
        print("🔋 Battery Automation Started")

        while self.running:
            self._check_battery()
            self._check_plug_state()
            time.sleep(self.check_interval)

    def _check_battery(self):
        battery = psutil.sensors_battery()
        if not battery:
            return

        percent = int(battery.percent)

        if percent < 10 and self.last_level != "critical":
            speak(random.choice(last_low), interrupt=True)
            self.last_level = "critical"

        elif percent < 30 and self.last_level != "low":
            speak(random.choice(low_b), interrupt=True)
            self.last_level = "low"

        elif percent == 100 and self.last_level != "full":
            speak(random.choice(full_battery), interrupt=True)
            self.last_level = "full"

        elif percent >= 30:
            self.last_level = None  # reset

    def _check_plug_state(self):
        battery = psutil.sensors_battery()
        if not battery:
            return

        if self.last_plug_state is None:
            self.last_plug_state = battery.power_plugged
            return

        if battery.power_plugged != self.last_plug_state:
            if battery.power_plugged:
                speak(random.choice(plug_in), interrupt=True)
            else:
                speak(random.choice(plug_out), interrupt=True)

            self.last_plug_state = battery.power_plugged


# --- Public helper functions for ActionRouter ---

def get_battery_percentage():
    battery = psutil.sensors_battery()
    if not battery:
        return "Sir, I cannot detect battery status on this device."
    return f"The device is running on {int(battery.percent)} percent battery power, Sir."
