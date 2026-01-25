# BACKEND/automations/youtube/yt_exceptions.py
"""Custom exceptions for YouTube automation"""

class YouTubeAutomationError(Exception):
    """Base exception for YouTube automation"""
    pass

class YouTubeSearchError(YouTubeAutomationError):
    """Exception for YouTube search failures"""
    pass

class YouTubePlayerError(YouTubeAutomationError):
    """Exception for YouTube player control failures"""
    pass

class YouTubeSessionError(YouTubeAutomationError):
    """Exception for YouTube session management failures"""
    pass

class YouTubeQueryError(YouTubeAutomationError):
    """Exception for YouTube query parsing failures"""
    pass
