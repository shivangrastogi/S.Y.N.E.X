# Path: d:\New folder (2) - JARVIS\backend\automations\calendar\test_calendar_flow.py
from meeting_flow import MeetingFlowHandler
import datetime

def run_test_suite():
    handler = MeetingFlowHandler()

    test_cases = [
        {
            "name": "Full Information in One Go",
            "inputs": ["Schedule a meeting about Project Alpha tomorrow at 5 PM"]
        },
        {
            "name": "Missing Title",
            "inputs": ["Schedule a meeting tomorrow at 3 PM", "Weekly Sync"]
        },
        {
            "name": "Just 'Schedule a Meeting'",
            "inputs": ["Schedule a meeting", "today at 10 PM", "Interview with John"]
        },
        {
            "name": "Missing Date/Time",
            "inputs": ["Schedule a meeting called Team Lunch", "next Friday at 1 PM"]
        },
        {
            "name": "Insufficient Data (Retry Limit Test)",
            "inputs": ["Schedule a meeting", "I don't know when", "Maybe later"]
        }
    ]

    for case in test_cases:
        print(f"\n--- TEST CASE: {case['name']} ---")
        handler.reset()
        for user_input in case['inputs']:
            print(f"User: {user_input}")
            result = handler.handle_turn(user_input)
            print(f"JARVIS: {result['message']}")
            
            if result['status'] == 'complete':
                print(f"SUCCESS: Data to save -> {result['data']}")
                break
            elif result['status'] == 'failed':
                print(f"FLOW ENDED: {result['message']}")
                break

if __name__ == "__main__":
    # Ensure current date is known for relative parsing demo
    print(f"System Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    run_test_suite()
