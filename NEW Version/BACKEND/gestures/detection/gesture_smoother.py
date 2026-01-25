# BACKEND/gestures/detection/gesture_smoother.py
from BACKEND.gestures.config import gesture_buffer, GESTURE_BUFFER_SIZE

def smooth_gesture(raw):
    gesture_buffer.append(raw)
    if len(gesture_buffer) < GESTURE_BUFFER_SIZE:
        return "STABILIZING"

    best = max(set(gesture_buffer), key=gesture_buffer.count)
    return best if gesture_buffer.count(best) > GESTURE_BUFFER_SIZE * 0.8 else "TRANSITIONING"
