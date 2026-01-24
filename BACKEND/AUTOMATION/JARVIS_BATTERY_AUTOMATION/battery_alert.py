# battery_alert
import random
import time
import psutil
from DATA.JARVIS_DLG_DATASET.DLG import low_b, last_low, full_battery
from UTILS.tts_singleton import speak

last_level = None

last_level = None

def battery_alert():
    global last_level
    while True:
        battery = psutil.sensors_battery()
        percent = int(battery.percent)

        if percent < 10 and last_level != "critical":
            speak(random.choice(last_low))
            last_level = "critical"
        elif percent < 30 and last_level != "low":
            speak(random.choice(low_b))
            last_level = "low"
        elif percent == 100 and last_level != "full":
            speak(random.choice(full_battery))
            last_level = "full"
        elif 30 <= percent < 100:
            last_level = None  # reset alert tracking

        time.sleep(300)


def battery_alert1():
        battery = psutil.sensors_battery()
        percent = int(battery.percent)

        if percent < 30:
            random_low = random.choice(low_b)
            speak(random_low)

        elif percent < 10:
            random_low = random.choice(last_low)
            speak(random_low)

        elif percent == 100:
            random_low = random.choice(full_battery)
            speak(random_low)
        else:
            speak("sir,your battery is in perfect battery level")
