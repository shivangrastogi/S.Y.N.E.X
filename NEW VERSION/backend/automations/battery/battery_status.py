# BACKEND/automations/battery/battery_status.py
import psutil


def speak_battery_percentage(speaker):
    battery = psutil.sensors_battery()
    if not battery:
        message = "Battery information is unavailable."
        try:
            speaker.speak(message)
        except Exception:
            pass
        return message

    percent = int(battery.percent)
    message = f"Battery is at {percent}%."
    try:
        speaker.speak(message)
    except Exception:
        pass
    return message
