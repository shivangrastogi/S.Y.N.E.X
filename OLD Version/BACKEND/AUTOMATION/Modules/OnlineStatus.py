import socket


def is_online(timeout=2):
    """
    Returns True if internet is reachable, else False.
    This does NOT depend on DNS resolution.
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False


def get_online_status_report():
    if is_online():
        return "Sir, you are currently online and connected to the internet."
    else:
        return "Sir, you are currently offline. No active internet connection is detected."
