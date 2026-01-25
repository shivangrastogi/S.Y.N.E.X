# BACKEND/gestures/detection/hand_tracker.py

import mediapipe as mp

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.8,
    min_tracking_confidence=0.8
)

# ✅ EXPORT THIS CONSTANT
HAND_CONNECTIONS = mp_hands.HAND_CONNECTIONS
