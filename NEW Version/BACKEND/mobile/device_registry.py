# BACKEND/mobile/device_registry.py
import time

class DeviceRegistry:
    def __init__(self):
        self.devices = {}

    def register(self, device_id, name, ip):
        self.devices[device_id] = {
            "name": name,
            "ip": ip,
            "last_seen": time.time()
        }

    def heartbeat(self, device_id):
        if device_id in self.devices:
            self.devices[device_id]["last_seen"] = time.time()

    def all(self):
        return self.devices
