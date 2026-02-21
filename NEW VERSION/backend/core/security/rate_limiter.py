# BACKEND/core/security/rate_limiter.py
import time
from collections import defaultdict
from threading import Lock

class RateLimiter:
    """
    Security rate limiter to prevent spam and abuse
    """
    
    def __init__(self):
        self.last_input_time = 0.0
        self.last_gesture_toggle_time = 0.0
        self.last_tts_time = 0.0
        self.command_history = {}  # cmd -> last_time
        self._lock = Lock()
        
        # Configuration (in seconds)
        self.MIN_INPUT_INTERVAL = 0.3      # Min 300ms between inputs
        self.MIN_GESTURE_INTERVAL = 1.0    # Min 1 second between gesture toggles
        self.MIN_TTS_INTERVAL = 0.1        # Min 100ms between TTS calls
        self.DUPLICATE_TIMEOUT = 3.0       # Reject same command within 3 seconds
        self.MAX_COMMANDS_PER_MINUTE = 60  # Max 60 commands per minute
        
    def check_input_rate(self):
        """Check if input rate is OK"""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_input_time
            
            if elapsed < self.MIN_INPUT_INTERVAL:
                return False, f"Too fast! Wait {self.MIN_INPUT_INTERVAL - elapsed:.2f}s"
            
            self.last_input_time = now
            return True, "OK"
    
    def check_duplicate(self, text: str):
        """Check if command is duplicate of recent command"""
        with self._lock:
            now = time.time()
            text_lower = text.lower().strip()
            
            # Check if same command was sent recently
            if text_lower in self.command_history:
                last_time = self.command_history[text_lower]
                elapsed = now - last_time
                
                if elapsed < self.DUPLICATE_TIMEOUT:
                    return False, f"Command already sent {elapsed:.1f}s ago. Wait {self.DUPLICATE_TIMEOUT - elapsed:.1f}s"
            
            # Update command history
            self.command_history[text_lower] = now
            
            # Clean old entries (keep only last 5 minutes)
            cutoff = now - 300
            self.command_history = {
                k: v for k, v in self.command_history.items() 
                if v > cutoff
            }
            
            return True, "OK"
    
    def check_gesture_toggle_rate(self):
        """Check if gesture mode toggle is happening too frequently"""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_gesture_toggle_time
            
            if elapsed < self.MIN_GESTURE_INTERVAL:
                return False, f"Gesture toggle too fast! Wait {self.MIN_GESTURE_INTERVAL - elapsed:.2f}s"
            
            self.last_gesture_toggle_time = now
            return True, "OK"
    
    def check_tts_rate(self):
        """Check if TTS output rate is OK (prevent overlapping speech)"""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_tts_time
            
            if elapsed < self.MIN_TTS_INTERVAL:
                return False
            
            self.last_tts_time = now
            return True
    
    def reset(self):
        """Reset all counters (for testing)"""
        with self._lock:
            self.last_input_time = 0.0
            self.last_gesture_toggle_time = 0.0
            self.last_tts_time = 0.0
            self.command_history = {}
