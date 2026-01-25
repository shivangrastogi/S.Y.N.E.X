# BACKEND/gestures/gestures/volume_pinch.py
import numpy as np
from pycaw.pycaw import AudioUtilities
from BACKEND.gestures.config import VOLUME_MIN_RATIO, VOLUME_MAX_RATIO
from BACKEND.gestures.detection.gesture_classifier import dist

devices = AudioUtilities.GetSpeakers()
volume = devices.EndpointVolume

def handle_volume(lm):
    wrist = lm.landmark[0]
    mid = lm.landmark[9]
    thumb = lm.landmark[4]
    index = lm.landmark[8]

    ratio = dist(thumb, index) / dist(mid, wrist)
    vol = np.clip(np.interp(ratio, [VOLUME_MIN_RATIO, VOLUME_MAX_RATIO], [0, 1]), 0, 1)
    volume.SetMasterVolumeLevelScalar(vol, None)
