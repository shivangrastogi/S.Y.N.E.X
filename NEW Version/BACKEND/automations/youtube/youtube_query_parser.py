# BACKEND/automations/youtube/youtube_query_parser.py
"""
YouTube query parser with validation and advanced pattern matching
Supports multiple query formats and Hinglish
"""

import re
from typing import Tuple, Optional, Literal


class YouTubeQueryError(Exception):
    """Custom exception for YouTube query parsing errors"""
    pass


def parse_youtube_query(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts action and query from user text.
    
    Supported formats:
    - "play [song/video] on youtube"
    - "search for [query] on youtube"
    - "youtube play [query]"
    - "open [query] youtube"
    - "play [query]" (assumes YouTube)
    - Hinglish: "[query] youtube pe play karo"
    
    Args:
        text: User input text
        
    Returns:
        Tuple of (action, query) where action is "play" or "search"
        Returns (None, None) if parsing fails
    """
    
    if not text or not isinstance(text, str):
        return None, None
    
    text = text.strip()
    text_lower = text.lower()
    
    # Remove common noise words
    noise_words = ["on youtube", "youtube", "a video", "video", "song"]
    text_cleaned = text_lower
    for noise in noise_words:
        text_cleaned = text_cleaned.replace(noise, " ")
    
    text_cleaned = " ".join(text_cleaned.split())  # Normalize whitespace
    
    # Enhanced patterns with priority order
    patterns = [
        # Play patterns
        (r"^play\s+(?:the\s+)?(?:song\s+)?(?:video\s+)?(.+)", "play"),
        (r"^start\s+playing\s+(.+)", "play"),
        (r"^put\s+on\s+(.+)", "play"),
        (r"^open\s+(.+)", "play"),
        
        # Search patterns
        (r"^search\s+(?:for\s+)?(.+)", "search"),
        (r"^find\s+(.+)", "search"),
        (r"^look\s+(?:for|up)\s+(.+)", "search"),
        
        # Hinglish patterns
        (r"(.+?)\s+(?:pe|par)\s+(?:play|chala|chalao)\s+(?:karo|do)", "play"),
        (r"(.+?)\s+(?:search|dhundo|dhundho)\s+(?:karo|do)", "search"),
        
        # Fallback: any remaining text as play
        (r"^(.+)$", "play"),
    ]
    
    for pattern, action in patterns:
        match = re.search(pattern, text_cleaned, re.IGNORECASE)
        if match:
            query = match.group(1).strip()
            
            if query and len(query) > 0:
                # Clean up query
                query = _clean_query(query)
                
                if query:
                    return action, query
    
    return None, None


def _clean_query(query: str) -> str:
    """
    Clean and normalize YouTube query
    
    Args:
        query: Raw query text
        
    Returns:
        Cleaned query
    """
    if not query:
        return ""
    
    # Remove common prefixes/suffixes
    removals = ["the ", "a ", "an ", " video", " song", " on youtube", " youtube"]
    for removal in removals:
        if query.lower().startswith(removal):
            query = query[len(removal):]
        if query.lower().endswith(removal):
            query = query[:-len(removal)]
    
    # Remove extra whitespace
    query = " ".join(query.split())
    
    return query.strip()


def validate_query(query: str, min_length: int = 1, max_length: int = 200) -> bool:
    """
    Validate YouTube query
    
    Args:
        query: Query to validate
        min_length: Minimum length (default 1)
        max_length: Maximum length (default 200)
        
    Returns:
        True if valid, False otherwise
    """
    if not query or not isinstance(query, str):
        return False
    
    query = query.strip()
    
    if len(query) < min_length or len(query) > max_length:
        return False
    
    return True


def parse_and_validate(text: str, settings=None) -> Tuple[str, str]:
    """
    Parse and validate YouTube query with settings integration
    
    Args:
        text: User input text
        settings: YouTubeAutomationSettings instance (optional)
        
    Returns:
        Tuple of (action, query)
        
    Raises:
        YouTubeQueryError: If parsing or validation fails
    """
    # Parse
    action, query = parse_youtube_query(text)
    
    if action is None or query is None:
        raise YouTubeQueryError(f"Failed to parse YouTube query from: '{text}'")
    
    # Get validation parameters from settings if provided
    if settings:
        query_min = settings._settings.get("query_min_length", 1)
        query_max = settings._settings.get("query_max_length", 200)
    else:
        query_min, query_max = 1, 200
    
    # Validate query
    if not validate_query(query, query_min, query_max):
        raise YouTubeQueryError(
            f"Invalid YouTube query: '{query}' "
            f"(must be {query_min}-{query_max} characters)"
        )
    
    return action, query


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract video ID from YouTube URL
    
    Args:
        url: YouTube URL
        
    Returns:
        Video ID or None if not found
    """
    patterns = [
        r"(?:youtube\.com\/watch\?v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be\/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})",
        r"(?:youtube\.com\/v\/)([a-zA-Z0-9_-]{11})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def is_youtube_url(text: str) -> bool:
    """
    Check if text is a YouTube URL
    
    Args:
        text: Text to check
        
    Returns:
        True if YouTube URL, False otherwise
    """
    if not text:
        return False
    
    youtube_domains = ["youtube.com", "youtu.be", "youtube-nocookie.com"]
    
    return any(domain in text.lower() for domain in youtube_domains)


def parse_player_command(text: str) -> Tuple[Optional[str], Optional[any]]:
    """
    Parse player control commands
    
    Supported commands:
    - pause, stop, resume
    - volume up/down, mute/unmute
    - forward/backward, restart
    - speed up/down, set speed to X
    - fullscreen, exit fullscreen
    
    Args:
        text: User input text
        
    Returns:
        Tuple of (command, parameter)
        Example: ("set_speed", 1.5) or ("pause", None)
    """
    
    if not text:
        return None, None
    
    text_lower = text.lower().strip()
    
    # Playback commands
    if "pause" in text_lower or "stop" in text_lower:
        return "pause", None
    if "resume" in text_lower or "play" in text_lower or "continue" in text_lower:
        return "resume", None
    if "restart" in text_lower or "start over" in text_lower:
        return "restart", None
    
    # Volume commands
    if "volume up" in text_lower or "increase volume" in text_lower:
        return "volume_up", None
    if "volume down" in text_lower or "decrease volume" in text_lower:
        return "volume_down", None
    if "mute" in text_lower:
        return "mute", None
    if "unmute" in text_lower:
        return "unmute", None
    
    # Seek commands
    if "forward" in text_lower or "skip ahead" in text_lower:
        # Try to extract seconds
        match = re.search(r"(\d+)\s*(?:seconds?|secs?)", text_lower)
        seconds = int(match.group(1)) if match else 10
        return "forward", seconds
    if "backward" in text_lower or "go back" in text_lower or "rewind" in text_lower:
        match = re.search(r"(\d+)\s*(?:seconds?|secs?)", text_lower)
        seconds = int(match.group(1)) if match else 10
        return "backward", seconds
    
    # Speed commands
    if "speed up" in text_lower or "faster" in text_lower:
        return "speed_up", None
    if "speed down" in text_lower or "slow down" in text_lower or "slower" in text_lower:
        return "speed_down", None
    if "normal speed" in text_lower or "reset speed" in text_lower:
        return "set_speed", 1.0
    
    # Speed setting
    match = re.search(r"(?:set|change|make)\s+speed\s+(?:to\s+)?([0-9.]+)", text_lower)
    if match:
        speed = float(match.group(1))
        return "set_speed", speed
    
    # Fullscreen commands
    if "fullscreen" in text_lower or "full screen" in text_lower:
        if "exit" in text_lower or "leave" in text_lower:
            return "exit_fullscreen", None
        return "fullscreen", None
    if "theater" in text_lower or "theatre" in text_lower:
        return "theater_mode", None
    
    # Captions
    if "caption" in text_lower or "subtitle" in text_lower:
        return "captions", None
    
    return None, None
