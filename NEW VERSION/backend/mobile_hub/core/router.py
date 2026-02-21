# Path: d:\New folder (2) - JARVIS\backend\mobile_hub\core\router.py
"""
Message Router - Routes incoming WebSocket messages to appropriate handlers
Clean interface between WebSocket layer and JARVIS core
"""

import logging
from typing import TYPE_CHECKING
from ..features.notifications import NotificationManager
from .protocol import (
    create_response,
    create_notification,
    create_error,
    create_heartbeat
)

if TYPE_CHECKING:
    from backend.main import Synex

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes WebSocket messages to JARVIS core functionality"""
    
    def __init__(self, jarvis_instance: 'Synex'):
        self.jarvis = jarvis_instance
        self.notification_manager = NotificationManager()
    
    async def route_message(self, message: dict, device_id: str) -> dict:
        """
        Route incoming message to appropriate handler
        
        Args:
            message: Parsed JSON message from client
            device_id: ID of the sending device
            
        Returns:
            Response message dict to send back to client
        """
        msg_type = message.get("type")
        payload = message.get("payload", {})
        
        try:
            if msg_type == "command":
                return await self._handle_command(payload, device_id)
            
            elif msg_type == "heartbeat":
                return await self._handle_heartbeat(payload, device_id)
                
            elif msg_type == "notification":
                return await self._handle_notification(payload, device_id)

            elif msg_type == "incoming_call":
                return await self._handle_call(payload, device_id)
            
            elif msg_type == "registration":
                # Registration is handled in websocket.py
                return create_response("success", "Already registered")
            
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                return create_error(
                    code="UNKNOWN_TYPE",
                    message=f"Unknown message type: {msg_type}"
                )
                
        except Exception as e:
            logger.error(f"Error routing message: {e}", exc_info=True)
            return create_error(
                code="ROUTING_ERROR",
                message="Internal server error",
                details={"error": str(e)}
            )
    
    async def _handle_command(self, payload: dict, device_id: str) -> dict:
        """Handle command execution request"""
        text = payload.get("text", "").strip()
        source = payload.get("source", "text")
        
        if not text:
            return create_error(
                code="EMPTY_COMMAND",
                message="Command text cannot be empty"
            )
        
        try:
            logger.info(f"📱 Command from {device_id}: {text}")
            
            # Submit command to JARVIS processing queue
            if hasattr(self.jarvis, 'submit_text'):
                self.jarvis.submit_text(text)
            else:
                 self.jarvis.input_queue.put(text)

            return create_response(
                status="success",
                message="Command received and queued",
                data={"command": text, "source": source}
            )
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return create_error(
                code="COMMAND_FAILED",
                message="Failed to process command",
                details={"error": str(e)}
            )
    
    async def _handle_heartbeat(self, payload: dict, device_id: str) -> dict:
        """Handle heartbeat ping"""
        # Just echo back a heartbeat response
        return create_heartbeat()

    async def _handle_notification(self, payload: dict, device_id: str) -> dict:
        """Handle incoming notification from device"""
        try:
            app_name = payload.get("app_name", "Unknown")
            title = payload.get("title", "")
            
            # Store notification
            self.notification_manager.add(payload)
            
            # Notify GUI via main instance
            if hasattr(self.jarvis, '_on_mobile_notification'):
                self.jarvis._on_mobile_notification(payload)
            
            logger.info(f"🔔 Notification received from {app_name}: {title}")
            return create_response("success", "Notification received")
        except Exception as e:
            logger.error(f"Error handling notification: {e}")
            return create_error("NOTIFICATION_ERROR", str(e))
            
    async def _handle_call(self, payload: dict, device_id: str) -> dict:
        """Handle incoming call event"""
        try:
            caller = payload.get("name") or payload.get("caller") or "Unknown"
            number = payload.get("number", "")
            status = payload.get("status", "ringing")
            
            logger.info(f"📞 Incoming call from {caller} ({number})")
            
            # Notify main instance (GUI + TTS)
            if hasattr(self.jarvis, '_on_incoming_call'):
                self.jarvis._on_incoming_call(payload)
                
            return create_response("success", "Call event processed")
        except Exception as e:
            logger.error(f"Error handling call: {e}")
            return create_error("CALL_ERROR", str(e))

    def send_notification_to_device(self, device_id: str, title: str, body: str):
        """
        Helper to send notification to a specific device
        (Called from JARVIS core when needed)
        """
        # This will be used by the WebSocket server's broadcast mechanism
        return create_notification(title, body)
