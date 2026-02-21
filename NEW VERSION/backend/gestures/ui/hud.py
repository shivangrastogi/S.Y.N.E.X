# BACKEND/gestures/ui/hud.py
import cv2

def draw_status(frame, active, gesture):
    h, w, _ = frame.shape
    color = (0,255,0) if active else (0,0,255)
    cv2.rectangle(frame, (0,0), (w,40), (40,40,40), -1)
    cv2.putText(
        frame,
        f"MODE: {'ACTIVE' if active else 'STANDBY'} | {gesture}",
        (10,28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2
    )
