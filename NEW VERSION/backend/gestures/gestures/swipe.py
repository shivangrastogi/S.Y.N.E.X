# BACKEND/gestures/gestures/swipe.py
import time
import pyautogui

from BACKEND.gestures.config import (
    hand_x_history,
    hand_time_history,
    SWIPE_MIN_SCREEN_RATIO,
    SWIPE_MIN_VELOCITY,
    SWIPE_COOLDOWN_TIME
)

last_swipe_time = 0


def detect_single_finger_swipe(lm, now):
    global last_swipe_time

    wrist = lm.landmark[0]
    mid = lm.landmark[9]

    x = (wrist.x + mid.x) / 2
    hand_x_history.append(x)
    hand_time_history.append(now)

    if len(hand_x_history) < 4:
        return

    dx = hand_x_history[-1] - hand_x_history[0]
    dt = hand_time_history[-1] - hand_time_history[0]
    velocity = abs(dx / dt) if dt > 0 else 0

    if abs(dx) > SWIPE_MIN_SCREEN_RATIO and velocity > SWIPE_MIN_VELOCITY:
        if now - last_swipe_time > SWIPE_COOLDOWN_TIME:
            last_swipe_time = now
            hand_x_history.clear()
            hand_time_history.clear()

            if dx > 0:
                pyautogui.hotkey("alt", "shift", "tab")  # RIGHT
            else:
                pyautogui.hotkey("alt", "tab")           # LEFT