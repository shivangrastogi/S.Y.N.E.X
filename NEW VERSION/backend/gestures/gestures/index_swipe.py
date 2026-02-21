import time
import pyautogui

HOLD_TIME = 1.0
MIN_SWIPE_DISTANCE = 0.15   # normalized screen width

class IndexSwipeController:
    def __init__(self):
        self.hold_start = None
        self.armed = False
        self.start_x = None
        self.triggered = False

    def reset(self):
        self.hold_start = None
        self.armed = False
        self.start_x = None
        self.triggered = False

    def update(self, lm, frame_width):
        """
        Returns:
        - status_text (str or None)
        - swipe_direction ("LEFT" | "RIGHT" | None)
        """
        now = time.time()
        index_tip = lm.landmark[8]
        x = index_tip.x

        # -----------------------------
        # HOLD TO ARM
        # -----------------------------
        if not self.armed:
            if self.hold_start is None:
                self.hold_start = now
                return "Hold index finger...", None

            elapsed = now - self.hold_start
            if elapsed >= HOLD_TIME:
                self.armed = True
                self.start_x = x
                return "Swipe ← or →", None

            return f"Hold {int((elapsed/HOLD_TIME)*100)}%", None

        # -----------------------------
        # SWIPE DETECTION
        # -----------------------------
        dx = x - self.start_x

        if abs(dx) >= MIN_SWIPE_DISTANCE and not self.triggered:
            self.triggered = True

            if dx > 0:
                pyautogui.hotkey("alt", "shift", "tab")
                self.reset()
                return None, "RIGHT"
            else:
                pyautogui.hotkey("alt", "tab")
                self.reset()
                return None, "LEFT"

        return "Swipe ← or →", None
