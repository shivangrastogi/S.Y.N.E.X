# Path: d:\New folder (2) - JARVIS\backend\isolations\mobile_test_server.py
import os
import sys
import time
import threading
import json
import asyncio

# Fix path to include workspace root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(CURRENT_DIR) 
WORKSPACE_ROOT = os.path.dirname(BACKEND_ROOT)

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

try:
    from mobile_hub.connectivity.websocket import start_websocket_server
    from mobile_hub.connectivity.discovery import DiscoveryService
except ImportError as e:
    print(f"Import Error: {e}")
    print(f"Sys Path: {sys.path}")
    sys.exit(1)

class MockSynex:
    """
    A lightweight mock of the main Synex class 
    to satisfy dependencies for WebSocketServer.
    """
    def __init__(self):
        self.mobile_callback = None
        self.incoming_call_callback = self._on_incoming_call
        self.websocket_server = None
    
    def _on_incoming_call(self, data):
        caller = data.get("caller", "Unknown")
        number = data.get("number", "Unknown")
        status = data.get("status", "Unknown")
        print(f"\n[📱] INCOMING CALL DETECTED!")
        print(f"      From: {caller} ({number})")
        print(f"      Status: {status}")
        print("      > Type 'a' to ANSWER or 'd' to DECLINE")

    def _on_mobile_notification(self, data):
        # Mute other notifications for this test to keep console clean
        pass

    def send_mobile_command(self, command, data=None):
        """Send a command using the broadcast_sync method we fixed"""
        if self.websocket_server:
            message = {
                "type": "command",
                "command": command,
                "payload": data or {}
            }
            if hasattr(self.websocket_server, "broadcast_sync"):
                self.websocket_server.broadcast_sync(message)
                print(f"[📤] Sent command: {command}")
            else:
                print("[❌] Error: WebSocketServer missing broadcast_sync")
        else:
            print("[❌] WebSocket Server not initialized")

def main():
    print("==================================================")
    print("      JARVIS MOBILE ISOLATION TEST FRAMEWORK      ")
    print("==================================================")
    print("1. Starting Mock Backend...")
    
    jarvis = MockSynex()
    
    # Start WebSocket Server
    print("2. Launching WebSocket Server on Port 8765...")
    try:
        jarvis.websocket_server = start_websocket_server(jarvis, host="0.0.0.0", port=8765)
        print("   [✓] WebSocket Server Running")
    except Exception as e:
        print(f"   [❌] Failed to start WebSocket: {e}")
        return

    # Start Discovery Service
    print("3. Starting Discovery Service (mDNS)...")
    try:
        discovery = DiscoveryService(port=8765)
        discovery.start()
        print("   [✓] Discovery Service Broadcasting")
    except Exception as e:
        print(f"   [❌] Failed to start Discovery: {e}")
        return

    print("\n--------------------------------------------------")
    print("STATUS: Waiting for mobile connection...")
    print("TIP: If the app doesn't find the server, check:")
    print("     1. Phone and PC are on SAME WiFi.")
    print("     2. Firewall on PC is not blocking port 8765.")
    print("     3. You see '📲 WebSocket connection' message below.")
    print("--------------------------------------------------")

    # Command Loop
    while True:
        try:
            cmd = input("\n[a] Answer | [d] Decline | [q] Quit > ").strip().lower()
            
            if cmd == 'q':
                print("Exiting...")
                break
            elif cmd == 'a':
                jarvis.send_mobile_command("answer_call")
            elif cmd == 'd':
                jarvis.send_mobile_command("decline_call")
            else:
                print("Invalid choice. Try: a, d, or q")
        except KeyboardInterrupt:
            break
            
    # Cleanup (OS will handle it mostly, but good practice)
    if discovery:
        discovery.stop()

if __name__ == "__main__":
    main()
