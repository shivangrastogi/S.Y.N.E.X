# BACKEND/gestures/camera/camera_stream.py
import cv2

class CameraStream:
    def __init__(self, index=0):
        self.cap = cv2.VideoCapture(index)

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()
        cv2.destroyAllWindows()
