import socket
import requests


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # No real packet sent
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_public_ip(timeout=3):
    """
    Returns public IP if online, else None
    """
    try:
        response = requests.get("https://api.ipify.org", timeout=timeout)
        response.raise_for_status()
        return response.text.strip()
    except Exception:
        return None


def get_ip_report():
    local_ip = get_local_ip()
    public_ip = get_public_ip()

    # No network interface at all
    if local_ip == "127.0.0.1" and not public_ip:
        return "Sir, no active network connection is detected."

    # Offline but LAN available
    if not public_ip:
        return f"Sir, you are offline. Your local IP address is {local_ip}."

    # Online
    return (
        f"Sir, you are online. "
        f"Your local IP address is {local_ip}, "
        f"and your public IP address is {public_ip}."
    )
