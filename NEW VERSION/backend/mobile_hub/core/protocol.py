# Path: d:\New folder (2) - JARVIS\backend\mobile_hub\core\protocol.py
"""
Message Protocol - Structured JSON schemas for WebSocket communication
Uses Pydantic for type safety and validation
"""

from pydantic import BaseModel, Field
from typing import Literal, Any, Optional, Dict
from datetime import datetime
import uuid


# Base Message Schema
class BaseMessage(BaseModel):
    """Base structure for all WebSocket messages"""
    type: str
    payload: Any
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


# Registration Messages
class RegistrationPayload(BaseModel):
    """Client registration data"""
    device_id: str
    device_name: str
    app_version: str


class RegistrationMessage(BaseMessage):
    """Client → Server: Device registration"""
    type: Literal["registration"] = "registration"
    payload: RegistrationPayload


# Command Messages
class CommandPayload(BaseModel):
    """Command execution request"""
    text: str
    source: Literal["voice", "text"] = "text"


class CommandMessage(BaseMessage):
    """Client → Server: Command execution request"""
    type: Literal["command"] = "command"
    payload: CommandPayload


# Response Messages
class ResponsePayload(BaseModel):
    """Server response to client"""
    status: Literal["success", "error"]
    message: str
    data: Optional[Dict[str, Any]] = None


class ResponseMessage(BaseMessage):
    """Server → Client: Response to command"""
    type: Literal["response"] = "response"
    payload: ResponsePayload


# Heartbeat Messages
class HeartbeatPayload(BaseModel):
    """Heartbeat ping/pong"""
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HeartbeatMessage(BaseMessage):
    """Bidirectional: Connection health check"""
    type: Literal["heartbeat"] = "heartbeat"
    payload: HeartbeatPayload


# Notification Messages
class NotificationPayload(BaseModel):
    """Push notification to client"""
    title: str
    body: str
    data: Optional[Dict[str, Any]] = None


class NotificationMessage(BaseMessage):
    """Server → Client: Push notification"""
    type: Literal["notification"] = "notification"
    payload: NotificationPayload


# Error Messages
class ErrorPayload(BaseModel):
    """Error information"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorMessage(BaseMessage):
    """Bidirectional: Error notification"""
    type: Literal["error"] = "error"
    payload: ErrorPayload


# Helper functions
def create_response(status: str, message: str, data: Optional[Dict] = None) -> dict:
    """Create a response message"""
    return ResponseMessage(
        payload=ResponsePayload(
            status=status,
            message=message,
            data=data
        )
    ).model_dump()


def create_notification(title: str, body: str, data: Optional[Dict] = None) -> dict:
    """Create a notification message"""
    return NotificationMessage(
        payload=NotificationPayload(
            title=title,
            body=body,
            data=data
        )
    ).model_dump()


def create_error(code: str, message: str, details: Optional[Dict] = None) -> dict:
    """Create an error message"""
    return ErrorMessage(
        payload=ErrorPayload(
            code=code,
            message=message,
            details=details
        )
    ).model_dump()


def create_heartbeat() -> dict:
    """Create a heartbeat message"""
    return HeartbeatMessage(
        payload=HeartbeatPayload()
    ).model_dump()
