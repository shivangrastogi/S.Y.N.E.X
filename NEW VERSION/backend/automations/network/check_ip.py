# BACKEND/automations/network/check_ip.py
from BACKEND.automations.network.network_service import get_public_ip

def check_ip_address():
    """
    Fetches public IP address.
    """
    return get_public_ip()
