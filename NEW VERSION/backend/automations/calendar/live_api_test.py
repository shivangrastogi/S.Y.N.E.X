# Path: d:\New folder (2) - JARVIS\backend\automations\calendar\live_api_test.py
from calendar_controller import CalendarController
from meeting_flow import MeetingFlowHandler
import os

def run_live_test():
    print("--- JARVIS GOOGLE CALENDAR LIVE INTEGRATION TEST ---")
    
    controller = CalendarController()
    handler = MeetingFlowHandler()
    
    # 1. Check for credentials.json
    if not os.path.exists(controller.creds_path):
        print(f"\n❌ ERROR: credentials.json NOT FOUND!")
        print(f"Please place your credentials.json in: {controller.config_dir}")
        print("You can get this from the Google Cloud Console (APIs & Services > Credentials).")
        return

    print("\nStep 1: Authenticating with Google...")
    if not controller.authenticate():
        print("❌ Authentication failed.")
        return
    print("✅ Authenticated successfully!")

    print("\nStep 2: Checking existing events...")
    events = controller.get_upcoming_events(max_results=5)
    print(events)

    print("\nStep 3: Interactive Scheduling Test")
    print("Simulating voice command: 'Schedule a discovery meeting for tomorrow at 11 AM'")
    
    user_input = "Schedule a discovery meeting for tomorrow at 11 AM"
    result = handler.handle_turn(user_input)
    
    print(f"JARVIS: {result['message']}")
    
    if result['status'] == 'complete':
        data = result['data']
        print(f"\n🚀 ATTEMPTING TO SAVE TO REAL CALENDAR...")
        save_result = controller.schedule_event(data['title'], data['date_time'])
        print(f"RESULT: {save_result}")
    else:
        print("❌ Flow did not complete. Check meeting_flow.py logic.")

if __name__ == "__main__":
    run_live_test()
