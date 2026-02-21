# Path: d:\New folder (2) - JARVIS\backend\automations\calendar\calendar_controller.py
import os
import datetime
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

class CalendarController:
    def __init__(self, username="default"):
        self.creds = None
        self.username = username
        self.config_dir = os.path.join(os.path.dirname(__file__), "config")
        self.token_dir = os.path.join(self.config_dir, "tokens")
        self.token_path = os.path.join(self.token_dir, f'{username}_token.pickle')
        self.creds_path = os.path.join(self.config_dir, 'credentials.json')
        self.service = None
        
        # Ensure token directory exists
        os.makedirs(self.token_dir, exist_ok=True)

    def is_authenticated(self):
        """Checks if there's a valid token for the current user."""
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
                return creds and (creds.valid or (creds.expired and creds.refresh_token))
        return False

    def authenticate(self):
        """Authenticates the user with Google Calendar API."""
        if not os.path.exists(self.creds_path):
            return "credentials_missing"

        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                self.creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception:
                    # Refresh failed, need fresh login
                    self.creds = None

            if not self.creds:
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_path, 'wb') as token:
                pickle.dump(self.creds, token)

        self.service = build('calendar', 'v3', credentials=self.creds)
        return True

    def clear_token(self):
        """Removes the stored token for the current user."""
        if os.path.exists(self.token_path):
            os.remove(self.token_path)
        self.creds = None
        self.service = None
        return True

    def get_account_info(self):
        """Fetches account information (email) for the connected user."""
        if not self.service and not self.authenticate():
            return None
        try:
            # We use the 'primary' calendar settings to find the owner's email
            calendar = self.service.calendars().get(calendarId='primary').execute()
            return calendar.get('id') # This is usually the email
        except Exception as e:
            print(f"Error fetching account info: {e}")
            return None

    def schedule_event(self, summary, start_time_str, duration_minutes=30, attendees=None, description=""):
        """
        Schedules an event in Google Calendar.
        start_time_str: ISO format string or natural language description (to be parsed by brain)
        """
        if not self.service and not self.authenticate():
            return "Authentication failed. Please check your credentials.json."

        try:
            # Basic parsing of start_time_str (Assumes it's ISO format for now)
            # In the full flow, the CommandProcessor will pass a pre-parsed datetime object
            if isinstance(start_time_str, str):
                start_time = datetime.datetime.fromisoformat(start_time_str)
            else:
                start_time = start_time_str

            end_time = start_time + datetime.timedelta(minutes=int(duration_minutes))

            # Get local context for timezone (using offset is most reliable for Google API)
            now = datetime.datetime.now()
            local_now = now.astimezone()
            tz_offset = local_now.strftime('%z')
            
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_time.strftime('%Y-%m-%dT%H:%M:%S') + tz_offset,
                },
                'end': {
                    'dateTime': end_time.strftime('%Y-%m-%dT%H:%M:%S') + tz_offset,
                },
            }

            if attendees:
                # attendees: list of email strings
                event['attendees'] = [{'email': email} for email in attendees]

            event = self.service.events().insert(calendarId='primary', body=event).execute()
            return f"Meeting scheduled: {event.get('htmlLink')}"

        except Exception as e:
            return f"An error occurred: {e}"

    def list_events(self, time_min=None, time_max=None, max_results=10):
        """Lists events in a given time range."""
        if not self.service and not self.authenticate():
            return "Authentication failed."

        if not time_min:
            time_min = datetime.datetime.utcnow().isoformat() + 'Z'
        elif isinstance(time_min, datetime.datetime):
            time_min = time_min.isoformat() + 'Z'

        if isinstance(time_max, datetime.datetime):
            time_max = time_max.isoformat() + 'Z'

        events_result = self.service.events().list(
            calendarId='primary', 
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results, 
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])

    def delete_event(self, event_id):
        """Deletes an event by ID."""
        if not self.service and not self.authenticate():
            return "Authentication failed."
        
        try:
            self.service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False

    def get_upcoming_events(self, max_results=10):
        """Legacy method retained for compatibility, uses list_events internally."""
        events = self.list_events(max_results=max_results)

        if isinstance(events, str): # Error message
            return events

        if not events:
            return "No upcoming events found."
        
        result = "Upcoming events:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            result += f"- {start}: {event['summary']}\n"
        return result
