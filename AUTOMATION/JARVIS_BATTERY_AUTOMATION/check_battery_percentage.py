import psutil

<<<<<<< HEAD
from FUNCTION.JARVIS_SPEAK.speak import speak
=======
from UTILS.tts_singleton import speak
>>>>>>> a8c9983 (added offline jarvis things and GUI interface)


def battery_percentage():
    battery = psutil.sensors_battery()
    percent = int(battery.percent)
    speak(f"the device is running on {percent}% battery power")
