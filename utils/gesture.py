import cv2
import mediapipe as mp
import time
import os
import sys

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class VisualCortex:
    def __init__(self, executor_engine=None):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.executor = executor_engine
        self.is_running = False

    def start(self):
        self.is_running = True
        cap = cv2.VideoCapture(0)
        print("Visual Cortex online. Camera active.")

        while self.is_running:
            success, img = cap.read()
            if not success:
                break

            # Convert to RGB for Mediapipe
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.hands.process(img_rgb)

            if results.multi_hand_landmarks:
                for hand_lms in results.multi_hand_landmarks:
                    # Logic to identify specific gestures
                    self.detect_gesture(hand_lms)
                    # Draw landmarks for debug (optional)
                    # self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)

            # Performance optimization: small sleep
            time.sleep(0.01)

        cap.release()

    def detect_gesture(self, hand_lms):
        """
        Analyze finger positions to detect simple gestures.
        Index 8 is Index Finger Tip, 4 is Thumb Tip, etc.
        """
        landmarks = hand_lms.landmark
        
        # Simple Example: If Index finger tip (8) is above index finger knuckle (6)
        # and other fingers are down, it's a "Point" gesture.
        
        index_up = landmarks[8].y < landmarks[6].y
        middle_up = landmarks[12].y < landmarks[10].y
        
        if index_up and not middle_up:
            # Gesture: Volume Up / One Finger
            if self.executor:
                # self.executor.execute("system_control", {"action": "volume_up"})
                pass
            print("Gesture Detected: Index Up")
            
        elif index_up and middle_up:
            # Gesture: Peace Sign / Two Fingers
            print("Gesture Detected: Peace Sign")

    def stop(self):
        self.is_running = False

if __name__ == "__main__":
    vc = VisualCortex()
    try:
        vc.start()
    except KeyboardInterrupt:
        vc.stop()
