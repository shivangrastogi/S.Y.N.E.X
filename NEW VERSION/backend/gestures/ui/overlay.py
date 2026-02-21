# BACKEND/gestures/ui/overlay.py
import cv2
import numpy as np

pulse = 0.0


def draw_volume_ui(frame, thumb, index, percent):
    global pulse
    h, w, _ = frame.shape

    tx, ty = int(thumb.x * w), int(thumb.y * h)
    ix, iy = int(index.x * w), int(index.y * h)
    cx, cy = (tx + ix) // 2, (ty + iy) // 2

    r = int(255 - percent * 2.55)
    g = int(percent * 2.55)
    color = (r, g, 255)

    cv2.line(frame, (tx, ty), (ix, iy), color, 4)
    cv2.circle(frame, (tx, ty), 7, color, cv2.FILLED)
    cv2.circle(frame, (ix, iy), 7, color, cv2.FILLED)

    pulse += 0.35
    radius = int(6 + (np.sin(pulse) + 1) / 2 * 14)
    cv2.circle(frame, (cx, cy), radius, color, 2)
    cv2.circle(frame, (cx, cy), 5, color, cv2.FILLED)
