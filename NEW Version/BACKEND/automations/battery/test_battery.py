# BACKEND/automations/battery/test_battery.py
import time

from BACKEND.core.state.mode_manager import ModeManager
from BACKEND.core.speaker.speech_service import SpeechService

from BACKEND.automations.battery.battery_status import speak_battery_percentage
from BACKEND.automations.battery.battery_plug import speak_plug_status
from BACKEND.automations.battery.battery_monitor import BatteryMonitor


def menu():
    print("\n==============================")
    print("🔋 JARVIS BATTERY TEST MODE")
    print("==============================")
    print("1. Speak battery percentage")
    print("2. Check charger status")
    print("3. Start background battery alerts")
    print("4. Stop background alerts")
    print("5. Exit")
    print("==============================")

def main():
    mode_manager = ModeManager()
    speaker = SpeechService(mode_manager)
    monitor = BatteryMonitor(speaker)

    while True:
        menu()
        choice = input("Enter choice (1-5): ").strip()

        if choice == "1":
            msg = speak_battery_percentage(speaker)
            print(msg)

        elif choice == "2":
            msg = speak_plug_status(speaker)
            print(msg)

        elif choice == "3":
            print("🚨 Battery monitor started")
            monitor.start()

        elif choice == "4":
            monitor.stop()
            print("🛑 Battery monitor stopped")

        elif choice == "5":
            monitor.stop()
            print("👋 Exiting")
            break

        else:
            print("❌ Invalid option")

if __name__ == "__main__":
    main()
