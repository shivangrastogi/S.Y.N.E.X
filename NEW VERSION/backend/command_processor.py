# Path: d:\New folder (2) - JARVIS\backend\command_processor.py
import os
import sys
import threading
import datetime
from core.speech.speaker import SpeakEngine

from automations.youtube.yt_controller import YouTubeController
from automations.google.google_controller import GoogleController
from automations.whatsapp.whatsapp_controller import WhatsAppController
from automations.calendar.calendar_controller import CalendarController
from automations.calendar.meeting_flow import MeetingFlowHandler
from automations.calendar.management_flow import CalendarManagementFlow

from core.brain.model import JarvisBrain
from core.brain.learner import JarvisLearner
from automations.system.app_launcher import AppLauncher
from automations.weather.weather_controller import WeatherController
from automations.automation_controller import AutomationController
from automations.system.system_controller import SystemController


class CommandProcessor:
    """
    Processes user commands and dispatches them to appropriate automation modules.
    """
    def __init__(self, synex_instance):
        self.synex = synex_instance
        self.speaker = synex_instance.speaker
        
        # Automation Controllers
        self._yt_controller = None
        self._google_controller = None
        self._whatsapp_controller = None
        self._weather_controller = None
        self._automation_controller = None
        self._system_controller = None
        self._calendar_controller = None
        self.meeting_flow = MeetingFlowHandler(auth_callback=self._check_calendar_auth)
        self.management_flow = None # Initialized lazily
        
        # Initialize specialized controllers
        self.app_launcher = AppLauncher()
        
        # Initialize the AI Brain and Learner
        self.brain = JarvisBrain()
        self.learner = JarvisLearner(self.brain)
        self.confidence_threshold = 0.5

    @property
    def yt_controller(self):
        if not self._yt_controller:
            try:
                self._yt_controller = YouTubeController()
            except Exception as e:
                print(f"Failed to load YouTube Controller: {e}")
                return None
        return self._yt_controller

    @property
    def google_controller(self):
        if not self._google_controller:
            try:
                self._google_controller = GoogleController()
            except Exception as e:
                print(f"Failed to load Google Controller: {e}")
                return None
        return self._google_controller

    @property
    def whatsapp_controller(self):
        if not self._whatsapp_controller:
            try:
                self._whatsapp_controller = WhatsAppController()
            except Exception as e:
                print(f"Failed to load WhatsApp Controller: {e}")
                return None
        return self._whatsapp_controller

    @property
    def weather_controller(self):
        if not self._weather_controller:
            try:
                self._weather_controller = WeatherController()
            except Exception as e:
                print(f"Failed to load Weather Controller: {e}")
                return None
        return self._weather_controller

    @property
    def automation_controller(self):
        if not self._automation_controller:
            try:
                self._automation_controller = AutomationController()
            except Exception as e:
                print(f"Failed to load Automation Controller: {e}")
                return None
        return self._automation_controller

    @property
    def calendar_controller(self):
        if not self._calendar_controller:
            try:
                username = getattr(self.synex, "current_user", "default")
                self._calendar_controller = CalendarController(username=username)
            except Exception as e:
                print(f"Failed to load Calendar Controller: {e}")
                return None
        return self._calendar_controller

    def system_controller(self):
        if not self._system_controller:
            try:
                self._system_controller = SystemController()
            except Exception as e:
                print(f"Failed to load System Controller: {e}")
                return None
        return self._system_controller

    def process(self, text, lang="en"):
        """
        Main entry point for command processing.
        """
        text_lower = text.lower()
        
        # 0. Check for Active Conversation Flows (e.g. Meeting Setup)
        if self.meeting_flow.active:
            # Check for cancellation
            if any(w in text_lower for w in ["cancel", "stop", "exit", "never mind", "rehne do", "band karo", "abort", "cancel it", "discard"]):
                self.meeting_flow.reset()
                return "Meeting scheduling cancelled."
            return self._handle_calendar(text)
            
        if self.management_flow and self.management_flow.active:
            # Check for cancellation
            if any(w in text_lower for w in ["cancel", "stop", "exit", "never mind", "rehne do", "band karo", "abort", "cancel it", "discard"]):
                self.management_flow.reset()
                return "Calendar management cancelled."
            return self.management_flow.handle(text)

        # 1. AI Intent Prediction
        intent, confidence = self.brain.predict(text)
        # 0. Pre-processing for specific command patterns (Regex Fallback)
        import re
        if re.search(r"send (whatsapp|email) to", text_lower):
            intent = "whatsapp_message" if "whatsapp" in text_lower else "email_message"
            confidence = 1.0
            print(f"DEBUG: Regex Match - Intent: {intent}")
        elif re.search(r"\b(mute|unmute|silence|quiet|shant|chup)\b", text_lower):
            intent = "volume_mute"
            confidence = 1.0
        elif re.search(r"\b(volume up|increase volume|volume badhao|awaaz badhao|loud)\b", text_lower):
            intent = "volume_up"
            confidence = 1.0
        elif re.search(r"\b(volume down|decrease volume|volume kam karo|awaaz kam karo|dheere)\b", text_lower):
            intent = "volume_down"
            confidence = 1.0
        elif re.search(r"\b(brightness|chamak)\b", text_lower):
            intent = "brightness_control"
            confidence = 1.0
        # 1. Use AI Brain to detect intent
        intent, confidence = self.brain.predict(text)
        print(f"AI Intent: {intent} ({confidence:.2f})")

        # 2. Handle Routing
        social_intents = ["greet", "wellbeing", "identity", "capabilities", "status_update", "goodbye"]
        
        # If confidence is low, check for fallback options
        if confidence < self.confidence_threshold:
            # If it sounds like a social intent, even with low confidence, we allow it to bypass RL learner
            if intent in social_intents and confidence > 0.2:
                print(f"Low confidence social intent ({intent}) accepted.")
            else:
                # Only trigger RL Learner for automation-like phrases, otherwise let it fall back to LLM later
                automation_keywords = ["open", "close", "band", "kholo", "chalao", "start", "stop", "volume", "brightness"]
                if any(w in text_lower for w in automation_keywords):
                    print(f"Confidence low ({confidence:.2f}). Triggering RL Learner for automation...")
                    intent = self.learner.handle_unknown(text)
                    confidence = 1.0
                else:
                    # Clear intent to trigger LLM fallback at the end
                    intent = "unknown"
                    confidence = 0.0

        # 3. Dispatch to Handlers
        if intent == "greet":
            # ... (random response logic)
            pass # Skipping for brevity in TargetContent matching, but I need to be careful with the existing logic
            import random
            responses = [
                "Hello! How can I help you today?",
                "Hi there! JARVIS at your service.",
                "Hey! What's on your mind?",
                "Namaste! How are you doing?"
            ]
            self.speaker.speak(random.choice(responses), lang=lang)
            return True

        if intent == "identity":
            import random
            responses = [
                "I am JARVIS, your personal AI assistant.",
                "I'm JARVIS. I'm here to help you with your tasks and automations.",
                "People call me JARVIS. I'm your digital companion."
            ]
            self.speaker.speak(random.choice(responses), lang=lang)
            return True

        if intent == "wellbeing":
            import random
            responses = [
                "I'm doing great, thank you for asking! How about you?",
                "System's running at 100%. I'm feeling good! How are you?",
                "I'm excellent! Always ready to help. How's your day going?"
            ]
            self.speaker.speak(random.choice(responses), lang=lang)
            return True

        if intent == "capabilities":
            self.speaker.speak(
                "I can help you with many things: opening apps, managing calls, "
                "syncing notifications, checking weather, battery, internet speed, "
                "controlling media, and even unlocking your phone.",
                lang=lang
            )
            return True

        if intent == "status_update":
            import random
            responses = [
                "That's good to hear!",
                "Great! Let me know if you need anything while you work.",
                "Understood. I'm here if you need me.",
                "Nice! Keep it up."
            ]
            self.speaker.speak(random.choice(responses), lang=lang)
            return True

        elif intent == "goodbye":
            return "Goodbye sir. System on standby."
            
        elif intent == "youtube_media":
            return self._handle_youtube(text_lower)
            
        elif intent == "google_search":
            return self._handle_browser(text_lower, "search")
            
        elif intent == "open_item":
            return self._handle_open(text_lower)
            
        elif intent == "close_item":
            return self._handle_close(text_lower)
            
        elif intent == "whatsapp_message":
            return self._handle_whatsapp(text_lower)
            
        elif intent == "email_message":
            return self._handle_email(text_lower)
            
        elif intent == "social_post":
            return self._handle_social(text_lower)
            
        elif intent == "gesture_mode_control":
            if any(w in text_lower for w in ["off", "disable", "stop", "band", "exit", "close"]):
                self.synex.set_gesture_allowed(False)
                return "Gesture recognition mode is now disabled."
            else:
                self.synex.set_gesture_allowed(True)
                return "Gesture recognition mode is now enabled."
            
        elif intent in ["volume_mute", "volume_up", "volume_down", "brightness_control"]:
            if self.system_controller:
                return self.system_controller.handle(intent, text)
            return "System control module is not available."
            
        elif intent == "check_time":
            now = datetime.datetime.now().strftime("%H:%M")
            return f"The current time is {now}"

        elif intent == "check_weather":
            if self.weather_controller:
                return self.weather_controller.handle(intent, text)
            return "Weather service is not available."

        elif intent == "check_battery":
            try:
                import psutil
                battery = psutil.sensors_battery()
                return f"Battery is at {battery.percent}%"
            except:
                return "I couldn't check the battery status."

        elif intent == "check_calendar" or any(w in text_lower for w in ["upcoming", "meetings", "appointments", "schedule for", "on my calendar"]):
            if self.calendar_controller:
                if not self.management_flow:
                    self.management_flow = CalendarManagementFlow(self.calendar_controller)
                return self.management_flow.handle(text)
            return "Calendar service is not available."

        elif intent == "schedule_event":
            return self._handle_calendar(text_lower)
            
        elif any(w in text_lower for w in ["remove", "delete", "cancel"]):
            # Check if this sounds like a calendar removal request
            if any(cw in text_lower for cw in ["meeting", "appointment", "event", "calendar"]):
                 if self.calendar_controller:
                    if not self.management_flow:
                        self.management_flow = CalendarManagementFlow(self.calendar_controller)
                    return self.management_flow.handle(text)

        elif intent == "check_ip":
            return self._handle_ip()

        # Default fallback
        if lang == "hi":
            return f"Maine suna: {text}. Main ispar seekh raha hoon."
        else:
            return f"I heard: {text}. I am learning how to handle this."

    def _handle_ip(self):
        """Fetches and returns the public IP address"""
        try:
            import requests
            response = requests.get('https://api.ipify.org?format=json', timeout=5)
            if response.status_code == 200:
                ip = response.json().get('ip')
                return f"Your public IP address is {ip}"
            else:
                return "I'm sorry, I couldn't reach the IP service."
        except Exception as e:
            print(f"Error fetching IP: {e}")
            return "I had trouble fetching your IP address. Please check your connection."

    def _handle_open(self, text):
        """Dispatches open command to AppLauncher or Browser"""
        # Strip trigger words
        item = text
        for w in ["open", "launch", "start", "kholo", "chalao", "application", "software"]:
            item = item.replace(w, "")
        item = item.strip()
        
        if not item:
            return "What should I open?"

        # 1. Try launching as a local App first
        if self.app_launcher.launch(item):
            return f"Opening {item}"
        
        # 2. If it looks like a website or app launch failed, try browser
        return self._handle_browser(text, "open")

    def _handle_close(self, text):
        """Dispatches close command with Tab vs App logic"""
        item = text
        for w in ["close", "exit", "stop", "terminate", "band", "hatao", "shut down"]:
            item = item.replace(w, "")
        item = item.strip()
        
        if not item:
            return "What should I close?"

        # 1. Specialized logic for Browser Tabs
        if "tab" in item:
            if self.google_controller:
                try:
                    self.google_controller.close_tab()
                    return "Closing current tab."
                except:
                    pass
            # Fallback for tab if google_controller isn't available
            return "I couldn't find an open tab to close."

        # 2. LIFO application closing using AppLauncher (psutil)
        cleaned_app_name = item.replace("app", "").replace("application", "").strip()
        if self.app_launcher.close(cleaned_app_name):
            return f"Closing most recent instance of {cleaned_app_name}"
            
        return f"I couldn't find a running application named {cleaned_app_name}"
            
    def _handle_whatsapp(self, text):
        if self.automation_controller:
            return self.automation_controller.handle_messaging("whatsapp", text)
        return "Automation module is not available."

    def _handle_email(self, text):
        if self.automation_controller:
            return self.automation_controller.handle_messaging("email", text)
        return "Automation module is not available."

    def _handle_social(self, text):
        if self.automation_controller:
            # Extract platform and content
            # Simplistic parsing for now: "post to [platform], [content]"
            # We'll rely on the controller to handle it
            platform = "unknown"
            content = text
            for p in ["instagram", "twitter", "x", "facebook", "linkedin"]:
                if p in text.lower():
                    platform = p
                    break
            return self.automation_controller.handle_posting(platform, content)
        return "Automation module is not available."

    def _handle_youtube(self, text):
        if self.yt_controller:
            intent = "youtube_search"
            if "play" in text:
                intent = "youtube_play"
            return self.yt_controller.handle(intent, text)
        return "YouTube module is not available."

    def _handle_browser(self, text, mode="search"):
        if self.google_controller:
            query = text
            for w in ["search", "google", "find", "open"]:
                query = query.replace(w, "")
            query = query.strip()
            
            if mode == "open":
                self.google_controller.open_site(query)
                return f"Opening website: {query}"
            else:
                self.google_controller.search(query)
                return f"Searching for {query}"
        return "Browser module is not available."

    def _check_calendar_auth(self):
        """Helper to check calendar authentication status without triggering OAuth flow."""
        if not self.calendar_controller:
            return "credentials_missing"
        return self.calendar_controller.is_authenticated()

    def _handle_calendar(self, text):
        """Dispatches calendar command to CalendarController after parsing info via MeetingFlowHandler"""
        if not self.calendar_controller:
            return "Calendar module is not available."
            
        flow_result = self.meeting_flow.handle_turn(text)
        
        if flow_result["status"] == "complete":
            data = flow_result["data"]
            # Trigger full authenticate only when we are ready to save (it may prompt OAuth in browser)
            # but usually it will just use the token we verified in is_authenticated
            auth_res = self.calendar_controller.authenticate()
            if auth_res == True:
                return self.calendar_controller.schedule_event(data["title"], data["date_time"])
            else:
                return "I ran into a problem authenticating. Please try linking your account again in Settings."
        
        return flow_result["message"]
