# main.py
# ================================
# SYNEX – MAIN ENTRY (PRODUCTION)
# ================================

import os
import sys
import threading
import traceback
import queue
import time
import re
from colorama import Fore, init

from BACKEND.core.brain.intent_classifier import IntentClassifier
from BACKEND.core.brain.action_router import ActionRouter
from BACKEND.core.brain.state_manager import StateManager, AudioState
from BACKEND.core.speaker.speech_service import SpeechService
from BACKEND.core.security.rate_limiter import RateLimiter
from BACKEND.automations.battery.battery_monitor import BatteryMonitor, BatteryMonitorConfig
from BACKEND.automations.battery.battery_config import get_battery_settings
from BACKEND.gestures.gesture_manager import GestureManager
from BACKEND.mobile.mobile import MobileServer
from BACKEND.core.listener.voice_listener import VoiceListener
import cv2

# ================================
# CONFIG
# ================================
TEST_MODE = True  # True = text testing | False = voice mode
INTENT_CONFIDENCE_THRESHOLD = 0.55

init(autoreset=True)


def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


def setup_error_handling():
    """Setup global exception handling"""

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        print(Fore.RED + "\n╔════════════════════════════════════════╗")
        print(Fore.RED + "║           CRITICAL ERROR              ║")
        print(Fore.RED + "╚════════════════════════════════════════╝")
        print(Fore.RED + f"\nError Type: {exc_type.__name__}")
        print(Fore.RED + f"Error Message: {exc_value}")

        # Print traceback
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        for line in tb_lines:
            print(Fore.RED + line.strip())

        print(Fore.YELLOW + "\n🔄 Attempting to recover...")

    sys.excepthook = handle_exception


class Synex:
    """
    Synex Core Runtime
    ML-first, automation-safe, production-ready
    """

    def __init__(self):
        setup_error_handling()
        clear_console()
        print(Fore.CYAN + "╔════════════════════════════════════════╗")
        print(Fore.CYAN + "║           SYNEX v1.0.0                ║")
        print(Fore.CYAN + "║    AI Assistant Initializing...       ║")
        print(Fore.CYAN + "╚════════════════════════════════════════╝\n")

        try:
            # ------------------------
            # Core systems
            # ------------------------
            print(Fore.CYAN + "🔧 Loading core systems...")
            self.state_manager = StateManager()
            self.speech = SpeechService(self.state_manager)
            self.intent_classifier = IntentClassifier()
            self.router = ActionRouter(self.speech)
            self.rate_limiter = RateLimiter()  # Security rate limiter
            self.mobile_server = MobileServer(self)
            self.mobile_server.start()

            # ------------------------
            # Response callback (GUI)
            # ------------------------
            self.response_callback = None
            self.heard_callback = None
            self.gesture_status_callback = None
            self.gesture_frame_callback = None
            self.gesture_event_callback = None

            # ------------------------
            # Input queue (GUI mode)
            # ------------------------
            self.input_queue = queue.Queue()

            from BACKEND.mobile.ws_server import MobileWebSocketServer
            import asyncio

            self.ws_server = MobileWebSocketServer(self)
            threading.Thread(
                target=lambda: asyncio.run(self.ws_server.start()),
                daemon=True
            ).start()

            # ------------------------
            # Runtime flags
            # ------------------------
            self.awake = False
            self.gesture_active = False
            self.gesture_allowed = False  # Toggle: whether gesture mode is allowed (OFF by default)
            self.gesture_manager = None
            self.gesture_thread = None
            self._gesture_lock = threading.Lock()

            # ------------------------
            # Voice control flags (GUI toggle)
            # ------------------------
            self.voice_listening = False
            self.voice_stop_event = threading.Event()
            self.voice_thread = None
            self.listener = VoiceListener(self.state_manager)
            self._last_mic_busy_at = 0.0

            # ------------------------
            # 🔋 Battery monitor (background)
            # ------------------------
            print(Fore.CYAN + "🔋 Starting battery monitor...")
            battery_settings = get_battery_settings()
            battery_cfg = BatteryMonitorConfig(
                critical_threshold=battery_settings.config.critical_threshold,
                low_threshold=battery_settings.config.low_threshold,
                full_threshold=battery_settings.config.full_threshold,
                plug_cooldown=battery_settings.config.plug_cooldown,
                level_cooldown=battery_settings.config.level_cooldown,
                idle_only=battery_settings.config.idle_only,
                max_pending=battery_settings.config.max_pending_alerts,
            )
            self.battery_monitor = BatteryMonitor(
                self.speech,
                interval=battery_settings.config.monitor_interval,
                config=battery_cfg,
                settings=battery_settings,
            )
            self.battery_monitor.start()

            # ------------------------
            # 🎙 Voice listener (toggle from GUI)
            # ------------------------
            print(Fore.CYAN + "🎙 Voice listener ready (toggle from GUI)")

            print(Fore.GREEN + "\n✅ System ready")
            print(
                Fore.YELLOW +
                ("💬 TEXT MODE ENABLED\n" if TEST_MODE else "🎙 VOICE MODE ENABLED\n")
            )

            # ------------------------
            # ✋ Gesture listener (starts when needed)
            # ------------------------
            # Don't initialize gesture manager on startup
            # It will be created when user toggles ON or uses voice command

            print(Fore.CYAN + "═" * 50)
            print(Fore.WHITE + "Type 'exit' to quit | 'help' for commands")
            print(Fore.CYAN + "═" * 50 + "\n")

        except Exception as e:
            print(Fore.RED + f"❌ Initialization failed: {e}")
            print(Fore.YELLOW + "Attempting to start with minimal functionality...")
            # Continue with minimal setup if possible

    # ================================
    # MAIN LOOP
    # ================================
    def run(self):
        try:
            while True:
                try:
                    self.state_manager.set_state(AudioState.LISTENING)
                    # ------------------------
                    # INPUT
                    # ------------------------
                    if os.getenv("SYNEX_INPUT_MODE", "console").lower() == "queue":
                        item = self.input_queue.get()
                        if item is None:
                            print(Fore.YELLOW + "👋 Goodbye!")
                            break

                        if isinstance(item, dict):
                            text = self._clean_text(item.get("text", ""))
                            source = item.get("source", "text")
                        else:
                            text = self._clean_text(str(item))
                            source = "text"

                        if source == "text":
                            if text.lower() == 'exit':
                                print(Fore.YELLOW + "👋 Goodbye!")
                                break
                            if text.lower() == 'help':
                                self._show_help()
                                continue
                    else:
                        text = self._clean_text(input(Fore.CYAN + "You: "))
                        source = "text"
                        if text.lower() == 'exit':
                            print(Fore.YELLOW + "👋 Goodbye!")
                            break
                        if text.lower() == 'help':
                            self._show_help()
                            continue

                    if not text:
                        continue

                    print(Fore.YELLOW + f"👤 Input: {text}")
                    text_lower = text.lower()

                    # ========================
                    # ⚔️  SECURITY: RATE LIMITING
                    # ========================
                    # Check input rate
                    ok, reason = self.rate_limiter.check_input_rate()
                    if not ok:
                        print(Fore.MAGENTA + f"🛡️  Rate limit: {reason}")
                        self.speech.speak("Please wait before sending another command")
                        self.state_manager.set_state(AudioState.IDLE)
                        continue
                    
                    # Check for duplicate commands
                    ok, reason = self.rate_limiter.check_duplicate(text)
                    if not ok:
                        print(Fore.MAGENTA + f"🛡️  Duplicate command: {reason}")
                        self.speech.speak("You just sent that command")
                        self.state_manager.set_state(AudioState.IDLE)
                        continue

                    battery_intent = self._detect_battery_intent(text_lower)
                    browser_intent, browser_payload = self._detect_browser_intent(text_lower)

                    # ------------------------
                    # WAKE WORD (VOICE INPUT)
                    # ------------------------
                    if source == "voice" and not self.awake:
                        if self._is_wake_word(text_lower):
                            self.awake = True
                            greeting = "Hello, how can I help?"
                            print(Fore.GREEN + f"🤖 Response: {greeting}")
                            if self.response_callback:
                                self.response_callback(greeting)
                            self.speech.speak(greeting)
                        continue

                    # ------------------------
                    # INTENT CLASSIFICATION
                    # ------------------------
                    self.state_manager.set_state(AudioState.THINKING)

                    # ------------------------
                    # GESTURE MODE (VOICE OVERRIDE)
                    # ------------------------
                    gesture_cmd = self._parse_gesture_command(text_lower)
                    if gesture_cmd:
                        # Rate limit gesture mode toggles
                        ok, reason = self.rate_limiter.check_gesture_toggle_rate()
                        if not ok:
                            print(Fore.MAGENTA + f"🛡️  Gesture rate limit: {reason}")
                            self.speech.speak("Gesture mode is changing too fast")
                            self.state_manager.set_state(AudioState.IDLE)
                            continue
                        
                        if gesture_cmd == "on":
                            self._start_gesture_mode(source="voice")
                            self.state_manager.set_state(AudioState.IDLE)
                            continue
                        if gesture_cmd == "off":
                            self._stop_gesture_mode(source="voice")
                            self.state_manager.set_state(AudioState.IDLE)
                            continue
                        if gesture_cmd == "toggle":
                            self._toggle_gesture_mode(source="voice")
                            self.state_manager.set_state(AudioState.IDLE)
                            continue

                    if browser_intent:
                        intent, confidence = browser_intent, 1.0
                    elif battery_intent:
                        intent, confidence = battery_intent, 1.0
                    else:
                        intent, confidence = self.intent_classifier.predict(text_lower)

                    print(
                        Fore.MAGENTA +
                        f"🧠 Intent: {intent} (Confidence: {confidence:.2f})"
                    )

                    # ------------------------
                    # LOW CONFIDENCE GUARD
                    # ------------------------
                    if confidence < INTENT_CONFIDENCE_THRESHOLD:
                        low_conf_response = "I'm not sure I understood that."
                        print(Fore.YELLOW + f"⚠️  Low confidence ({confidence:.2f}) - asking for clarification")
                        if self.response_callback:
                            self.response_callback(low_conf_response)
                        self.speech.speak(low_conf_response)
                        self.state_manager.set_state(AudioState.IDLE)
                        continue

                    # ------------------------
                    # ROUTE ACTION
                    # ------------------------
                    if browser_intent:
                        result = self.router.handle(intent, browser_payload or text_lower)
                    else:
                        result = self.router.handle(intent, text_lower)

                    # ------------------------
                    # GESTURE MODE
                    # ------------------------
                    if result == "START_GESTURE":
                        self._toggle_gesture_mode(source="voice")
                        continue

                    # ------------------------
                    # SLEEP
                    # ------------------------
                    if result == "SLEEP":
                        self.awake = False
                        sleep_response = "Going to sleep."
                        print(Fore.GREEN + f"🤖 Response: {sleep_response}")
                        if self.response_callback:
                            self.response_callback(sleep_response)
                        self.speech.speak(sleep_response)
                        continue

                    # ------------------------
                    # SPEAK RESULT
                    # ------------------------
                    # Always generate and speak a response
                    result_text = None
                    if result is not None:
                        result_text = str(result).strip()
                    
                    if result_text:
                        print(Fore.GREEN + f"🤖 Response: {result_text}")
                        # Send response to UI callback
                        if self.response_callback:
                            self.response_callback(result_text)
                        # ALWAYS speak the response regardless of input source
                        self.speech.speak(result_text)
                    else:
                        # If no response, provide a fallback response
                        fallback = "I've completed the task. Is there anything else you need?"
                        print(Fore.GREEN + f"🤖 Response: {fallback}")
                        if self.response_callback:
                            self.response_callback(fallback)
                        self.speech.speak(fallback)

                    self.state_manager.set_state(AudioState.IDLE)

                except KeyboardInterrupt:
                    print(Fore.YELLOW + "\n👋 Shutting down gracefully...")
                    break

                except Exception as e:
                    print(Fore.RED + f"[ERROR] {e}")
                    traceback.print_exc()
                    error_response = "I encountered an error. Please try again."
                    if self.response_callback:
                        self.response_callback(error_response)
                    self.speech.speak(error_response)
                    self.state_manager.set_state(AudioState.IDLE)
        finally:
            self._cleanup()

    def _show_help(self):
        """Show available commands"""
        print(Fore.CYAN + "\n📚 Available Commands:")
        print(Fore.WHITE + "─" * 40)
        print(Fore.YELLOW + "WhatsApp:")
        print(Fore.WHITE + "  • Send a message to [contact] saying [message]")
        print(Fore.WHITE + "  • Send WhatsApp message to [contact] that [message]")
        print(Fore.YELLOW + "\nWeather:")
        print(Fore.WHITE + "  • What's the weather in [city]?")
        print(Fore.WHITE + "  • Temperature in [city]")
        print(Fore.YELLOW + "\nYouTube:")
        print(Fore.WHITE + "  • Open YouTube")
        print(Fore.WHITE + "  • Search [query] on YouTube")
        print(Fore.YELLOW + "\nGoogle:")
        print(Fore.WHITE + "  • Search [query] on Google")
        print(Fore.WHITE + "  • Open [website]")
        print(Fore.YELLOW + "\nSystem:")
        print(Fore.WHITE + "  • Battery status")
        print(Fore.WHITE + "  • Check internet speed")
        print(Fore.WHITE + "  • Gesture mode")
        print(Fore.WHITE + "  • Goodbye (sleep)")
        print(Fore.CYAN + "\nType 'exit' to quit\n")

    def _cleanup(self):
        """Cleanup resources before exit"""
        print(Fore.YELLOW + "Cleaning up resources...")
        if hasattr(self, 'battery_monitor'):
            self.battery_monitor.stop()
        if hasattr(self, 'gesture_manager') and self.gesture_manager:
            self.gesture_manager.stop()
        if hasattr(self, 'speech') and self.speech:
            try:
                self.speech.shutdown()
            except Exception:
                pass

    def submit_text(self, text: str):
        """Receive text input from GUI and enqueue it for processing."""
        if not hasattr(self, "input_queue"):
            self.input_queue = queue.Queue()
        if text is None:
            return
        self.input_queue.put({"text": self._clean_text(text), "source": "text"})

    def safe_speak(self, text: str):
        """Speak with rate limiting to prevent spam"""
        if not self.rate_limiter.check_tts_rate():
            # TTS rate limited - drop this speech
            return
        self.speech.speak(text)

    def configure_rate_limits(self, min_input_interval=None, min_gesture_interval=None, duplicate_timeout=None):
        """Configure rate limiter parameters"""
        if min_input_interval is not None:
            self.rate_limiter.MIN_INPUT_INTERVAL = min_input_interval
        if min_gesture_interval is not None:
            self.rate_limiter.MIN_GESTURE_INTERVAL = min_gesture_interval
        if duplicate_timeout is not None:
            self.rate_limiter.DUPLICATE_TIMEOUT = duplicate_timeout

    def get_rate_limit_status(self):
        """Get current rate limiter configuration"""
        return {
            "min_input_interval": self.rate_limiter.MIN_INPUT_INTERVAL,
            "min_gesture_interval": self.rate_limiter.MIN_GESTURE_INTERVAL,
            "duplicate_timeout": self.rate_limiter.DUPLICATE_TIMEOUT,
            "min_tts_interval": self.rate_limiter.MIN_TTS_INTERVAL,
        }

    def set_gesture_allowed(self, allowed: bool):
        """
        Set whether gesture mode is allowed by UI toggle
        True = gesture can be activated (toggle is ON)
        False = gesture is blocked (toggle is OFF) - stops camera completely
        Voice commands override this
        """
        with self._gesture_lock:
            self.gesture_allowed = allowed
            # If toggle is turned OFF, completely stop gesture and camera
            if not allowed:
                self.gesture_active = False
                # Stop the gesture thread and cleanup camera
                if self.gesture_manager:
                    self.gesture_manager.stop()
                    # Wait for thread to finish
                    if self.gesture_thread and self.gesture_thread.is_alive():
                        self.gesture_thread.join(timeout=2.0)
                # Reset gesture manager so it's recreated when needed
                self.gesture_manager = None
                self.gesture_thread = None
                self._emit_gesture_status(False, "INACTIVE", 0.0)

    def set_response_callback(self, callback):
        """Set callback for UI response updates."""
        self.response_callback = callback

    def set_heard_callback(self, callback):
        """Set callback for UI heard text updates."""
        self.heard_callback = callback

    def set_gesture_status_callback(self, callback):
        """Set callback for gesture mode status updates."""
        self.gesture_status_callback = callback

    def set_gesture_frame_callback(self, callback):
        """Set callback for gesture camera preview frames."""
        self.gesture_frame_callback = callback

    def set_gesture_event_callback(self, callback):
        """Set callback for gesture event updates."""
        self.gesture_event_callback = callback

    def start_voice_listening(self):
        if self.voice_listening and self.voice_thread and self.voice_thread.is_alive():
            return
        self.voice_listening = True
        self.voice_stop_event.clear()
        self.listener.start_listening()
        self.voice_thread = threading.Thread(target=self._voice_loop, daemon=True)
        self.voice_thread.start()

    def stop_voice_listening(self):
        if not self.voice_listening:
            return
        self.voice_listening = False
        self.voice_stop_event.set()
        self.awake = False
        if hasattr(self, "listener"):
            try:
                self.listener.stop()
            except Exception:
                pass

    def _voice_loop(self):
        while not self.voice_stop_event.is_set():
            try:
                text = self.listener.listen_once()
                if text == "__MIC_BUSY__":
                    now = time.time()
                    if now - self._last_mic_busy_at > 5:
                        self._last_mic_busy_at = now
                        self.input_queue.put({
                            "text": "Microphone is busy. Please close other apps using it.",
                            "source": "text"
                        })
                    time.sleep(1.0)
                    continue
                if not text:
                    continue
                cleaned = self._clean_text(text)
                if not cleaned:
                    continue
                print(Fore.LIGHTCYAN_EX + f"🎧 Heard (clean): {cleaned}")
                if self.heard_callback:
                    self.heard_callback(cleaned)
                self.input_queue.put({"text": cleaned, "source": "voice"})
            except Exception as e:
                print(Fore.RED + f"[VOICE LOOP ERROR] {e}")
                time.sleep(0.5)
                continue
        self.voice_listening = False

    def _clean_text(self, text: str) -> str:
        if text is None:
            return ""
        cleaned = " ".join(str(text).strip().split())
        cleaned = self._normalize_hinglish(cleaned)
        return " ".join(cleaned.strip().split())

    def _is_wake_word(self, text_lower: str) -> bool:
        if not text_lower:
            return False
        wake_phrases = [
            "jarvis",
            "jarvish",
            "jaarvis",
            "jervis",
            "synex",
            "wake up",
            "wakeup",
            "wake",
            "vek ap",
            "vek up",
            "वेक अप",
            "वेक",
            "जागो",
            "जाग जाओ",
        ]
        return any(phrase in text_lower for phrase in wake_phrases)

    def _normalize_hinglish(self, text: str) -> str:
        if not text:
            return ""
        t = text.lower()

        phrase_rules = [
            (r"\b(open|kholo|khol)\s+(kro|karo|kar do|kr do|krdo|kardo)\b", "open"),
            (r"\b(search|dhundho|dhundo|khojo)\s+(kro|karo|kar do|kr do|krdo|kardo)\b", "search"),
            (r"\b(play|chalao|bajao|bjao)\s+(kro|karo|kar do|kr do|krdo|kardo)\b", "play"),
            (r"\b(close|band)\s+(kro|karo|kar do|kr do|krdo|kardo)\b", "close"),
            (r"\b(send|bhejo|bhej do)\b", "send"),
            (r"\b(batao|tell)\b", "tell"),
            (r"\b(dikhao|dikhaao|dikhayo|show)\b", "show"),
        ]

        for pattern, repl in phrase_rules:
            t = re.sub(pattern, repl, t, flags=re.IGNORECASE)

        word_rules = {
            "kholo": "open",
            "khol": "open",
            "band": "close",
            "bnd": "close",
            "dhundho": "search",
            "dhundo": "search",
            "khojo": "search",
            "chalao": "play",
            "bajao": "play",
            "bjao": "play",
            "bhejo": "send",
            "batao": "tell",
            "dikhao": "show",
            "gaana": "song",
            "gaane": "songs",
        }

        tokens = [word_rules.get(tok, tok) for tok in t.split()]
        t = " ".join(tokens)

        t = re.sub(r"\b(kro|karo|kar do|kr do|krdo|kardo|krna|karna)\b", "", t, flags=re.IGNORECASE)
        return t

    def _detect_battery_intent(self, text_lower: str):
        if not text_lower:
            return None
        if any(word in text_lower for word in ["battery", "charge", "charging", "charger", "power"]):
            if any(word in text_lower for word in ["plug", "plugged", "plugged in", "on charge", "charging", "charger"]):
                return "check_battery_plug"
            return "check_battery_percentage"
        return None

    def _detect_browser_intent(self, text_lower: str):
        if not text_lower:
            return None, None

        # search google
        if any(w in text_lower for w in ["search", "google"]):
            query = (
                text_lower
                .replace("search", "", 1)
                .replace("on google", "")
                .replace("google", "", 1)
                .strip()
            )
            if query:
                return "google_search", query

        # open website
        if "open" in text_lower or "website" in text_lower:
            name = (
                text_lower
                .replace("open", "", 1)
                .replace("website", "", 1)
                .strip()
            )
            if name:
                return "open_item", name

        # close tab/window
        if "close tab" in text_lower or "close" in text_lower:
            return "close_item", None

        # navigation / tabs / scroll / refresh
        if "new tab" in text_lower or "open new tab" in text_lower:
            return "browser_new_tab", None
        if "next tab" in text_lower:
            return "browser_next_tab", None
        if "previous tab" in text_lower or "prev tab" in text_lower:
            return "browser_previous_tab", None
        if "back" in text_lower:
            return "browser_back", None
        if "forward" in text_lower:
            return "browser_forward", None
        if "refresh" in text_lower or "reload" in text_lower:
            return "browser_refresh", None
        if "scroll down" in text_lower:
            return "browser_scroll_down", None
        if "scroll up" in text_lower:
            return "browser_scroll_up", None
        if "scroll top" in text_lower:
            return "browser_scroll_top", None
        if "scroll bottom" in text_lower:
            return "browser_scroll_bottom", None

        return None, None

    def shutdown(self):
        """Shutdown backend services and stop the main loop."""
        self.stop_voice_listening()
        if hasattr(self, "input_queue"):
            self.input_queue.put(None)

    # ================================
    # GESTURE MODE
    # ================================
    def _parse_gesture_command(self, text_lower: str):
        if "gesture" not in text_lower:
            return None

        on_keywords = ["on", "enable", "start", "activate"]
        off_keywords = ["off", "disable", "stop", "deactivate"]

        if any(k in text_lower for k in on_keywords):
            return "on"
        if any(k in text_lower for k in off_keywords):
            return "off"
        return "toggle"

    def _ensure_gesture_manager(self):
        if self.gesture_manager and self.gesture_thread and self.gesture_thread.is_alive():
            return

        self.gesture_manager = GestureManager(
            on_exit=self._on_gesture_exit,
            on_toggle=lambda: self._toggle_gesture_mode(source="gesture"),
            on_status=self._emit_gesture_status,
            on_frame=self._emit_gesture_frame,
            on_event=self._emit_gesture_event,
            active=False,
            show_ui=False,
            toggle_hold_seconds=2.0
        )
        self.gesture_thread = threading.Thread(
            target=self.gesture_manager.run,
            daemon=True
        )
        self.gesture_thread.start()

    def _start_gesture_mode(self, source="voice"):
        with self._gesture_lock:
            self._ensure_gesture_manager()
            if self.gesture_active:
                if source == "voice":
                    self.speech.speak("Gesture mode is already active.")
                return

            self.gesture_active = True
            self.gesture_allowed = True  # Voice command overrides toggle setting
            self.gesture_manager.set_active(True, show_ui=False)
            self._emit_gesture_status(self.gesture_active, "ACTIVE", 0.0)
            if source == "voice":
                self.speech.speak("Gesture mode activated.")

    def _stop_gesture_mode(self, source="voice"):
        with self._gesture_lock:
            if not self.gesture_active:
                if source == "voice":
                    self.speech.speak("Gesture mode is already disabled.")
                return

            self.gesture_active = False
            if self.gesture_manager:
                self.gesture_manager.set_active(False, show_ui=False)
            self._emit_gesture_status(self.gesture_active, "INACTIVE", 0.0)
            if source == "voice":
                self.speech.speak("Gesture mode disabled.")
            # If toggle is OFF, keep gesture_allowed as False
            if not self.gesture_allowed:
                self.gesture_active = False

    def _toggle_gesture_mode(self, source="voice"):
        if self.gesture_active:
            self._stop_gesture_mode(source=source)
        else:
            self._start_gesture_mode(source=source)

    def _on_gesture_exit(self):
        self.gesture_active = False
        self._emit_gesture_status(self.gesture_active, "INACTIVE", 0.0)

    def _emit_gesture_status(self, active: bool, gesture: str, fps: float):
        if self.gesture_status_callback:
            try:
                self.gesture_status_callback(active, gesture, fps)
            except Exception:
                pass

    def _emit_gesture_frame(self, frame):
        if self.gesture_frame_callback and frame is not None:
            try:
                # Encode frame as JPEG bytes to avoid Qt memoryview issues
                ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    self.gesture_frame_callback(buf.tobytes())
                else:
                    # Fallback: emit raw frame
                    self.gesture_frame_callback(frame)
            except Exception:
                # Fallback on any error
                try:
                    self.gesture_frame_callback(frame)
                except Exception:
                    pass

    def _emit_gesture_event(self, gesture: str):
        if self.gesture_event_callback:
            try:
                self.gesture_event_callback(gesture)
            except Exception:
                pass


# ================================
# ENTRY POINT
# ================================
if __name__ == "__main__":
    try:
        Synex().run()
    except Exception as e:
        print(Fore.RED + f"Fatal error: {e}")
        traceback.print_exc()
        input(Fore.YELLOW + "Press Enter to exit...")