import os
import subprocess
import webbrowser
import requests
import psutil

class ActionExecutor:
    def __init__(self):
        # App mapping - can be expanded by the user
        self.app_map = {
            "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "visual studio code": "code",
            "vlc": "vlc.exe"
        }

    def execute(self, intent, slots):
        """
        Main entry point for execution.
        """
        if intent == "open_app":
            return self.open_application(slots.get("app_name", "").lower())
        
        elif intent == "close_app":
            return self.close_application(slots.get("app_name", "").lower())
        
        elif intent == "get_weather":
            return self.fetch_weather()
        
        elif intent == "play_music":
            return self.play_music_control()
            
        elif intent == "system_info":
            return self.get_system_status()

        return f"Logic for {intent} is being developed."

    def open_application(self, app_name):
        if not app_name:
            return "App name not specified."
            
        # Clean the app_name: remove common command verbs if user repeated them
        for verb in ["open", "launch", "start", "kholo", "chalu karo", "chalu"]:
            app_name = app_name.replace(verb, "").strip()

        # Search in our map

        app_path = self.app_map.get(app_name)
        
        try:
            if app_path:
                os.startfile(app_path) if os.path.exists(app_path) or "." not in app_path else subprocess.Popen(app_path)
                return f"Opening {app_name} for you."
            else:
                # Try a generic search in case it's not in the map
                os.system(f"start {app_name}")
                return f"Attempting to open {app_name}..."
        except Exception as e:
            return f"Error opening {app_name}: {str(e)}"

    def close_application(self, app_name):
        # Close process using psutil
        closed = False
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    # Ignore processes that Jarvis shouldn't touch
                    if any(x in proc.info['name'].lower() for x in ["crashhandler", "service", "system"]):
                        continue

                    if app_name in proc.info['name'].lower():
                        proc.kill()
                        closed = True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            print(f"Close Error: {str(e)}")
        
        return f"Closed {app_name}." if closed else f"Couldn't find {app_name} running."


    def fetch_weather(self, city="New Delhi"):
        # Placeholder for real API or Scraper
        # You can replace this with your OpenWeatherMap key later
        return f"Mausam in {city} is currently 28 degrees and sunny."

    def get_system_status(self):
        battery = psutil.sensors_battery()
        percent = battery.percent if battery else "Unknown"
        cpu = psutil.cpu_percent()
        return f"System status: Battery is at {percent}% and CPU usage is {cpu}%."

    def play_music_control(self):
        # Simply opens a music site or local player
        webbrowser.open("https://www.youtube.com/results?search_query=lofi+music")
        return "Playing some music on YouTube for you."

if __name__ == "__main__":
    executor = ActionExecutor()
    # Test App Opening
    print(executor.execute("open_app", {"app_name": "notepad"}))
    # Test System Info
    print(executor.execute("system_info", {}))
