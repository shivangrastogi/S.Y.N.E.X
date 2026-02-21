# BACKEND/gestures/gestures/fist.py
import ctypes
import time

LOCK_HOLD_SECONDS = 2.0


class FistLocker:
    def __init__(self):
        self.start_time = None
        self.triggered = False

    def update(self, active: bool):
        """
        Returns:
        - progress (0.0 → 1.0)
        - triggered (True only once when lock happens)
        """
        now = time.time()

        if not active:
            self.start_time = None
            self.triggered = False
            return 0.0, False

        if self.start_time is None:
            self.start_time = now

        elapsed = now - self.start_time

        if elapsed >= LOCK_HOLD_SECONDS and not self.triggered:
            self.triggered = True
            ctypes.windll.user32.LockWorkStation()
            return 1.0, True

        return min(elapsed / LOCK_HOLD_SECONDS, 1.0), False
