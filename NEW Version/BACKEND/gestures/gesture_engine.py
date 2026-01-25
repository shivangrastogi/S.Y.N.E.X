# BACKEND/gestures/gesture_engine.py
import time
import ctypes
import numpy as np
from pycaw.pycaw import AudioUtilities

from BACKEND.gestures.config import (
    HOLD_TIME_V,
    HOLD_TIME_LOCK,
    VOLUME_MIN_RATIO,
    VOLUME_MAX_RATIO
)
from BACKEND.gestures.detection.gesture_classifier import dist

try:
    devices = AudioUtilities.GetSpeakers()
    volume = devices.EndpointVolume
except Exception:
    volume = None


class GestureEngine:
    def __init__(self):
        self.active = False

        # ---- V SIGN STATE ----
        self.v_start = None
        self.v_triggered = False

        # ---- FIST STATE ----
        self.fist_start = None
        self.fist_triggered = False

    def update(self, gesture, lm):
        now = time.time()

        # =================================================
        # ✌️ V SIGN — MODE TOGGLE (EXCLUSIVE OWNER)
        # =================================================
        if gesture == "V_SIGN":
            # HARD BLOCK everything else
            self.fist_start = None
            self.fist_triggered = False

            if not self.v_triggered:
                self.v_start = self.v_start or now
                elapsed = now - self.v_start

                if elapsed >= HOLD_TIME_V:
                    self.active = not self.active
                    self.v_triggered = True

                return elapsed / HOLD_TIME_V, None

            return 1.0, None

        # Reset V-sign when released
        self.v_start = None
        self.v_triggered = False

        # =================================================
        # ⛔ MODE OFF → NOTHING ELSE WORKS
        # =================================================
        if not self.active:
            self.fist_start = None
            self.fist_triggered = False
            return 0.0, None

        # =================================================
        # ✊ FIST — LOCK SCREEN (ONE SHOT)
        # =================================================
        if gesture == "FIST":
            if not self.fist_triggered:
                self.fist_start = self.fist_start or now
                elapsed = now - self.fist_start

                if elapsed >= HOLD_TIME_LOCK:
                    ctypes.windll.user32.LockWorkStation()
                    self.fist_triggered = True

                return elapsed / HOLD_TIME_LOCK, None

            return 1.0, None

        # Reset fist when released
        self.fist_start = None
        self.fist_triggered = False

        # =================================================
        # 🔊 VOLUME PINCH — CONTINUOUS
        # =================================================
        if gesture == "VOLUME_PINCH" and lm:
            if volume is None:
                return 0.0, None
            wrist = lm.landmark[0]
            mid = lm.landmark[9]
            thumb = lm.landmark[4]
            index = lm.landmark[8]

            ratio = dist(thumb, index) / dist(mid, wrist)
            vol = np.clip(
                np.interp(ratio, [VOLUME_MIN_RATIO, VOLUME_MAX_RATIO], [0, 1]),
                0, 1
            )

            try:
                volume.SetMasterVolumeLevelScalar(vol, None)
            except Exception:
                pass
            return 0.0, int(vol * 100)

        return 0.0, None
