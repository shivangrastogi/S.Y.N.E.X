# BACKEND/gestures/gestures/dispatcher_test.py
def test_dispatcher(event, payload=None):
    """
    This dispatcher is ONLY for testing.
    It prints gesture actions instead of controlling system/apps.
    """

    if event == "GESTURE_MODE":
        print(f"\n🟢 Gesture Mode {'ENABLED' if payload else 'DISABLED'}")

    elif event == "LOCK":
        print("🔒 LOCK gesture detected (FIST)")

    elif event == "VOLUME":
        print("🔊 VOLUME PINCH detected")

    elif event == "SWIPE_LEFT":
        print("⬅️ SWIPE LEFT detected")

    elif event == "SWIPE_RIGHT":
        print("➡️ SWIPE RIGHT detected")

    else:
        print(f"⚠️ Unknown event: {event}")
