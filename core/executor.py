import ctypes
import json
import logging
import os
import shutil
import subprocess
import webbrowser
from datetime import datetime
from typing import Optional

import psutil

from core.skill_registry import get_skill
from core.time_parser import parse_time_string

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ActionExecutor:
    def __init__(self, scheduler=None):
        self.scheduler = scheduler
        # Command list per canonical app name. Each list is tried in order
        # by _launch_command — the first that resolves wins. Mixed forms:
        #   * plain exe (resolved via shutil.which against PATH)
        #   * Windows URI protocols (ms-settings:, ms-photos:, microsoft.windows.camera:)
        #   * "shell:appsFolder\<AUMID>!App" tokens for UWP apps with no protocol
        self.app_aliases = {
            "chrome":              ["chrome", "google-chrome"],
            "edge":                ["msedge", "microsoft-edge:"],
            "brave":               ["brave"],
            "firefox":             ["firefox"],
            "visual studio code":  ["code"],
            "vs code":             ["code"],
            "notepad":             ["notepad"],
            "calculator":          ["calc", "ms-calculator:"],
            "vlc":                 ["vlc"],
            "file explorer":       ["explorer"],
            "settings":            ["ms-settings:"],
            "control panel":       ["control"],
            "cmd":                 ["cmd"],
            "powershell":          ["powershell"],
            "windows terminal":    ["wt"],
            "task manager":        ["taskmgr"],
            "paint":               ["mspaint"],
            "spotify":             ["spotify"],
            "discord":             ["discord"],
            "zoom":                ["zoom"],
            "excel":               ["excel"],
            "word":                ["winword"],
            "powerpoint":          ["powerpnt"],
            "outlook":             ["outlook"],
            "mail":                ["outlookmail:"],
            "photos":              ["ms-photos:"],
            "camera":              ["microsoft.windows.camera:"],
            "store":               ["ms-windows-store:"],
            "snipping tool":       ["ms-screenclip:", "snippingtool"],
            "magnifier":           ["magnify"],
            "sticky notes":        ["shell:appsFolder\\Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe!App"],
            "clock":               ["ms-clock:"],
            "calendar":            ["outlookcal:"],
            "whatsapp":            ["shell:appsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App", "whatsapp"],
            "teams":               ["ms-teams:"],
            "telegram":            ["telegram"],
            "obs":                 ["obs64", "obs"],
            "steam":               ["steam"],
            "python":              ["idle", "python"],
            "registry editor":     ["regedit"],
            "device manager":      ["devmgmt.msc"],
            "disk management":     ["diskmgmt.msc"],
            "system info":         ["msinfo32"],
            "performance monitor": ["perfmon"],
            "event viewer":        ["eventvwr.msc"],
            "services":            ["services.msc"],
            "git bash":            [r"C:\Program Files\Git\git-bash.exe", "git-bash"],
            "github desktop":      ["github"],
            "android studio":      ["studio64"],
            "intellij":            ["idea64"],
            "pycharm":             ["pycharm64"],
            "blender":             ["blender"],
            "figma":               ["figma"],
            "postman":             ["postman"],
        }

        # Hard-coded install paths to try before falling back to PATH/protocol.
        # Useful for browser binaries that often aren't on PATH.
        self.fixed_paths = {
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "edge":   r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "brave":  r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
            "spotify": os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
            "discord": os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
            "telegram": os.path.expandvars(r"%APPDATA%\Telegram Desktop\Telegram.exe"),
            "github desktop": os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\GitHubDesktop.exe"),
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
            # Route plugin skills through the breaker so a stuck handler
            # can't wedge the brain thread, and 3 consecutive failures
            # auto-disable the skill for 60s instead of nagging the user.
            from core.skill_breaker import call as _breaker_call
            result = _breaker_call(intent, plugin.run, slots)
            if result.ok:
                return result.value
            # Surface a clean, user-readable message; the structured
            # error is in result.error and gets logged below.
            log.warning("[executor] skill %s failed: %s (elapsed=%dms, "
                        "timeout=%s, shorted=%s)",
                        intent, result.error, result.elapsed_ms,
                        result.timed_out, result.short_circuited)
            if result.short_circuited:
                return result.error
            if result.timed_out:
                return f"'{intent}' is taking too long — try again in a moment."
            return f"Error executing {intent}: {result.error}"

        return f"Ye kaam karna seekh raha hoon: {intent}."

    # ------------------------------------------------------------------ #
    #  App control                                                         #
    # ------------------------------------------------------------------ #

    def open_application(self, app_name: str) -> str:
        if not app_name:
            return "App name nahi bataya. Kaunsa app kholna hai?"

        app_name = app_name.strip().lower()
        commands = self.app_aliases.get(app_name, [app_name])

        # Try fixed install path first — most reliable for browsers /
        # third-party apps that aren't on PATH.
        path = self.fixed_paths.get(app_name)
        if path and os.path.exists(path):
            try:
                os.startfile(path)
                return f"{app_name.title()} khol raha hoon."
            except Exception as e:
                log.debug("[executor] fixed-path launch failed for %s: %s",
                          app_name, e)

        # Now try each command in priority order. Three command shapes:
        #   1. URI protocols (ms-settings:, microsoft.windows.camera:,
        #      ms-photos:, etc.) — launched via `start` so Shell resolves them.
        #   2. UWP `shell:appsFolder\...!App` tokens — launched via explorer.
        #   3. Plain exe — resolved through PATH first, then `start <name>`
        #      as a final hail-mary (Windows protocol handlers, App Paths
        #      registry, etc. may still know it).
        for cmd in commands:
            try:
                if ":" in cmd and not cmd.lower().startswith("c:"):
                    # URI protocol — let the shell route it.
                    subprocess.Popen(f'start "" "{cmd}"', shell=True,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return f"{app_name.title()} khol raha hoon."
                if cmd.lower().startswith("shell:"):
                    subprocess.Popen(f'explorer.exe "{cmd}"', shell=True,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return f"{app_name.title()} khol raha hoon."
                if shutil.which(cmd):
                    subprocess.Popen(cmd, shell=True,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return f"{app_name.title()} khol raha hoon."
                # Direct path that may not exist on PATH but exists on disk.
                if os.path.isabs(cmd) and os.path.exists(cmd):
                    os.startfile(cmd)
                    return f"{app_name.title()} khol raha hoon."
            except Exception as e:
                log.debug("[executor] command %r failed for %s: %s",
                          cmd, app_name, e)

        # Last-ditch: `start <whatever>` — Windows may resolve via
        # App Paths registry or known protocol handlers.
        try:
            subprocess.Popen(f'start "" "{commands[0]}"', shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return f"{app_name.title()} launch karne ki koshish kar raha hoon."
        except Exception as e:
            return f"{app_name} nahi khul raha: {e}"

    def close_application(self, app_name: str) -> str:
        """Close an app GRACEFULLY — WM_CLOSE to its windows first.

        Previously this went straight to ``proc.kill()``: a force-kill
        that destroys unsaved work with no save prompt (a user lost an
        editing session to exactly this). WM_CLOSE is what clicking the
        window's ✕ does — apps get their "save changes?" dialog. Only if
        the process has no windows at all (background/service style) do
        we fall back to terminate(), and never to kill().
        """
        if not app_name:
            return "Kaunsa app band karna hai?"

        targets = self.app_aliases.get(app_name, [app_name])
        pids: set[int] = set()
        for proc in psutil.process_iter(["name"]):
            try:
                pname = proc.info["name"].lower()
                if any(t in pname for t in targets):
                    pids.add(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if not pids:
            return f"{app_name.title()} chal nahi raha tha."

        # Pass 1 — polite: WM_CLOSE every top-level window of the target
        # processes (triggers the app's own save-confirmation flow).
        windows_closed = 0
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            WM_CLOSE = 0x0010
            hits: list[int] = []

            @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            def _enum(hwnd, _l):
                if user32.IsWindowVisible(hwnd):
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in pids:
                        hits.append(hwnd)
                return True

            user32.EnumWindows(_enum, 0)
            for hwnd in hits:
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                windows_closed += 1
        except Exception:
            pass

        if windows_closed:
            return (f"{app_name.title()} ko band hone ko keh diya "
                    f"({windows_closed} window). Agar unsaved kaam hai to "
                    f"save prompt aayega — force karna ho to "
                    f"'kill process {app_name}' bolo.")

        # Pass 2 — windowless process: terminate() (still catchable by the
        # app, unlike kill()). Explicit force-kill stays behind the clearly
        # named kill_process skill.
        stopped = 0
        for pid in pids:
            try:
                psutil.Process(pid).terminate()
                stopped += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if stopped:
            return f"{app_name.title()} band kar diya."
        return (f"{app_name.title()} band nahi hua — "
                f"'kill process {app_name}' se force kar sakte ho.")

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
        result = self._eval_math(expression)
        if result is None:
            return f"Yeh calculate nahi kar saka: {expression}"
        # Trim a clean float (49.0 → 49), keep real decimals.
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        elif isinstance(result, float):
            result = round(result, 6)
        return f"{expression.strip()} = {result}"

    def _eval_math(self, text: str):
        """Evaluate an arithmetic expression, understanding Hinglish/English word
        operators (plus, minus, into, times, divided by, guna, ka … percent, ki
        power …) — including the Hinglish word-order where the operator trails
        the operands ('45 aur 55 add karo'). Returns a number or None."""
        import re
        t = " " + (text or "").lower() + " "
        nums = re.findall(r"\d+(?:\.\d+)?", t)
        # Detect the operator anywhere in the phrase (word OR symbol).
        if re.search(r"percent|%", t):
            op = "%"
        elif re.search(r"\bpower\b|to the power|\bghaat\b|\*\*", t):
            op = "**"
        elif re.search(r"\bdivid|\bbhag\b|/", t):
            op = "/"
        elif re.search(r"\bmultipl|\btimes\b|\binto\b|\bguna\b|\*|\bx\b", t):
            op = "*"
        elif re.search(r"\bplus\b|\badd|\bjod|\bsum\b|\+", t):
            op = "+"
        elif re.search(r"\bminus\b|\bsubtract|\bghatao\b|\bless\b| - ", t):
            op = "-"
        else:
            op = None
        # Two-operand direct path — robust to operator position.
        if op and len(nums) == 2:
            a, b = float(nums[0]), float(nums[1])
            try:
                if op == "%":  return a * b / 100.0
                if op == "**": return a ** b
                if op == "/":  return a / b if b else None
                if op == "*":  return a * b
                if op == "+":  return a + b
                if op == "-":  return a - b
            except Exception:
                return None
        # Fallback: a fully symbolic expression ("2 + 3 * 4", "(5+1)/2").
        safe = "".join(c for c in (text or "") if c in "0123456789+-*/.() ").strip()
        if safe and any(c.isdigit() for c in safe):
            try:
                return eval(safe, {"__builtins__": {}}, {})
            except Exception:
                return None
        return None

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
            base, hint = "Good morning, sir! Kya seva kar sakta hoon?", "morning"
        elif hour < 17:
            base, hint = "Good afternoon, sir! Kaisa chal raha hai?", "afternoon"
        else:
            base, hint = "Good evening, sir! Kya karna hai aaj?", "evening"
        try:
            from core.response_enricher import enriched_reply
            return enriched_reply("greeting", base, hint=hint)
        except Exception:
            return base
