# BACKEND/mobile/mobile.py
from flask import Flask, request, jsonify
import threading, time
from BACKEND.mobile.device_registry import DeviceRegistry

class MobileServer:
    def __init__(self, jarvis):
        self.jarvis = jarvis
        self.app = Flask(__name__)
        self.registry = DeviceRegistry()
        self.port = 5055
        self._routes()

    def _routes(self):

        @self.app.route("/ping")
        def ping():
            return jsonify({
                "status": "online",
                "name": "Synex",
                "features": [
                    "notifications",
                    "calls",
                    "device_info",
                    "websocket"
                ]
            })

        @self.app.route("/register", methods=["POST"])
        def register():
            data = request.json
            device_id = data["device_id"]
            name = data.get("device_name", "Android")
            ip = request.remote_addr

            self.registry.register(device_id, name, ip)
            print(f"📱 Registered {name} @ {ip}")

            return jsonify({"status": "registered"})

        @self.app.route("/notification", methods=["POST"])
        def notification():
            data = request.json
            print("🔔 Notification:", data)

            self.jarvis.speech.speak(
                f"Notification from {data.get('app')}"
            )
            return jsonify({"ok": True})

    def start(self):
        threading.Thread(
            target=lambda: self.app.run(
                host="0.0.0.0",
                port=self.port,
                debug=False,
                use_reloader=False
            ),
            daemon=True
        ).start()

        print("📡 Mobile HTTP bridge running on", self.port)
