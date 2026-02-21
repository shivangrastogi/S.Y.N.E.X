import dateparser
from dateparser.search import search_dates
import datetime
import re

class CalendarManagementFlow:
    def __init__(self, controller):
        self.controller = controller
        self.reset()

    def reset(self):
        self.active = False
        self.last_listed_events = []
        self.current_date_context = None

    def handle(self, text):
        text_lower = text.lower()
        
        # 1. Check for "list/show/what" patterns
        if any(w in text_lower for w in ["show", "list", "what", "any", "upcoming", "meetings", "appointments"]):
            return self._handle_list(text)
            
        # 2. Check for "remove/delete/cancel" patterns
        if any(w in text_lower for w in ["remove", "delete", "cancel"]):
            return self._handle_delete(text)

        # 3. If active and user provides an index or simple confirmation
        if self.active and self.last_listed_events:
            return self._handle_followup(text)

        return None

    def _handle_list(self, text):
        matches = search_dates(text, settings={'PREFER_DATES_FROM': 'future'})
        
        start_time = None
        end_time = None
        
        if matches:
            date_val = matches[0][1]
            # If user said "tomorrow", we want the whole day
            start_time = date_val.replace(hour=0, minute=0, second=0)
            end_time = start_time + datetime.timedelta(days=1)
            self.current_date_context = start_time
        else:
            # Default to upcoming if no date found
            start_time = datetime.datetime.utcnow()
            self.current_date_context = "upcoming"

        events = self.controller.list_events(time_min=start_time, time_max=end_time)
        
        if isinstance(events, str):
            return events

        if not events:
            date_str = start_time.strftime("%A, %B %d") if isinstance(start_time, datetime.datetime) else "upcoming"
            return f"I couldn't find any meetings for {date_str}."

        self.last_listed_events = events
        self.active = True
        
        resp = f"Here are your meetings for {start_time.strftime('%A') if isinstance(start_time, datetime.datetime) else 'the upcoming days'}:\n"
        for i, ev in enumerate(events):
            start = ev['start'].get('dateTime', ev['start'].get('date'))
            st_dt = dateparser.parse(start)
            st_str = st_dt.strftime("%I:%M %p") if st_dt else start
            resp += f"{i+1}. {st_str}: {ev.get('summary', 'No Title')}\n"
        
        resp += "\nYou can say 'remove the first one' or 'delete meeting 2' to cancel any of these."
        return resp

    def _handle_delete(self, text):
        # 1. Try to find an index (e.g., "remove the second one", "delete 1")
        index = self._extract_index(text)
        if index is not None and self.active and 0 <= index < len(self.last_listed_events):
            event = self.last_listed_events[index]
            success = self.controller.delete_event(event['id'])
            if success:
                summary = event.get('summary', 'meeting')
                self.reset()
                return f"Done! I've removed the meeting: {summary}."
            else:
                return "I encountered an error while trying to delete that meeting."

        # 2. Try to find by title if index failed
        if self.active:
            for i, ev in enumerate(self.last_listed_events):
                summary = ev.get('summary', '').lower()
                if summary and summary in text.lower():
                    success = self.controller.delete_event(ev['id'])
                    if success:
                        self.reset()
                        return f"Alright, I've cancelled the '{ev.get('summary')}' meeting."

        # 3. If they just said "delete meeting" without context
        if not self.active:
            return "Which meeting should I remove? You can ask me to 'list my meetings' first to see them."
            
        return "I'm not sure which meeting you want to remove. Please specify the number or the title."

    def _handle_followup(self, text):
        # If user just says "first", "second", etc.
        index = self._extract_index(text)
        if index is not None and 0 <= index < len(self.last_listed_events):
            return self._handle_delete(f"remove {index + 1}")
        return None

    def _extract_index(self, text):
        # Handle word forms
        words = {
            "first": 0, "1st": 0, "one": 0, "1": 0,
            "second": 1, "2nd": 1, "two": 1, "2": 1,
            "third": 2, "3rd": 2, "three": 2, "3": 2,
            "fourth": 3, "4th": 3, "four": 3, "4": 3,
            "fifth": 4, "5th": 4, "five": 4, "4": 4
        }
        for word, idx in words.items():
            if f" {word}" in f" {text.lower()}":
                return idx
        
        # Handle digits
        match = re.search(r"\b(\d+)\b", text)
        if match:
            return int(match.group(1)) - 1
            
        return None
