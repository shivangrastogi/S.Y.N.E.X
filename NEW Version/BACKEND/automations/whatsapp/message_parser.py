# BACKEND/automations/whatsapp/message_parser.py
"""
Enhanced WhatsApp message parser with validation and advanced pattern matching
Supports multiple message formats, Hinglish, and contact validation
"""

import re
from typing import Tuple, Optional


class MessageParserError(Exception):
    """Custom exception for message parsing errors"""
    pass


def parse_whatsapp_message(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts contact name and message content from user text.
    
    Supported formats:
    - "send a message to X, Y"
    - "send whatsapp message to X that Y"
    - "message X saying Y"
    - "whatsapp X: Y"
    - "send X a message Y"
    - "tell X that Y"
    - "ping X with Y"
    - Hinglish: "X ko message bhej Y"
    
    Args:
        text: User input text
        
    Returns:
        Tuple of (contact_name, message_content) or (None, None) if parsing fails
    """
    
    if not text or not isinstance(text, str):
        return None, None
    
    text = text.strip()
    text_lower = text.lower()
    
    # Remove common noise words (preserve original for extraction)
    text_for_matching = text_lower
    noise_words = ["whatsapp", "a message"]
    for noise in noise_words:
        text_for_matching = text_for_matching.replace(noise, " ")
    
    text_for_matching = " ".join(text_for_matching.split())  # Normalize whitespace
    
    # Enhanced patterns with priority order
    patterns = [
        # Standard formats
        r"send\s+to\s+(?P<contact>[^,]+),\s*(?P<message>.+)",
        r"send\s+to\s+(?P<contact>[^,]+)\s+that\s+(?P<message>.+)",
        r"send\s+(?P<contact>[^,]+)\s+(?:that|saying)\s+(?P<message>.+)",
        
        # Compact formats with colon
        r"^(?:message|ping|text)\s+(?P<contact>[^:,]+):\s*(?P<message>.+)",
        r"(?:message|ping|text)\s+(?P<contact>\w+(?:\s+\w+)?)\s+(?:saying|that)\s+(?P<message>.+)",
        
        # Tell format
        r"tell\s+(?P<contact>[^,]+)\s+(?:that|to)\s+(?P<message>.+)",
        
        # Direct format (Hinglish)
        r"(?P<contact>\w+)\s+ko\s+(?:message|msg)\s+(?:bhej|send|karo)\s+(?P<message>.+)",
        
        # Fallback: "to X, message"
        r"to\s+(?P<contact>[^,]+),\s*(?P<message>.+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_for_matching, re.IGNORECASE)
        if match:
            contact = match.group("contact").strip()
            message = match.group("message").strip()
            
            # Validate extracted data
            if contact and message:
                # Clean up contact name
                contact = _clean_contact_name(contact)
                # Clean up message
                message = _clean_message(message)
                
                if contact and message:
                    return contact, message
    
    return None, None


def _clean_contact_name(contact: str) -> str:
    """
    Clean and normalize contact name
    
    Args:
        contact: Raw contact name
        
    Returns:
        Cleaned contact name
    """
    if not contact:
        return ""
    
    # Remove common prefixes
    prefixes = ["to ", "message ", "send ", "tell "]
    for prefix in prefixes:
        if contact.lower().startswith(prefix):
            contact = contact[len(prefix):]
    
    # Remove trailing punctuation
    contact = contact.rstrip(",:;.")
    
    # Normalize whitespace
    contact = " ".join(contact.split())
    
    # Capitalize properly (each word)
    contact = contact.title()
    
    return contact.strip()


def _clean_message(message: str) -> str:
    """
    Clean and normalize message content
    
    Args:
        message: Raw message content
        
    Returns:
        Cleaned message content
    """
    if not message:
        return ""
    
    # Remove common prefixes
    prefixes = ["that ", "saying ", ":", "-"]
    for prefix in prefixes:
        if message.lower().startswith(prefix):
            message = message[len(prefix):]
    
    # Normalize whitespace
    message = " ".join(message.split())
    
    return message.strip()


def validate_contact(contact: str, min_length: int = 1, max_length: int = 100) -> bool:
    """
    Validate contact name
    
    Args:
        contact: Contact name to validate
        min_length: Minimum length (default 1)
        max_length: Maximum length (default 100)
        
    Returns:
        True if valid, False otherwise
    """
    if not contact or not isinstance(contact, str):
        return False
    
    contact = contact.strip()
    
    if len(contact) < min_length or len(contact) > max_length:
        return False
    
    # Check for invalid characters (allow letters, numbers, spaces, common punctuation)
    if not re.match(r'^[a-zA-Z0-9\s\.\-_]+$', contact):
        return False
    
    return True


def validate_message(message: str, min_length: int = 1, max_length: int = 5000, 
                    allow_empty: bool = False) -> bool:
    """
    Validate message content
    
    Args:
        message: Message to validate
        min_length: Minimum length (default 1)
        max_length: Maximum length (default 5000)
        allow_empty: Allow empty messages (default False)
        
    Returns:
        True if valid, False otherwise
    """
    if not message or not isinstance(message, str):
        return False if not allow_empty else True
    
    message = message.strip()
    
    if not allow_empty and len(message) == 0:
        return False
    
    if len(message) < min_length or len(message) > max_length:
        return False
    
    return True


def parse_and_validate(text: str, settings=None) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse and validate message with settings integration
    
    Args:
        text: User input text
        settings: WhatsAppAutomationSettings instance (optional)
        
    Returns:
        Tuple of (contact, message) or raises MessageParserError
        
    Raises:
        MessageParserError: If parsing or validation fails
    """
    # Parse
    contact, message = parse_whatsapp_message(text)
    
    if contact is None or message is None:
        raise MessageParserError(f"Failed to parse message from: '{text}'")
    
    # Get validation parameters from settings if provided
    if settings:
        contact_min = settings._settings.get("contact_min_length", 1)
        contact_max = settings._settings.get("contact_max_length", 100)
        message_max = settings._settings.get("message_max_length", 5000)
        allow_empty = settings._settings.get("allow_empty_messages", False)
    else:
        contact_min, contact_max = 1, 100
        message_max = 5000
        allow_empty = False
    
    # Validate contact
    if not validate_contact(contact, contact_min, contact_max):
        raise MessageParserError(
            f"Invalid contact name: '{contact}' "
            f"(must be {contact_min}-{contact_max} characters, alphanumeric)"
        )
    
    # Validate message
    if not validate_message(message, 1, message_max, allow_empty):
        raise MessageParserError(
            f"Invalid message: length must be 1-{message_max} characters"
        )
    
    return contact, message
