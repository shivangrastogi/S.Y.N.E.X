# BACKEND/gestures/detection/gesture_classifier.py
from BACKEND.gestures.config import V_SIGN_MIN_SPREAD_RATIO


def dist(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def classify_raw_gesture(lm):
    l = lm.landmark

    index_up = dist(l[8], l[0]) > dist(l[6], l[0])
    middle_up = dist(l[12], l[0]) > dist(l[10], l[0])
    ring_up = dist(l[16], l[0]) > dist(l[14], l[0])
    pinky_up = dist(l[20], l[0]) > dist(l[18], l[0])

    # 👇 Thumb OPEN means far from palm
    thumb_open = dist(l[4], l[17]) > dist(l[3], l[17])
    thumb_closed = not thumb_open

    # ==========================================
    # ☝️ INDEX ONLY (SWIPE MODE)
    # Thumb MUST be closed
    # ==========================================
    if index_up and thumb_closed and not any([middle_up, ring_up, pinky_up]):
        return "INDEX_ONLY"

    # ==========================================
    # ✌️ V SIGN (MODE TOGGLE)
    # ==========================================
    if index_up and middle_up and not ring_up and not pinky_up:
        hand_size = dist(l[9], l[0])
        gap = dist(l[8], l[12])
        if hand_size > 0 and (gap / hand_size) >= V_SIGN_MIN_SPREAD_RATIO:
            return "V_SIGN"
        else:
            return "TWO_FINGER_CLOSE"

    # ==========================================
    # ✊ FIST (LOCK)
    # ==========================================
    if not any([index_up, middle_up, ring_up, pinky_up, thumb_open]):
        return "FIST"

    # ==========================================
    # 🔊 VOLUME PINCH
    # Thumb MUST be OPEN
    # ==========================================
    if thumb_open and index_up and not any([middle_up, ring_up, pinky_up]):
        if dist(l[4], l[8]) > 0.025:
            return "VOLUME_PINCH"

    return "NONE"
