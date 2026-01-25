# BACKEND/gestures/gestures/test_gestures.py
"""
Gesture Testing Mode (REAL ACTIONS)
----------------------------------
✔ Hand detection
✔ Mode toggle (V sign)
✔ Lock screen (Fist – 1 shot)
✔ Volume control (Pinch – live)
✔ App switching (Single finger swipe)

Press 'q' to quit
"""

from BACKEND.gestures.gesture_manager import GestureManager


def main():
    print("\n==============================")
    print("🧪 JARVIS GESTURE TEST MODE")
    print("==============================")
    print("Controls:")
    print("  ✌️ V Sign (hold)  → Toggle Gesture Mode")
    print("  ✊ Fist (hold)    → Lock Screen")
    print("  🤏 Pinch          → Volume Control")
    print("  ☝️ Swipe          → App Switch")
    print("  Press 'q' to quit")
    print("==============================\n")

    gm = GestureManager()   # ✅ FIXED
    gm.run()


if __name__ == "__main__":
    main()
