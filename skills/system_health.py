"""Extended system + network health check.

The legacy `system_info` intent only reports battery/cpu/ram. This skill
goes deeper: disk usage, uptime, network latency, public IP, top 3 CPU
processes — useful when something feels slow.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.skill_registry import skill  # noqa: E402

log = logging.getLogger(__name__)


def _disk_summary() -> str:
    try:
        import psutil
        parts = []
        for p in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(p.mountpoint)
                parts.append(f"{p.device.rstrip(chr(92))} {u.percent:.0f}% used "
                             f"({u.free/1e9:.0f} GB free)")
            except Exception:
                continue
        return " · ".join(parts) if parts else "disk info unavailable"
    except Exception:
        return "disk info unavailable"


def _uptime() -> str:
    try:
        import psutil
        delta = timedelta(seconds=time.time() - psutil.boot_time())
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        mins = rem // 60
        bits = []
        if days: bits.append(f"{days}d")
        if hours: bits.append(f"{hours}h")
        bits.append(f"{mins}m")
        return " ".join(bits)
    except Exception:
        return "?"


def _top_processes(n: int = 3) -> list[str]:
    try:
        import psutil
        ps = []
        for p in psutil.process_iter(["name", "cpu_percent"]):
            try:
                ps.append((p.info["name"] or "?", p.info["cpu_percent"] or 0.0))
            except Exception:
                continue
        # First call is always 0.0 — re-poll briefly for real numbers.
        psutil.cpu_percent(interval=None)
        time.sleep(0.4)
        ps = []
        for p in psutil.process_iter(["name", "cpu_percent"]):
            try:
                ps.append((p.info["name"] or "?", p.info["cpu_percent"] or 0.0))
            except Exception:
                continue
        ps.sort(key=lambda r: r[1], reverse=True)
        return [f"{name}({pct:.0f}%)" for name, pct in ps[:n] if pct > 0]
    except Exception:
        return []


def _ping(host: str = "8.8.8.8", count: int = 2) -> str:
    try:
        cmd = ["ping", "-n", str(count), host]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL,
                                      timeout=4, text=True, encoding="cp437")
        # Parse "Average = 12ms" line on Windows ping.
        for line in out.splitlines():
            if "Average" in line:
                return line.strip().split("=")[-1].strip()
        return "ok"
    except Exception:
        return "no internet"


def _public_ip() -> str:
    try:
        import urllib.request
        with urllib.request.urlopen("https://api.ipify.org", timeout=3) as r:
            return r.read().decode("utf-8").strip()
    except Exception:
        return "unknown"


def _wifi_name() -> str:
    try:
        out = subprocess.check_output(["netsh", "wlan", "show", "interfaces"],
                                      timeout=4, text=True,
                                      stderr=subprocess.DEVNULL,
                                      encoding="cp437")
        for line in out.splitlines():
            line = line.strip()
            if line.lower().startswith("ssid") and not line.lower().startswith("bssid"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip() or "(none)"
    except Exception:
        pass
    return "unknown"


@skill(
    name="full_system_health",
    description="Deep system check: battery, CPU, RAM, disk, uptime, top processes, network ping, WiFi SSID.",
    patterns=[
        "full system health", "system health check karo",
        "deep system check", "saari system info do",
        "complete system status", "everything about my system",
        "full pc check", "laptop ka full status",
        "system ka full report", "full diagnostic",
    ],
    required_entities=[],
)
def full_system_health(slots: dict) -> str:
    try:
        import psutil
    except Exception:
        return "psutil install nahi hai."
    lines = []
    bat = psutil.sensors_battery()
    if bat:
        plug = "charging" if bat.power_plugged else "on battery"
        lines.append(f"Battery: {bat.percent:.0f}% ({plug})")
    lines.append(f"CPU: {psutil.cpu_percent(interval=0.4):.0f}%, "
                 f"{psutil.cpu_count(logical=True)} threads")
    ram = psutil.virtual_memory()
    lines.append(f"RAM: {ram.used/1e9:.1f}/{ram.total/1e9:.1f} GB ({ram.percent:.0f}%)")
    lines.append(f"Disk: {_disk_summary()}")
    lines.append(f"Uptime: {_uptime()}")
    top = _top_processes(3)
    if top:
        lines.append(f"Top CPU: {', '.join(top)}")
    lines.append(f"Net: ping {_ping()}, WiFi '{_wifi_name()}', public IP {_public_ip()}")
    return "\n".join(lines)


@skill(
    name="network_check",
    description="Quick network status: ping, public IP, WiFi name.",
    patterns=[
        "network check karo", "internet check karo",
        "wifi name kya hai", "ping check",
        "public ip kya hai", "internet status",
        "network status batao",
    ],
    required_entities=[],
)
def network_check(slots: dict) -> str:
    return (f"Ping {_ping()} · WiFi '{_wifi_name()}' · "
            f"Public IP {_public_ip()}")
