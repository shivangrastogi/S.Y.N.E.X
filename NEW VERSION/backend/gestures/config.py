# BACKEND/gestures/config.py
from collections import deque

# =============================
# GESTURE BUFFER
# =============================
GESTURE_BUFFER_SIZE = 15
gesture_buffer = deque(maxlen=GESTURE_BUFFER_SIZE)

# =============================
# HOLD TIMINGS
# =============================
HOLD_TIME_V = 1.0
HOLD_TIME_LOCK = 1.0

# =============================
# VOLUME CONTROL
# =============================
VOLUME_MIN_RATIO = 0.18
VOLUME_MAX_RATIO = 1.25

# =============================
# SWIPE (HAND SWING)
# =============================
SWIPE_MIN_SCREEN_RATIO = 0.20
SWIPE_MIN_VELOCITY = 0.35
SWIPE_COOLDOWN_TIME = 1.0

hand_x_history = deque(maxlen=6)
hand_time_history = deque(maxlen=6)

# =============================
# V-SIGN
# =============================
V_SIGN_MIN_SPREAD_RATIO = 0.35
