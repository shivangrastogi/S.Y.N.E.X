import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import time
import os
import sys

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class VisualCortex:
    def __init__(self, executor_engine=None):
        self.executor = executor_engine
        self.is_running = False
        self.model_path = 'data/models/hand_landmarker.task'
        
        # Initialize Tasks API
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.detector = vision.HandLandmarker.create_from_options(options)
        print("Visual Cortex online (Modern API).")

    def start(self):
        self.is_running = True
        cap = cv2.VideoCapture(0)
        
        while self.is_running:
            success, img = cap.read()
            if not success: break
            
            # Convert to RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
            
            # Detect in Video Mode (needs timestamp)
            timestamp_ms = int(time.time() * 1000)
            detection_result = self.detector.detect_for_video(mp_image, timestamp_ms)
            
            if detection_result.hand_landmarks:
                for hand_lms in detection_result.hand_landmarks:
                    self.detect_gesture(hand_lms)
                    
            time.sleep(0.01)
        cap.release()

    def detect_gesture(self, landmarks):
        # Index 8 is Tip, 6 is PIP joint
        index_up = landmarks[8].y < landmarks[6].y
        # Middle 12 is Tip, 10 is PIP joint
        middle_up = landmarks[12].y < landmarks[10].y
        
        if index_up and not middle_up:
            print("Gesture Detected: Index Up")
        elif index_up and middle_up:
            print("Gesture Detected: Peace Sign")

    def stop(self):
        self.is_running = False

if __name__ == "__main__":
    vc = VisualCortex()
    try:
        vc.start()
    except KeyboardInterrupt:
        vc.stop()
