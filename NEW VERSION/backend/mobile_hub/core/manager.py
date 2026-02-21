# Path: d:\New folder (2) - JARVIS\backend\mobile_hub\core\manager.py
"""
Client Manager - Manages multiple connected WebSocket clients
Thread-safe operations for multi-client scenarios
"""

import asyncio
import logging
from typing import Dict, Optional, Set
from fastapi import WebSocket
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectedClient:
    """Represents a connected WebSocket client"""
    
    def __init__(self, websocket: WebSocket, device_id: str, device_name: str, app_version: str):
        self.websocket = websocket
        self.device_id = device_id
        self.device_name = device_name
        self.app_version = app_version
        self.connected_at = datetime.utcnow()
        self.last_heartbeat = datetime.utcnow()
        
    def __repr__(self):
        return f"<Client {self.device_name} ({self.device_id})>"


class ClientManager:
    """Manages all connected WebSocket clients"""
    
    def __init__(self):
        self._clients: Dict[str, ConnectedClient] = {}  # device_id -> ConnectedClient
        self._lock = asyncio.Lock()
        
    async def register(self, websocket: WebSocket, device_id: str, device_name: str, app_version: str) -> ConnectedClient:
        """Register a new client"""
        async with self._lock:
            # Disconnect existing client with same device_id if present
            if device_id in self._clients:
                logger.warning(f"Device {device_id} already connected. Replacing old connection.")
                await self.disconnect(device_id)
            
            client = ConnectedClient(websocket, device_id, device_name, app_version)
            self._clients[device_id] = client
            logger.info(f"📱 Registered {client}")
            return client
    
    async def disconnect(self, device_id: str):
        """Disconnect a client"""
        async with self._lock:
            if device_id in self._clients:
                client = self._clients.pop(device_id)
                try:
                    await client.websocket.close()
                except Exception as e:
                    logger.debug(f"Error closing websocket for {device_id}: {e}")
                logger.info(f"📴 Disconnected {client}")
    
    async def get_client(self, device_id: str) -> Optional[ConnectedClient]:
        """Get a specific client"""
        async with self._lock:
            return self._clients.get(device_id)
    
    async def get_all_clients(self) -> Dict[str, ConnectedClient]:
        """Get all connected clients (copy)"""
        async with self._lock:
            return self._clients.copy()
    
    async def send_to_client(self, device_id: str, message: dict) -> bool:
        """Send message to a specific client"""
        client = await self.get_client(device_id)
        if client:
            try:
                await client.websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"Failed to send message to {device_id}: {e}")
                await self.disconnect(device_id)
                return False
        return False
    
    async def broadcast(self, message: dict, exclude: Optional[Set[str]] = None):
        """Broadcast message to all clients (optionally excluding some)"""
        exclude = exclude or set()
        clients = await self.get_all_clients()
        
        for device_id, client in clients.items():
            if device_id not in exclude:
                try:
                    await client.websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to broadcast to {device_id}: {e}")
                    await self.disconnect(device_id)
    
    async def update_heartbeat(self, device_id: str):
        """Update last heartbeat timestamp for a client"""
        async with self._lock:
            if device_id in self._clients:
                self._clients[device_id].last_heartbeat = datetime.utcnow()
    
    async def count(self) -> int:
        """Get number of connected clients"""
        async with self._lock:
            return len(self._clients)
    
    async def cleanup_stale_connections(self, timeout_seconds: int = 120):
        """Remove clients that haven't sent heartbeat in timeout_seconds"""
        now = datetime.utcnow()
        async with self._lock:
            stale_devices = [
                device_id for device_id, client in self._clients.items()
                if (now - client.last_heartbeat).total_seconds() > timeout_seconds
            ]
        
        for device_id in stale_devices:
            logger.warning(f"Removing stale connection: {device_id}")
            await self.disconnect(device_id)
