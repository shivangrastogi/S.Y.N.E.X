# Path: d:\New folder (2) - JARVIS\backend\mobile_hub\connectivity\websocket.py
"""
WebSocket Server - FastAPI WebSocket endpoint with Synex integration
Unified transport and launcher for mobile clients
"""

import logging
import asyncio
import json
import uvicorn
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import TYPE_CHECKING, Dict

from ..core.manager import ClientManager
from ..core.router import MessageRouter
from ..core.protocol import create_response, create_error
from backend.core.audio_handler import AudioHandler

if TYPE_CHECKING:
    from backend.main import Synex

logger = logging.getLogger(__name__)

class WebSocketServer:
    """FastAPI WebSocket server for JARVIS mobile clients"""
    
    def __init__(self, jarvis_instance: 'Synex'):
        self.jarvis = jarvis_instance
        self.client_manager = ClientManager()
        self.message_router = MessageRouter(jarvis_instance)
        self.audio_handler = AudioHandler(self)
        self.app = FastAPI(title="JARVIS Mobile Hub API")
        self.loop = None
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.handle_connection(websocket)
        
        @self.app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "connected_clients": await self.client_manager.count()
            }
        
    async def handle_connection(self, websocket: WebSocket):
        if not self.loop:
            self.loop = asyncio.get_running_loop()

        await websocket.accept()
        device_id = None
        
        try:
            while websocket.application_state.name != "DISCONNECTED":
                try:
                    data = await websocket.receive()
                except Exception as e:
                    logger.debug(f"Socket receive failed: {e}")
                    break
                    
                if "text" in data:
                    try:
                        message = json.loads(data["text"])
                    except json.JSONDecodeError:
                        continue
                    
                    msg_type = message.get("type")
                    
                    if msg_type == "heartbeat":
                        if device_id:
                            await self.client_manager.update_heartbeat(device_id)
                        await websocket.send_json({"type": "heartbeat_ack"})
                        continue

                    if msg_type == "registration":
                        payload = message.get("payload", {})
                        temp_device_id = payload.get("device_id")
                        if temp_device_id:
                            device_id = temp_device_id
                            await self.client_manager.register(
                                websocket, device_id, 
                                payload.get("device_name", "Unknown"),
                                payload.get("app_version", "1.0.0")
                            )
                            await websocket.send_json(create_response(
                                status="success",
                                message="Registration successful"
                            ))
                            self.jarvis._on_mobile_registration(
                                True, 
                                payload.get("device_name", "Unknown"),
                                device_id,
                                websocket.client.host
                            )
                        continue

                    if not device_id:
                        await websocket.send_json(create_error("UNAUTHORIZED", "Please register first"))
                        continue

                    response = await self.message_router.route_message(message, device_id)
                    
                    if msg_type == "command" and message.get("command") == "answer_call":
                         self.audio_handler.start_bridge(device_id)
                    
                    if response:
                        await websocket.send_json(response)
                
                elif "bytes" in data:
                    self.audio_handler.handle_mobile_audio(data["bytes"])

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if device_id:
                await self.client_manager.disconnect(device_id)
                self.audio_handler.stop_bridge()
                self.jarvis._on_mobile_registration(False, "", device_id, "")

    async def send_to_device_binary(self, device_id: str, data: bytes):
        client = await self.client_manager.get_client(device_id)
        if client:
            try: await client.websocket.send_bytes(data)
            except: pass

    async def broadcast(self, message: dict):
        await self.client_manager.broadcast(message)
    
    async def send_to_device(self, device_id: str, message: dict):
        await self.client_manager.send_to_client(device_id, message)
    
    def get_app(self) -> FastAPI:
        return self.app

    def broadcast_sync(self, message: dict):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)

def start_websocket_server(jarvis_instance, host="0.0.0.0", port=8765):
    """Start the FastAPI WebSocket server in a separate thread"""
    ws_server = WebSocketServer(jarvis_instance)
    app = ws_server.get_app()
    jarvis_instance.websocket_server = ws_server
    
    config = uvicorn.Config(app=app, host=host, port=port, log_level="info", access_log=False)
    server = uvicorn.Server(config)
    
    threading.Thread(target=server.run, daemon=True).start()
    return ws_server
