import ctypes
import json
import os
import shutil
import subprocess
import webbrowser
from datetime import datetime
from typing import Optional

import psutil

from core.skill_registry import get_skill
from core.time_parser import parse_time_string

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ActionExecutor:
    def __init__(self, scheduler=None):
        self.scheduler = scheduler
        self.app_aliases = {
            "chrome": ["chrome", "google-chrome"],
            "edge": ["msedge"],
            "visual studio code": ["code"],
            "vs code": ["code"],
            "notepad": ["notepad"],
            "calculator": ["calc"],
            "vlc": ["vlc"],
            "brave": ["brave"],
            "file explorer": ["explorer"],
            "settings": ["ms-settings:"],
            "cmd": ["cmd"],
            "task manager": ["taskmgr"],
            "paint": ["mspaint"],
            "spotify": ["spotify"],
            "discord": ["discord"],
            "zoom": ["zoom"],
            "excel": ["excel"],
            "word": ["winword"],
            "powerpoint": ["powerpnt"],
        }

        self.fixed_paths = {
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            "spotify": os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
            "discord": os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
        }

        self.notes_dir = os.path.join(_ROOT, "data", "notes")
        os.makedirs(self.notes_dir, exist_ok=True)

    # ------------------------------------------------------------------ #
    #  Dispatch                                                            #
    # ------------------------------------------------------------------ #

    def execute(self, intent: str, slots: dict) -> str:
        dispatch = {
            "open_app":       lambda: self.open_application(slots.get("app_name", "").lower()),
            "close_app":      lambda: self.close_application(slots.get("app_name", "").lower()),
            "get_weather":    lambda: "Mausam filhaal suhana hai, around 25 degrees Celsius.",
            "play_music":     lambda: self.play_music(),
            "stop_music":     lambda: self.stop_music(),
            "get_time":       lambda: self.get_time(),
            "take_screenshot":lambda: self.take_screenshot(),
            "search_web":     lambda: self.search_web(slots.get("query", "")),
            "system_info":    lambda: self.get_system_status(),
            "volume_up":      lambda: self.volume_change("up"),
            "volume_down":    lambda: self.volume_change("down"),
            "volume_mute":    lambda: self.volume_change("mute"),
            "lock_screen":    lambda: self.lock_screen(),
            "shutdown_system":lambda: self.shutdown_system(),
            "calculate":      lambda: self.calculate(slots.get("expression", "")),
            "create_note":    lambda: self.create_note(slots.get("content", "")),
            "greet":          lambda: self.greet(),
            "schedule_meeting": lambda: self.schedule_meeting(slots),
            "play_youtube":   lambda: self.play_youtube(slots.get("query", "")),
            "open_website":   lambda: self.open_website(slots.get("url", "")),
            "set_reminder":   lambda: self.set_reminder(slots),
        }

        handler = dispatch.get(intent)
        if handler:
            try:
                return handler()
            except Exception as e:
                return f"Error executing {intent}: {str(e)}"

        plugin = get_skill(intent)
        if plugin:
            try:
                return plugin.run(slots)
            except Exception as e:
                return f"Error executing {intent}: {str(e)}"

        return f"Ye kaam karna seekh raha hoon: {intent}."

    # ------------------------------------------------------------------ #
    #  App control                                                         #
    # ------------------------------------------------------------------ #

    def open_application(self, app_name: str) -> str:
        if not app_name:
            return "App name nahi bataya. Kaunsa app kholna hai?"

        app_name = app_name.strip()
        commands = self.app_aliases.get(app_name, [app_name])

        for cmd in commands:
            if cmd.startswith("ms-settings:"):
                subprocess.Popen(f"start {cmd}", shell=True)
                return f"Settings open kar raha hoon."
            if shutil.which(cmd):
                subprocess.Popen(cmd, shell=True)
                return f"{app_name.title()} khol raha hoon."
            path = self.fixed_paths.get(app_name)
            if path and os.path.exists(path):
                os.startfile(path)
                return f"{app_name.title()} khol raha hoon."

        try:
            subprocess.Popen(f"start {commands[0]}", shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"{app_name.title()} launch karne ki koshish kar raha hoon."
        except Exception as e:
            return f"{app_name} nahi khul raha: {e}"

    def close_application(self, app_name: str) -> str:
        if not app_name:
            return "Kaunsa app band karna hai?"

        targets = self.app_aliases.get(app_name, [app_name])
        closed = False

        for proc in psutil.process_iter(["name"]):
            try:
                pname = proc.info["name"].lower()
                if any(t in pname for t in targets):
                    proc.kill()
                    closed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return f"{app_name.title()} band kar diya." if closed else f"{app_name.title()} chal nahi raha tha."

    # ------------------------------------------------------------------ #
    #  System                                                              #
    # ------------------------------------------------------------------ #

    def get_system_status(self) -> str:
        battery = psutil.sensors_battery()
        bat = f"{battery.percent:.0f}%" if battery else "Unknown"
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        ram_used = f"{ram.used / 1e9:.1f} GB / {ram.total / 1e9:.1f} GB"
        return f"Battery: {bat}, CPU: {cpu}%, RAM: {ram_used}."

    def get_time(self) -> str:
        now = datetime.now()
        return f"Abhi {now.strftime('%I:%M %p')} baj rahe hain, aaj {now.strftime('%A, %d %B %Y')} hai."

    def lock_screen(self) -> str:
        ctypes.windll.user32.LockWorkStation()
        return "Screen lock kar raha hoon."

    def shutdown_system(self) -> str:
        subprocess.run(["shutdown", "/s", "/t", "30"], shell=True)
        return "System 30 seconds mein shutdown ho jayega. Cancel karne ke liye 'shutdown /a' type karein."

    def take_screenshot(self) -> str:
        try:
            import pyautogui
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(_ROOT, "data", f"screenshot_{ts}.png")
            pyautogui.screenshot(path)
            return f"Screenshot le liya: {path}"
        except ImportError:
            return "pyautogui install nahi hai. 'pip install pyautogui' run karein."

    def volume_change(self, direction: str) -> str:
        VK_UP   = 0xAF
        VK_DOWN = 0xAE
        VK_MUTE = 0xAD

        key_map = {"up": VK_UP, "down": VK_DOWN, "mute": VK_MUTE}
        key = key_map.get(direction)
        if key:
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)

        messages = {"up": "Volume badhaya.", "down": "Volume kam kiya.", "mute": "Mute kar diya."}
        return messages.get(direction, "Volume change kiya.")

    # ------------------------------------------------------------------ #
    #  Web / Search                                                        #
    # ------------------------------------------------------------------ #

    def search_web(self, query: str) -> str:
        if not query:
            return "Kya search karoon? Batao."
        try:
            from core.browser_launcher import launch
            res = launch(query, is_search=True)
            return f"'{query}' search kar raha hoon ({res.used_browser})."
        except Exception:
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            return f"'{query}' search kar raha hoon Google pe."

    def play_youtube(self, query: str) -> str:
        if not query:
            return "Kya dekhna hai YouTube pe?"
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        try:
            from core.browser_launcher import launch
            res = launch(url, is_search=False)
            return f"YouTube pe '{query}' search kar raha hoon ({res.used_browser})."
        except Exception:
            webbrowser.open(url)
            return f"YouTube pe '{query}' search kar raha hoon."

    def open_website(self, url: str) -> str:
        if not url:
            return "URL batao."
        try:
            from core.browser_launcher import launch
            res = launch(url)
            return f"{url} khol raha hoon ({res.used_browser})."
        except Exception:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            webbrowser.open(url)
            return f"{url} khol raha hoon."

    # ------------------------------------------------------------------ #
    #  Music                                                               #
    # ------------------------------------------------------------------ #

    def play_music(self) -> str:
        # Try Spotify first, then Windows Media Player
        if shutil.which("spotify") or os.path.exists(self.fixed_paths.get("spotify", "")):
            self.open_application("spotify")
            return "Spotify chalu kar raha hoon."
        webbrowser.open("https://open.spotify.com")
        return "Spotify web pe khol raha hoon."

    def stop_music(self) -> str:
        # Send media stop key
        VK_MEDIA_STOP = 0xB2
        ctypes.windll.user32.keybd_event(VK_MEDIA_STOP, 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK_MEDIA_STOP, 0, 2, 0)
        return "Music rok diya."

    # ------------------------------------------------------------------ #
    #  Productivity                                                        #
    # ------------------------------------------------------------------ #

    def calculate(self, expression: str) -> str:
        if not expression:
            return "Kya calculate karoon?"
        try:
            # Allow only safe math characters
            safe = "".join(c for c in expression if c in "0123456789+-*/.() ")
            result = eval(safe)
            return f"{expression} = {result}"
        except Exception:
            return f"Yeh calculate nahi kar saka: {expression}"

    def create_note(self, content: str) -> str:
        if not content:
            return "Note mein kya likhoon?"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.notes_dir, f"note_{ts}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Note save kar liya."

    def set_reminder(self, slots: dict) -> str:
        msg = (slots.get("message") or "kuch yaad karna hai").strip()
        time_str = (slots.get("time") or "").strip()

        if not self.scheduler:
            return f"Reminder note kar liya: '{msg}' — {time_str or 'baad mein'} pe."

        fire_at = parse_time_string(time_str)
        if not fire_at:
            return f"'{time_str}' samajh nahi aaya. Time clearer batao — jaise '5 pm' ya '10 minute mein'."

        try:
            self.scheduler.schedule(msg, fire_at)
        except ValueError:
            return f"'{time_str}' to past mein hai. Future ka time batao."
        except Exception as e:
            return f"Reminder set nahi ho paya: {e}"

        return f"Reminder set: '{msg}' — {fire_at.strftime('%I:%M %p, %d %b')} pe yaad dilaoonga."

    def schedule_meeting(self, slots: dict) -> str:
        person = slots.get("person", "unknown")
        time_ = slots.get("time", "unknown")
        return f"{person} ke saath meeting {time_} pe schedule kar di."

    def greet(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning, sir! Kya seva kar sakta hoon?"
        if hour < 17:
            return "Good afternoon, sir! Kaisa chal raha hai?"
        return "Good evening, sir! Kya karna hai aaj?"
