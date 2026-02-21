# ws_server.py
import json
import asyncio
import websockets

class MobileWebSocketServer:
    def __init__(self, jarvis):
        self.jarvis = jarvis
        self.clients = set()

    async def handler(self, websocket):
        self.clients.add(websocket)
        print("📲 Phone connected via WebSocket")

        try:
            async for message in websocket:
                data = json.loads(message)
                self._handle_message(data)
        finally:
            self.clients.remove(websocket)
            print("📴 Phone disconnected")

    def _handle_message(self, data):
        msg_type = data.get("type")

        if msg_type == "notification":
            print("🔔 Phone notification:", data)
            self.jarvis.speech.speak(
                f"New notification from {data.get('app')}"
            )
            self._reply("notification_ack")

        elif msg_type == "call":
            print("📞 Incoming call:", data)
            self.jarvis.speech.speak("Incoming call")
            self._reply("call_ack")

        elif msg_type == "heartbeat":
            print("💓 Heartbeat received")
            self._reply("heartbeat_ack")

    def _reply(self, ack_type):
        for ws in list(self.clients):
            asyncio.create_task(
                ws.send(json.dumps({"type": ack_type}))
            )

    async def start(self, host="0.0.0.0", port=8765):
        try:
            print("🌐 WebSocket server started on", port)
            async with websockets.serve(self.handler, host, port):
                await asyncio.Future()
        except OSError as e:
            if getattr(e, "errno", None) == 10048:
                print(f"⚠️ WebSocket port {port} already in use. Skipping WebSocket server startup.")
                return
            raise
