# Path: d:\New folder (2) - JARVIS\backend\automations\system\app_launcher.py
import os
import subprocess
import webbrowser

class AppLauncher:
    def __init__(self):
        # App name to system command/executable map
        self.app_map = {
            "chrome": "chrome",
            "edge": "msedge",
            "browser": "msedge",
            "vs code": "code",
            "vscode": "code",
            "notepad": "notepad",
            "calculator": "calc",
            "settings": "start ms-settings:",
            "terminal": "wt",
            "cmd": "cmd",
            "powershell": "powershell",
            "spotify": "spotify",
            "file explorer": "explorer",
            "explorer": "explorer",
        }

    def launch(self, app_name: str) -> bool:
        """Launch an application by name"""
        app_name = app_name.lower().strip()
        
        # 1. Check if it's a URL first
        if "." in app_name and " " not in app_name:
            # If it's something like "google.com", let the browser handle it
            return False 

        # 2. Check the app map
        cmd = self.app_map.get(app_name)
        if not cmd:
            # Try the name itself if it's not in the map
            cmd = app_name

        try:
            print(f"[AppLauncher] Attempting to launch: {cmd}")
            if cmd.startswith("start "):
                # Use shell=True for 'start' commands
                subprocess.Popen(cmd, shell=True)
            elif hasattr(os, 'startfile'):
                # Try simple startfile first (works for most registered apps on Windows)
                os.startfile(cmd)
            else:
                # Fallback for non-windows or missing startfile
                subprocess.Popen(cmd, shell=True)
            return True
        except Exception as e:
            print(f"[AppLauncher] Failed to launch {cmd}: {e}")
            return False

    def close(self, app_name: str) -> bool:
        """Close the MOST RECENT instance of an application (LIFO)"""
        import psutil
        app_name = app_name.lower().strip()
        target_name = self.app_map.get(app_name, app_name)
        
        # Ensure it has .exe for comparison if needed
        if not target_name.endswith(".exe"):
            search_name = target_name + ".exe"
        else:
            search_name = target_name

        try:
            print(f"[AppLauncher] Searching for latest instance of: {search_name}")
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                try:
                    # Check both with and without .exe
                    pinfo = proc.info
                    name = pinfo['name'].lower()
                    if name == search_name.lower() or name == target_name.lower():
                        processes.append(pinfo)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not processes:
                return False
                
            # Sort by create_time descending to get LIFO
            processes.sort(key=lambda x: x['create_time'], reverse=True)
            latest = processes[0]
            
            print(f"[AppLauncher] Killing LIFO instance (PID {latest['pid']})")
            p = psutil.Process(latest['pid'])
            p.terminate() 
            return True
            
        except Exception as e:
            print(f"[AppLauncher] LIFO close failed: {e}")
            return False

