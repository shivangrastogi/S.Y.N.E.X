import cv2
import time
import numpy as np
import mediapipe as mp
import math
from threading import Thread
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

class VolumeGestureController:
    def __init__(self, speak_function=None, ui_notify_function=None):
        """
        speak_function: Optional callable for audio feedback
        ui_notify_function: Optional for UI updates on volume
        """
        try:
            self.mpHands = mp.solutions.hands
            self.hands = self.mpHands.Hands(max_num_hands=1, min_detection_confidence=0.7)
            self.mpDraw = mp.solutions.drawing_utils

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volumeControl = cast(interface, POINTER(IAudioEndpointVolume))
            self.volMin, self.volMax = self.volumeControl.GetVolumeRange()[:2]

            self.cap = cv2.VideoCapture(0)
            self.cap.set(3, 640)  # Width
            self.cap.set(4, 480)  # Height
            self.pTime = 0
            self.running = False

            self.speak = speak_function
            self.ui_notify = ui_notify_function
            self.thread = None
        except Exception as e:
            print(f"[ERROR] Initialization failed: {e}")
            if self.speak:
                self.speak("Failed to initialize gesture control. Check your camera or dependencies.")

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = Thread(target=self._gesture_loop, daemon=True)
        self.thread.start()
        if self.speak:
            self.speak("Hand gesture volume control started.")

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if hasattr(self, 'cap'):
            self.cap.release()
        cv2.destroyAllWindows()
        if self.speak:
            self.speak("Hand gesture volume control stopped.")

    def _gesture_loop(self):
        try:
            while self.running:
                ret, img = self.cap.read()
                if not ret:
                    continue
                img = cv2.flip(img, 1)
                imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                results = self.hands.process(imgRGB)

                lmList = []
                if results.multi_hand_landmarks:
                    handLms = results.multi_hand_landmarks[0]
                    for id, lm in enumerate(handLms.landmark):
                        h, w, _ = img.shape
                        cx, cy = int(lm.x * w), int(lm.y * h)
                        lmList.append((id, cx, cy))

                    self.mpDraw.draw_landmarks(img, handLms, self.mpHands.HAND_CONNECTIONS)
                    x1, y1 = lmList[4][1], lmList[4][2]
                    x2, y2 = lmList[8][1], lmList[8][2]
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                    cv2.circle(img, (x1, y1), 10, (255, 0, 255), -1)
                    cv2.circle(img, (x2, y2), 10, (255, 0, 255), -1)
                    cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
                    cv2.circle(img, (cx, cy), 10, (0, 255, 0), -1)

                    length = math.hypot(x2 - x1, y2 - y1)
                    vol = np.interp(length, [20, 180], [self.volMin, self.volMax])
                    self.volumeControl.SetMasterVolumeLevel(vol, None)
                    volBar = np.interp(length, [20, 180], [400, 150])
                    volPer = np.interp(length, [20, 180], [0, 100])

                    cv2.rectangle(img, (50, 150), (85, 400), (0, 0, 255), 3)
                    cv2.rectangle(img, (50, int(volBar)), (85, 400), (0, 0, 255), -1)
                    cv2.putText(img, f'{int(volPer)} %', (40, 450), cv2.FONT_HERSHEY_PLAIN,
                                2, (255, 255, 255), 2)

                    if self.ui_notify and int(volPer) % 10 == 0:
                        self.ui_notify(int(volPer))

                cTime = time.time()
                fps = 1 / (cTime - self.pTime + 1e-5)
                self.pTime = cTime
                cv2.putText(img, f'FPS: {int(fps)}', (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow("JARVIS Volume Control - Hand Gestures (Press 'q' to quit)", img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop()
                    break
        except Exception as e:
            print(f"[ERROR] Error during gesture loop: {e}")
            if self.speak:
                self.speak("An error occurred in the gesture volume controller.")
            self.stop()
