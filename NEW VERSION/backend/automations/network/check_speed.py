# BACKEND/automations/network/check_speed.py
from BACKEND.automations.network.network_service import check_internet_speed as _check_internet_speed

def check_internet_speed(speech=None):
    """
    Measures internet speed.
    This is a blocking task and may take time.
    """
    return _check_internet_speed(speech)
