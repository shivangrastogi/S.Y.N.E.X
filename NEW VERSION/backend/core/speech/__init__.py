# Path: d:\New folder (2) - JARVIS\backend\core\speech\__init__.py
"""
Speech Module
Handles speech-to-text (listening) and text-to-speech (speaking) functionality.
"""

from .listener import ListenEngine
from .speaker import SpeakEngine

__all__ = ['ListenEngine', 'SpeakEngine']
