# Path: d:\New folder (2) - JARVIS\backend\mobile_hub\connectivity\discovery.py
"""
Discovery Service - mDNS/Zeroconf announcement for JARVIS
"""

import logging
import socket
from zeroconf import ServiceInfo, Zeroconf

logger = logging.getLogger(__name__)

class DiscoveryService:
    def __init__(self, port=8765):
        self.port = port
        self.zeroconf = Zeroconf()
        self.info = None
        self.running = False

    def start(self):
        if self.running:
            return

        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # doesn't even have to be reachable
                s.connect(('10.255.255.255', 1))
                IP = s.getsockname()[0]
            except Exception:
                IP = '127.0.0.1'
            finally:
                s.close()

            desc = {'path': '/ws'}
            
            self.info = ServiceInfo(
                "_jarvis._tcp.local.",
                "JARVIS Backend._jarvis._tcp.local.",
                addresses=[socket.inet_aton(IP)],
                port=self.port,
                properties=desc,
                server="jarvis-server.local.",
            )

            self.zeroconf.register_service(self.info)
            self.running = True
            logger.info(f"Discovery Service started. Announcing JARVIS at {IP}:{self.port}")
            print(f"DISCOVERY: Discovery Service started. Announcing JARVIS at {IP}:{self.port}")
        
        except Exception as e:
            logger.error(f"Failed to start Discovery Service: {e}")
            print(f"DISCOVERY Error: Failed to start Discovery Service: {e}")

    def stop(self):
        if self.running and self.info:
            try:
                self.zeroconf.unregister_service(self.info)
                self.zeroconf.close()
                self.running = False
                logger.info("Discovery Service stopped.")
                print("DISCOVERY: Discovery Service stopped.")
            except Exception as e:
                logger.error(f"Error stopping Discovery Service: {e}")
