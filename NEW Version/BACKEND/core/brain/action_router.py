# BACKEND/core/brain/action_router.py
import traceback
import time
from datetime import datetime
from BACKEND.automations.battery.battery_controller import BatteryController
from BACKEND.automations.network.check_ip import check_ip_address
from BACKEND.automations.network.check_speed import check_internet_speed

from BACKEND.automations.youtube.yt_controller import YouTubeController

from BACKEND.automations.google.google_controller import GoogleController
from BACKEND.automations.google.google_session import GoogleBlockedError

from BACKEND.automations.weather.weather_controller import WeatherController

from BACKEND.automations.whatsapp.whatsapp_controller import WhatsAppController
from BACKEND.automations.whatsapp.message_parser import parse_whatsapp_message


class ActionRouter:
    """
    ML-first Action Router
    intent → automation execution
    """

    def __init__(self, speaker):
        self.speaker = speaker
        self.battery = BatteryController(speaker)
        self.google = GoogleController()
        self.weather = WeatherController()
        self.whatsapp_controller = None  # Lazy initialization
        self.youtube_controller = None  # Lazy initialization

    def _get_youtube_controller(self):
        """Lazy initialization of YouTube controller"""
        if self.youtube_controller is None:
            try:
                self.youtube_controller = YouTubeController()
            except Exception as e:
                print(f"❌ YouTube controller initialization failed: {e}")
                raise
        return self.youtube_controller

    def _get_whatsapp_controller(self):
        """Lazy initialization of WhatsApp controller"""
        if self.whatsapp_controller is None:
            try:
                self.whatsapp_controller = WhatsAppController()
            except Exception as e:
                print(f"❌ WhatsApp controller initialization failed: {e}")
                raise
        return self.whatsapp_controller

    def handle(self, intent: str, text: str):
        print(f"🎯 Handling intent: {intent}")

        # Intent aliases from model labels
        intent_aliases = {
            "send_whatsapp_message": "whatsapp_send_message",
        }
        intent = intent_aliases.get(intent, intent)

        try:
            # =================================================
            # 🎥 YOUTUBE (ML-DRIVEN WITH RETRY LOGIC)
            # =================================================
            if intent in ["youtube_play", "youtube_search", "youtube_control"]:
                return self._handle_youtube(intent, text)

            # =================================================
            # 💬 WHATSAPP (ML-DRIVEN) - UPDATED WITH RETRY LOGIC
            # =================================================
            if intent == "whatsapp_send_message":
                return self._handle_whatsapp_message(text)

            # =================================================
            # 🌦 WEATHER (ML-DRIVEN, SPEAKABLE)
            # =================================================
            weather_response = self.weather.handle(intent, text)
            if weather_response:
                return weather_response

            # =================================================
            # 🔋 BATTERY
            # =================================================
            battery_response = self.battery.handle(intent)
            if battery_response:
                return battery_response

            # =================================================
            # 🌐 GOOGLE AUTOMATION (ML ONLY)
            # =================================================
            google_response = self._handle_google_automation(intent, text)
            if google_response is not None:
                return google_response

            # =================================================
            # 🌐 NETWORK
            # =================================================
            network_response = self._handle_network_automation(intent)
            if network_response:
                return network_response

            # =================================================
            # ✋ GESTURE MODE
            # =================================================
            if intent == "gesture_mode_control":
                return "START_GESTURE"

            # =================================================
            # 👋 SYSTEM
            # =================================================
            if intent == "check_time":
                now = datetime.now().strftime("%I:%M %p")
                return f"The time is {now}."

            if intent == "schedule_event":
                return "Calendar scheduling is not configured yet."

            if intent == "user_login_setup":
                return "Login setup is not configured yet."

            if intent == "refresh_contacts":
                return "Contacts refreshed."

            if intent == "open_item":
                name = (
                    text.replace("open", "", 1)
                    .replace("launch", "", 1)
                    .strip()
                )
                if not name:
                    return "What should I open?"
                try:
                    self.google.open_site(name)
                    return f"Opening {name}."
                except Exception:
                    return "I couldn't open that item."

            if intent == "close_item":
                try:
                    self.google.close_tab()
                    return "Closed the active tab."
                except Exception:
                    return "I couldn't close that item."

            if intent == "goodbye":
                return "SLEEP"

            if intent == "greet":
                return "Hello! How can I help you today?"

            return "Sorry, I didn't understand that command."

        except Exception as e:
            print(f"❌ ActionRouter error: {e}")
            traceback.print_exc()
            return f"I encountered an error: {str(e)}"

    def _handle_youtube(self, intent: str, text: str):
        """Handle YouTube automation with retry logic"""
        try:
            # Get YouTube controller (lazy init)
            yt = self._get_youtube_controller()
            
            # Delegate to controller's handle method
            return yt.handle(intent, text)
        
        except Exception as e:
            error_msg = str(e)
            print(f"❌ YouTube error: {error_msg}")
            return f"YouTube automation failed: {error_msg}"

    def _handle_whatsapp_message(self, text: str):
        """Handle WhatsApp message sending with retry logic"""
        max_retries = 2

        for attempt in range(max_retries):
            try:
                # Parse message
                contact, message = parse_whatsapp_message(text)

                if not contact:
                    return "I couldn't understand who to message. Please say something like 'Send a message to John saying Hello'"

                if not message:
                    return f"What would you like me to send to {contact}?"

                print(f"📱 Attempt {attempt + 1}: Sending to {contact}")

                # Get WhatsApp controller (may trigger detection)
                wa = self._get_whatsapp_controller()

                # Send message
                wa.send_message(contact, message)

                return f"Message sent to {contact} successfully."

            except Exception as e:
                error_msg = str(e)
                print(f"❌ WhatsApp attempt {attempt + 1} failed: {error_msg}")

                if attempt == max_retries - 1:
                    # Last attempt failed
                    if "desktop" in error_msg.lower() and "web" in error_msg.lower():
                        return "I couldn't access WhatsApp. Please make sure WhatsApp Desktop is installed or try using WhatsApp Web directly."
                    return f"Failed to send message after {max_retries} attempts: {error_msg}"

                # Wait before retry
                print(f"🔄 Retrying in 2 seconds...")
                time.sleep(2)

                # Reset controller for fresh detection
                self.whatsapp_controller = None

    def _handle_google_automation(self, intent: str, text: str):
        """Handle Google-related automations"""
        try:
            if intent == "google_search":
                query = (
                    text.replace("search", "", 1)
                    .replace("google", "", 1)
                    .strip()
                )
                if not query:
                    return "What should I search on Google?"

                self.google.search(query)
                return f"Searching '{query}' on Google."

            if intent == "google_open_site":
                name = (
                    text.replace("open", "", 1)
                    .replace("website", "", 1)
                    .strip()
                )
                if not name:
                    return "Which website should I open?"

                self.google.open_site(name)
                return f"Opening {name}."

            if intent == "browser_new_tab":
                self.google.new_tab()
                return "Opened a new tab."

            if intent == "browser_close_tab":
                self.google.close_tab()
                return "Closed the active tab."

            if intent == "browser_next_tab":
                self.google.next_tab()
                return "Switched to the next tab."

            if intent == "browser_previous_tab":
                self.google.previous_tab()
                return "Switched to the previous tab."

            if intent == "browser_back":
                self.google.back()
                return "Went back."

            if intent == "browser_forward":
                self.google.forward()
                return "Went forward."

            if intent == "browser_refresh":
                self.google.refresh()
                return "Refreshed the page."

            if intent == "browser_scroll_down":
                self.google.scroll_down()
                return "Scrolled down."

            if intent == "browser_scroll_up":
                self.google.scroll_up()
                return "Scrolled up."

            if intent == "browser_scroll_top":
                self.google.scroll_top()
                return "Scrolled to the top."

            if intent == "browser_scroll_bottom":
                self.google.scroll_bottom()
                return "Scrolled to the bottom."

            # Handle other Google intents
            google_actions = {
                "google_scroll_down": (self.google.scroll_down, None),
                "google_scroll_up": (self.google.scroll_up, None),
                "google_scroll_top": (self.google.scroll_top, None),
                "google_scroll_bottom": (self.google.scroll_bottom, None),
                "google_new_tab": (self.google.new_tab, None),
                "google_close_tab": (self.google.close_tab, None),
                "google_next_tab": (self.google.next_tab, None),
                "google_previous_tab": (self.google.previous_tab, None),
                "google_back": (self.google.back, None),
                "google_forward": (self.google.forward, None),
                "google_refresh": (self.google.refresh, None),
            }

            if intent in google_actions:
                action, response = google_actions[intent]
                action()
                return response

        except GoogleBlockedError:
            return (
                "Google has temporarily blocked automation. "
                "Please solve the captcha and try again."
            )
        except Exception as e:
            return f"Google automation failed: {str(e)}"

        return None

    def _handle_network_automation(self, intent: str):
        """Handle network-related queries"""
        try:
            if intent == "check_internet_speed":
                return check_internet_speed(self.speaker)

            if intent == "check_online_status":
                return "You are connected to the internet."

            if intent == "check_ip":
                return check_ip_address()

        except Exception as e:
            return f"Network check failed: {str(e)}"

        return None