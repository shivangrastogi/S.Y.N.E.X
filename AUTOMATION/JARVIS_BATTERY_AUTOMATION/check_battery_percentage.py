import psutil

from UTILS.tts_singleton import speak


def battery_percentage():
    battery = psutil.sensors_battery()
    percent = int(battery.percent)
    speak(f"the device is running on {percent}% battery power")
