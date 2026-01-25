# BACKEND/automations/battery/battery_plug.py
import psutil


def speak_plug_status(speaker):
    battery = psutil.sensors_battery()
    if not battery:
        message = "Charger status unavailable."
        try:
            speaker.speak(message)
        except Exception:
            pass
        return message

    if battery.power_plugged:
        message = "Charger is plugged in."
    else:
        message = "Charger is unplugged."

    try:
        speaker.speak(message)
    except Exception:
        pass
    return message
