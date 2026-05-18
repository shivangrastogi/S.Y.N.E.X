"""System-info + network-info + power-action skills.

Three groups bundled in one file because they all share the same psutil/
ctypes/subprocess footprint and grouping them keeps the skills/ folder
tidy.

system_info
-----------
* ``system_stats`` — CPU / RAM / disk / uptime snapshot
* ``cpu_info``     — model, core count, current frequency

network_info
------------
* ``network_status`` — IP, WiFi SSID, link speed, public IP (cached)
* ``ping`` — round-trip to a host (default 8.8.8.8)

power_actions
-------------
* ``lock_screen``    — Win+L equivalent (LockWorkStation)
* ``sleep_pc``       — SetSuspendState (S3)
* ``shutdown_pc``    — explicit confirm with delay
* ``cancel_shutdown`` — abort the scheduled shutdown
"""
from __future__ import annotations

import logging
import os
import re
import socket
import subprocess
import sys
import time
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════════╗
# ║  system_info                                                    ║
# ╚══════════════════════════════════════════════════════════════════╝

def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _uptime() -> str:
    try:
        import psutil
        secs = int(time.time() - psutil.boot_time())
    except Exception:
        return "—"
    days, secs = divmod(secs, 86400)
    hrs, secs = divmod(secs, 3600)
    mins = secs // 60
    parts = []
    if days: parts.append(f"{days}d")
    if hrs:  parts.append(f"{hrs}h")
    parts.append(f"{mins}m")
    return " ".join(parts)


@skill(
    name="system_stats",
    description="Snapshot of CPU, RAM, disk, uptime",
    patterns=[
        "system stats", "system status", "system info", "pc stats",
        "computer ka status", "ram usage", "cpu usage", "kitna ram use ho raha hai",
        "disk space", "free space", "uptime",
    ],
)
def system_stats(_slots: dict) -> str:
    try:
        import psutil
    except ImportError:
        return "psutil install nahi hai."
    cpu = psutil.cpu_percent(interval=0.4)
    vm = psutil.virtual_memory()
    du = psutil.disk_usage(os.environ.get("SystemDrive", "C:") + os.sep
                           if sys.platform == "win32" else "/")
    return (
        f"CPU: {cpu:.0f}% · "
        f"RAM: {_human_bytes(vm.used)} / {_human_bytes(vm.total)} ({vm.percent:.0f}%) · "
        f"Disk: {_human_bytes(du.free)} free of {_human_bytes(du.total)} · "
        f"Uptime: {_uptime()}"
    )


@skill(
    name="cpu_info",
    description="CPU model, core count, current frequency",
    patterns=[
        "cpu info", "kaun sa processor", "what cpu", "processor model",
        "cpu kya hai", "cores kitne hain",
    ],
)
def cpu_info(_slots: dict) -> str:
    try:
        import psutil
    except ImportError:
        return "psutil install nahi hai."
    cores_p = psutil.cpu_count(logical=False) or 0
    cores_l = psutil.cpu_count(logical=True) or 0
    freq = psutil.cpu_freq()
    freq_str = f"{freq.current:.0f} MHz" if freq else "—"
    model = ""
    if sys.platform == "win32":
        try:
            import platform
            model = platform.processor() or ""
        except Exception:
            pass
    return f"CPU: {model or 'unknown'} · {cores_p}P / {cores_l}L cores · {freq_str}"


# ╔══════════════════════════════════════════════════════════════════╗
# ║  network_info                                                   ║
# ╚══════════════════════════════════════════════════════════════════╝

def _local_ip() -> str:
    """Best local IP — the one the kernel would pick to talk to 8.8.8.8."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "—"


def _wifi_ssid() -> str:
    if sys.platform != "win32":
        return "—"
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=3,
        )
        for line in out.stdout.splitlines():
            ln = line.strip()
            if ln.lower().startswith("ssid") and not ln.lower().startswith("bssid"):
                return ln.split(":", 1)[1].strip() or "—"
    except Exception:
        return "—"
    return "—"


_PUBLIC_IP_CACHE = {"value": None, "ts": 0.0}


def _public_ip(cache_s: float = 300.0) -> str:
    if (time.monotonic() - _PUBLIC_IP_CACHE["ts"]) < cache_s and _PUBLIC_IP_CACHE["value"]:
        return _PUBLIC_IP_CACHE["value"]
    try:
        import urllib.request
        with urllib.request.urlopen("https://api.ipify.org", timeout=2.5) as r:
            ip = r.read().decode("ascii", "replace").strip()
        if re.match(r"^[\d.]+$", ip):
            _PUBLIC_IP_CACHE.update({"value": ip, "ts": time.monotonic()})
            return ip
    except Exception:
        pass
    return "—"


@skill(
    name="network_status",
    description="Local IP, WiFi SSID, public IP",
    patterns=[
        "network status", "wifi status", "kya wifi connect hai",
        "ip address", "mera ip kya hai", "public ip", "internet info",
    ],
)
def network_status(_slots: dict) -> str:
    return (f"Local IP: {_local_ip()} · "
            f"WiFi: {_wifi_ssid()} · "
            f"Public IP: {_public_ip()}")


@skill(
    name="ping",
    description="Ping a host and report round-trip time",
    patterns=["ping", "ping google", "internet check karo", "is internet up"],
)
def ping(slots: dict) -> str:
    host = (slots.get("content") or "8.8.8.8").strip().split()[0]
    if not re.match(r"^[\w.\-]+$", host):
        return "Invalid host."
    cmd = (["ping", "-n", "1", "-w", "1500", host]
           if sys.platform == "win32" else
           ["ping", "-c", "1", "-W", "2", host])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except Exception as e:
        return f"Ping failed: {e}"
    text = out.stdout + out.stderr
    m = re.search(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", text, re.I)
    if m:
        return f"{host} reachable · {m.group(1)} ms"
    return f"{host} did not respond."


# ╔══════════════════════════════════════════════════════════════════╗
# ║  power_actions                                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

@skill(
    name="lock_screen",
    description="Lock the workstation (Win+L equivalent)",
    patterns=["lock screen", "lock the pc", "lock karo", "screen lock",
              "pc lock", "screen lock karo"],
)
def lock_screen(_slots: dict) -> str:
    if sys.platform != "win32":
        return "Lock sirf Windows pe."
    try:
        import ctypes
        ok = ctypes.WinDLL("user32").LockWorkStation()
        return "Screen lock ho gaya." if ok else "Lock fail ho gaya."
    except Exception as e:
        return f"Lock failed: {e}"


@skill(
    name="sleep_pc",
    description="Put the PC to sleep (S3 standby)",
    patterns=["sleep pc", "sleep mode", "pc sleep karo", "computer sleep",
              "standby"],
)
def sleep_pc(_slots: dict) -> str:
    if sys.platform != "win32":
        return "Sleep sirf Windows pe."
    try:
        # rundll32 powrprof,SetSuspendState 0,1,0 — Stand-by, no hibernate, no force.
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState",
                          "0,1,0"], close_fds=True)
        return "Sleep mode mein ja raha hoon — sweet dreams."
    except Exception as e:
        return f"Sleep failed: {e}"


@skill(
    name="shutdown_pc",
    description="Schedule a shutdown in 60 s (can be cancelled)",
    patterns=["shutdown", "shutdown pc", "power off", "shut down karo",
              "pc band karo", "computer off karo"],
)
def shutdown_pc(_slots: dict) -> str:
    if sys.platform != "win32":
        return "Shutdown sirf Windows pe."
    try:
        # 60 s delay so the user has time to cancel via 'cancel shutdown'.
        subprocess.Popen(["shutdown", "/s", "/t", "60",
                          "/c", "AERIS scheduled shutdown — say 'cancel shutdown' to abort."],
                         close_fds=True)
        return "Shutdown 60 seconds mein hoga. 'cancel shutdown' bolo to ruk jayega."
    except Exception as e:
        return f"Shutdown failed: {e}"


@skill(
    name="cancel_shutdown",
    description="Abort a pending shutdown",
    patterns=["cancel shutdown", "shutdown cancel karo", "ruk jao shutdown",
              "abort shutdown", "shutdown abort"],
)
def cancel_shutdown(_slots: dict) -> str:
    if sys.platform != "win32":
        return "Sirf Windows pe."
    try:
        subprocess.Popen(["shutdown", "/a"], close_fds=True)
        return "Shutdown cancel kar diya."
    except Exception as e:
        return f"Cancel failed: {e}"


@skill(
    name="restart_pc",
    description="Schedule a restart in 60 s (can be cancelled)",
    patterns=["restart pc", "reboot", "computer restart", "pc restart karo",
              "reboot karo"],
)
def restart_pc(_slots: dict) -> str:
    if sys.platform != "win32":
        return "Sirf Windows pe."
    try:
        subprocess.Popen(["shutdown", "/r", "/t", "60",
                          "/c", "AERIS scheduled restart — say 'cancel shutdown' to abort."],
                         close_fds=True)
        return "Restart 60 seconds mein. 'cancel shutdown' to abort."
    except Exception as e:
        return f"Restart failed: {e}"
