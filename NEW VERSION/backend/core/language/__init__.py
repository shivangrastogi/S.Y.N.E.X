# Path: d:\New folder (2) - JARVIS\backend\core\language\__init__.py
"""
Language Module
Handles language detection and processing.
"""

from .detector import detect_language
from .validator import is_meaningful_command

__all__ = ['detect_language', 'is_meaningful_command']
