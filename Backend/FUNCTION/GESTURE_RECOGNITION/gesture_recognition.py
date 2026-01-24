import cv2
import mediapipe as mp
import numpy as np
import time
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
from ctypes import windll

# --- Initialization ---

# MediaPipe
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)

# Pycaw for Windows audio
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume_control = interface.QueryInterface(IAudioEndpointVolume)

user32 = windll.user32  # For locking the workstation (sleep/lock)

VOLUME_STEP = 0.08
DEBOUNCE_TIME = 1.2
CMD_TIMES = {}

def debounce(cmd):
    curr = time.time()
    if CMD_TIMES.get(cmd, 0) < curr - DEBOUNCE_TIME:
        CMD_TIMES[cmd] = curr
        return True
    return False

# --- Gesture Logic ---

def count_fingers(landmarks):
    # Counts fingers up (for simplified palm and peace detection)
    tips = [8, 12, 16, 20]
    cnt = 0
    for i, tip in enumerate(tips):
        if landmarks[tip].y < landmarks[tip-2].y:
            cnt += 1
    return cnt

def is_fist(landmarks):
    # All fingertips below PIP joints
    return all(landmarks[tip].y > landmarks[tip-2].y for tip in [8,12,16,20]) and \
           (landmarks[4].x < landmarks[3].x if landmarks[17].x < landmarks[0].x else landmarks[4].x > landmarks[3].x)

def is_palm(landmarks):
    # All fingertips above PIP joints and spread apart
    return all(landmarks[tip].y < landmarks[tip-2].y for tip in [8,12,16,20]) and \
           abs(landmarks[8].x - landmarks[20].x) > 0.4  # spread pinky & index

def is_thumb_up(landmarks):
    # Thumb up, others down: thumb tip much higher than IP and fingers folded
    thumb = landmarks[4].y < landmarks[3].y < landmarks[2].y
    others = all(landmarks[tip].y > landmarks[tip-2].y for tip in [8,12,16,20])
    return thumb and others

def is_thumb_down(landmarks):
    # Thumb down, others down: thumb tip much lower than IP and fingers folded
    thumb = landmarks[4].y > landmarks[3].y > landmarks[2].y
    others = all(landmarks[tip].y > landmarks[tip-2].y for tip in [8,12,16,20])
    return thumb and others

def is_peace(landmarks):
    # Index and middle up, others folded
    return (landmarks[8].y < landmarks[6].y and
            landmarks[12].y < landmarks[10].y and
            landmarks[16].y > landmarks[14].y and
            landmarks[20].y > landmarks[18].y and
            landmarks[4].y > landmarks[3].y)

def gesture_action(landmarks):
    if is_fist(landmarks):
        if debounce("sleep"):
            print("[Gesture] Sleep: Locking workstation.")
            user32.LockWorkStation()
        return "Sleep (Fist)"
    elif is_palm(landmarks):
        if debounce("mute"):
            current_mute = volume_control.GetMute()
            volume_control.SetMute(not current_mute, None)
            print(f"[Gesture] {'Mute' if not current_mute else 'Unmute'}")
        return "Mute/Unmute (Open Palm)"
    elif is_thumb_up(landmarks):
        if debounce("vol_up"):
            v = volume_control.GetMasterVolumeLevelScalar()
            volume_control.SetMasterVolumeLevelScalar(min(1.0, v + VOLUME_STEP), None)
            print("[Gesture] Volume Up")
        return "Volume Up (Thumbs Up)"
    elif is_thumb_down(landmarks):
        if debounce("vol_down"):
            v = volume_control.GetMasterVolumeLevelScalar()
            volume_control.SetMasterVolumeLevelScalar(max(0.0, v - VOLUME_STEP), None)
            print("[Gesture] Volume Down")
        return "Volume Down (Thumbs Down)"
    elif is_peace(landmarks):
        if debounce("toggle_playback"):
            print("[Gesture] Peace (could map to play/pause or custom action)")
            # Placeholder: Add your action here if desired.
        return "Peace/Custom Action"
    else:
        return "No recognized gesture"

# --- Main Loop ---

def move_window_bottom_right(winname, w, h):
    # Set your display resolution here!
    from screeninfo import get_monitors
    scr = get_monitors()[0]
    screen_w, screen_h = scr.width, scr.height
    cv2.moveWindow(winname, screen_w - w, screen_h - h)

def main():
    cap = cv2.VideoCapture(0)
    winname = "Jarvis Gesture Control"
    first_frame = True

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)
        gesture = "Show Gesture..."
        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                try:
                    gesture = gesture_action(hand_landmarks.landmark)
                except Exception as e:
                    gesture = "Error"
        cv2.putText(frame, f"{gesture}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    1.4, (0,255,0), 3)
        cv2.imshow(winname, frame)
        if first_frame:
            move_window_bottom_right(winname, frame.shape[1], frame.shape[0])
            first_frame = False
        if cv2.waitKey(1) & 0xFF == 27:
            break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
