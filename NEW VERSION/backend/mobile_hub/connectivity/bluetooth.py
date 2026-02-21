# Path: d:\New folder (2) - JARVIS\backend\mobile_hub\connectivity\bluetooth.py
"""
Bluetooth Server - RFCOMM transport for JARVIS mobile clients
"""

import logging
import socket
import threading
import json
import platform

logger = logging.getLogger(__name__)

class BluetoothServer:
    def __init__(self, jarvis, port=1):
        self.jarvis = jarvis
        self.port = port
        self.server_sock = None
        self.client_sock = None
        self.running = False
        # Standard Serial Port Profile (SPP) UUID
        self.uuid = "00001101-0000-1000-8000-00805F9B34FB"
        
        # Set device name for identification
        self.device_name = f"JARVIS-{platform.node()}"

    def start(self):
        if self.running:
            return

        try:
            for p in range(1, 11):
                try:
                    self.server_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                    self.server_sock.bind((socket.BDADDR_ANY, p))
                    self.server_sock.listen(1)
                    self.port = p
                    self.running = True
                    print(f"BT: Bluetooth Server started on RFCOMM channel {self.port}")
                    break
                except OSError:
                    if self.server_sock:
                        self.server_sock.close()
            
            if not self.running:
                 raise Exception("Could not find an open RFCOMM channel (1-10)")

            threading.Thread(target=self._accept_loop, daemon=True).start()

        except Exception as e:
            print(f"BT Error: Failed to start Bluetooth Server: {e}")
            logger.error(f"Failed to start Bluetooth Server: {e}")

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, client_info = self.server_sock.accept()
                self.client_sock = client_sock
                
                try:
                    welcome_msg = json.dumps({"type": "connected", "status": "ready"}) + "\n"
                    client_sock.send(welcome_msg.encode('utf-8'))
                except Exception as e:
                    print(f"BT: Failed to send welcome message: {e}")
                
                self._handle_client(client_sock)
            except Exception as e:
                if self.running:
                    print(f"BT Error: Bluetooth Accept Error: {e}")
                break

    def _handle_client(self, client_sock):
        try:
            while True:
                data = client_sock.recv(1024)
                if not data:
                    break
                
                try:
                    text_data = data.decode('utf-8').strip()
                    if text_data:
                        try:
                            json_data = json.loads(text_data)
                            self._process_json_command(json_data)
                        except json.JSONDecodeError:
                            self.jarvis._process_command(text_data)
                except Exception as e:
                    print(f"BT Error: Error processing BT data: {e}")
                    
        except OSError:
            pass
        finally:
            client_sock.close()
            self.client_sock = None

    def _process_json_command(self, data):
        msg_type = data.get("type")
        if msg_type == "command" or msg_type == "text_input":
            text = data.get("text")
            if text:
                self.jarvis.submit_text(text)

    def send(self, message):
        """Send JSON message to connected client"""
        if self.client_sock:
            try:
                if isinstance(message, dict):
                    message = json.dumps(message)
                
                # Ensure newline delimiter
                if not message.endswith("\n"):
                    message += "\n"
                
                self.client_sock.send(message.encode('utf-8'))
                return True
            except Exception as e:
                print(f"BT Error: Failed to send message: {e}")
                threading.Thread(target=self._handle_disconnect, daemon=True).start()
                return False
        return False

    def _handle_disconnect(self):
        # Cleanup
        if self.client_sock:
            try: self.client_sock.close()
            except: pass
            self.client_sock = None
        print("BT: Client disconnected")

    def stop(self):
        self.running = False
        if self.server_sock:
            try: self.server_sock.close()
            except: pass
        if self.client_sock:
            try: self.client_sock.close()
            except: pass
        print("BT: Bluetooth Server stopped.")
