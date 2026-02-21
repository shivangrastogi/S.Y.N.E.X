# Path: d:\New folder (2) - JARVIS\backend\automations\calendar\meeting_flow.py
import dateparser
from dateparser.search import search_dates
import datetime
import re

class MeetingFlowHandler:
    def __init__(self, auth_callback=None):
        self.reset()
        self.max_retries = 4 # Increased for better flexibility
        self.auth_callback = auth_callback

    def reset(self):
        self.slots = {
            "title": None,
            "date_time": None
        }
        self.active = False
        self.retries = 0
        self.last_asked = None

    def is_complete(self):
        return self.slots["title"] is not None and self.slots["date_time"] is not None

    def extract_slots(self, text):
        """Attempts to fill missing slots from the user's text."""
        text_lower = text.lower()
        
        # 1. Extract Date/Time if missing
        matches = search_dates(text, settings={'PREFER_DATES_FROM': 'future'})
        date_segment = ""
        if matches:
            # We take the best match for date_time
            if not self.slots["date_time"]:
                self.slots["date_time"] = matches[0][1]
            date_segment = matches[0][0]

        # 2. Extract Title if missing
        if not self.slots["title"]:
            if self.last_asked == "title":
                 # If we specifically asked for the title, take the whole input (unless it's just a date)
                 if not matches:
                    self.slots["title"] = text.strip().capitalize()
            else:
                # Look for patterns that identify the title
                temp_text = text
                if date_segment:
                    # Remove the date segment so it doesn't get caught in the title
                    # Using case-insensitive replace
                    pattern = re.compile(re.escape(date_segment), re.IGNORECASE)
                    temp_text = pattern.sub("", temp_text)
                
                # Cleanup common conversational prefixes/triggers anywhere in the string
                triggers = [
                    r"schedule a meeting", r"schedule meeting", r"book a meeting", 
                    r"book appointment", r"i want to schedule a meeting",
                    r"can you schedule", r"please schedule", r"jarvis", r"i want you to schedule"
                ]
                for trigger in triggers:
                    temp_text = re.sub(trigger, "", temp_text, flags=re.IGNORECASE)

                # Search for explicit title indicators
                # Patterns: "about X", "called X", "titled X", "title that X", "subject X", "meeting of X"
                title_patterns = [
                    r"about\s+(.*)",
                    r"called\s+(.*)",
                    r"titled\s+(.*)",
                    r"title\s+that\s+(.*)",
                    r"title\s+is\s+(.*)",
                    r"subject\s+(.*)",
                    r"meeting\s+of\s+(.*)",
                    r"meeting\s+with\s+(.*)"
                ]
                
                title_candidate = None
                for p in title_patterns:
                    m = re.search(p, temp_text, re.IGNORECASE)
                    if m:
                        title_candidate = m.group(1).strip()
                        break
                
                if not title_candidate:
                    # Fallback: take what's left after stripping triggers and date
                    title_candidate = temp_text.strip()
                
                # Clean up results
                if title_candidate and len(title_candidate) > 2:
                    # Final check: if it's just generic words, ignore it
                    cleaned_lower = title_candidate.lower()
                    stop_words = ["meeting", "a meeting", "appointment", "schedule", "will it", "the meeting"]
                    if cleaned_lower not in stop_words:
                        # Ensure no date is hidden in the title candidate
                        if not search_dates(title_candidate):
                            # Remove "will it title that" if it leaked in
                            title_candidate = re.sub(r"^(will it|can you)\s+(title|name|subject)\s+(that|is|as)\s+", "", title_candidate, flags=re.IGNORECASE)
                            self.slots["title"] = title_candidate.strip().capitalize()

    def get_next_prompt(self):
        """Determines what to ask next or returns None if complete."""
        if not self.slots["date_time"]:
            self.last_asked = "date_time"
            return "When should I schedule the meeting?"
        
        if not self.slots["title"]:
            self.last_asked = "title"
            return "What is the meeting about?"
            
        return None

    def handle_turn(self, text):
        """Main entry point for a conversation turn."""
        if not self.active:
            # Check Authentication BEFORE starting the flow
            if self.auth_callback:
                auth_status = self.auth_callback()
                if auth_status == "credentials_missing":
                     return {"status": "error", "message": "Sir, I need a Google Calendar API key to work. Please check the setup instructions."}
                if not auth_status:
                     return {"status": "not_authenticated", "message": "I don't have access to your calendar yet. Please go to Settings and link your Google account."}
            
            self.active = True
            
        self.extract_slots(text)
        
        if self.is_complete():
            response = {
                "status": "complete",
                "data": self.slots,
                "message": f"Perfect. Scheduling '{self.slots['title']}' for {self.slots['date_time'].strftime('%A at %I:%M %p')}."
            }
            self.active = False # Reset for next session
            return response
        
        prompt = self.get_next_prompt()
        if prompt:
            self.retries += 1
            if self.retries > self.max_retries:
                self.reset()
                return {
                    "status": "failed",
                    "message": "I'm sorry, I couldn't get all the details. Let's try again later."
                }
            
            return {
                "status": "incomplete",
                "message": prompt
            }
        
        return {"status": "error", "message": "Something went wrong with the meeting flow."}
