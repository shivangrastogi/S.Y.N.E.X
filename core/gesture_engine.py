"""Real-time hand gesture controller.

Subscribes to VisionEngine, runs MediaPipe Hands on each frame, classifies
discrete gestures, and emits a high-level event ("fist", "swipe_left",
"thumbs_up", ...). A debouncer prevents rapid re-fire of the same gesture.

Default action map (see DEFAULT_ACTIONS):
    fist            -> lock workstation
    swipe_left      -> Alt+Shift+Tab (window back) OR Ctrl+Shift+Tab in browser
    swipe_right     -> Alt+Tab          OR Ctrl+Tab          in browser
    thumbs_up       -> volume up (3 ticks)
    thumbs_down     -> volume down (3 ticks)
    open_palm_hold  -> media play/pause toggle

Browser detection: GetForegroundWindow + GetWindowText looks for chrome /
brave / edge / firefox / opera in the title; if matched, swipes route to
Ctrl+Tab / Ctrl+Shift+Tab so we cycle tabs instead of windows.

Fail-safes:
  - mediapipe missing -> engine stays disabled and returns helpful message
  - camera unavailable -> ditto
  - any exception inside the per-frame callback is logged and swallowed
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from core.vision_engine import get_vision_engine

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Windows action helpers                                                     #
# --------------------------------------------------------------------------- #

_VK_TAB        = 0x09
_VK_LMENU      = 0xA4   # left Alt
_VK_LCONTROL   = 0xA2
_VK_LSHIFT     = 0xA0
_VK_VOLUME_UP  = 0xAF
_VK_VOLUME_DN  = 0xAE
_VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_KEYUP = 0x0002


def _press(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)


def _release(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _tap(vk: int) -> None:
    _press(vk); time.sleep(0.02); _release(vk)


def _foreground_title() -> str:
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        length = u32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        u32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


_BROWSER_HINTS = ("chrome", "brave", "edge", "firefox", "opera", "vivaldi", "arc ")


def _is_browser_focused() -> bool:
    title = _foreground_title().lower()
    return any(b in title for b in _BROWSER_HINTS)


def _alt_tab(reverse: bool = False) -> None:
    _press(_VK_LMENU)
    try:
        if reverse:
            _press(_VK_LSHIFT)
        time.sleep(0.05)
        _tap(_VK_TAB)
        time.sleep(0.08)
    finally:
        if reverse:
            _release(_VK_LSHIFT)
        _release(_VK_LMENU)


def _ctrl_tab(reverse: bool = False) -> None:
    _press(_VK_LCONTROL)
    try:
        if reverse:
            _press(_VK_LSHIFT)
        _tap(_VK_TAB)
    finally:
        if reverse:
            _release(_VK_LSHIFT)
        _release(_VK_LCONTROL)


def _lock_screen() -> None:
    ctypes.windll.user32.LockWorkStation()


def _smart_swipe(direction: str) -> None:
    """direction in {'left','right'}. Browser → Ctrl+Tab, else Alt+Tab."""
    reverse = (direction == "left")
    if _is_browser_focused():
        _ctrl_tab(reverse=reverse)
    else:
        _alt_tab(reverse=reverse)


def _volume(direction: str, ticks: int = 3) -> None:
    vk = _VK_VOLUME_UP if direction == "up" else _VK_VOLUME_DN
    for _ in range(ticks):
        _tap(vk); time.sleep(0.03)


def _media_play_pause() -> None:
    _tap(_VK_MEDIA_PLAY_PAUSE)


# --------------------------------------------------------------------------- #
#  Gesture classification                                                     #
# --------------------------------------------------------------------------- #

# MediaPipe Hand landmark indices we care about.
_WRIST = 0
_TIPS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
_PIPS = {"thumb": 3, "index": 6, "middle": 10, "ring": 14, "pinky": 18}


def _finger_extended(lm, finger: str, hand_label: str) -> bool:
    """True if the named finger is extended.

    For the four non-thumb fingers, "extended" means the tip is higher (smaller y)
    than its proximal interphalangeal joint. The thumb uses an x-axis test
    that's mirrored for left vs right hand.
    """
    tip_idx = _TIPS[finger]
    pip_idx = _PIPS[finger]
    if finger == "thumb":
        # Mirrored for left hand because the thumb points the other way.
        if hand_label == "Right":
            return lm[tip_idx].x < lm[pip_idx].x
        return lm[tip_idx].x > lm[pip_idx].x
    return lm[tip_idx].y < lm[pip_idx].y


def _classify_static(lm, hand_label: str) -> str:
    """Classify into one of: fist, open_palm, thumbs_up, thumbs_down, point, none."""
    states = {f: _finger_extended(lm, f, hand_label) for f in _TIPS}
    n_ext = sum(1 for f, v in states.items() if f != "thumb" and v)

    if n_ext == 0:
        if states["thumb"]:
            # Thumb out, fist body. Direction by tip-vs-wrist y.
            tip_y = lm[_TIPS["thumb"]].y
            wrist_y = lm[_WRIST].y
            return "thumbs_up" if tip_y < wrist_y - 0.03 else "thumbs_down"
        return "fist"
    if n_ext >= 4:
        return "open_palm"
    if n_ext == 1 and states["index"]:
        return "point"
    return "none"


# --------------------------------------------------------------------------- #
#  Engine                                                                     #
# --------------------------------------------------------------------------- #

@dataclass
class _GestureState:
    last_static: str = "none"
    last_static_at: float = 0.0
    last_emit_at: dict = field(default_factory=dict)
    palm_track: deque = field(default_factory=lambda: deque(maxlen=15))
    palm_hold_since: float = 0.0


DEFAULT_ACTIONS: dict[str, Callable[[], None]] = {
    "fist":            _lock_screen,
    "swipe_left":      lambda: _smart_swipe("left"),
    "swipe_right":     lambda: _smart_swipe("right"),
    "thumbs_up":       lambda: _volume("up", 3),
    "thumbs_down":     lambda: _volume("down", 3),
    "open_palm_hold":  _media_play_pause,
}

_GESTURE_COOLDOWN_S = 1.4
_FIST_HOLD_S = 0.6           # require fist held for ~0.6s before locking
_PALM_HOLD_S = 0.9           # palm steady for ~0.9s = play/pause toggle


class GestureEngine:
    def __init__(self, actions: Optional[dict] = None):
        self._actions = dict(DEFAULT_ACTIONS)
        if actions:
            self._actions.update(actions)
        self._state = _GestureState()
        self._mp_hands = None
        self._lock = threading.RLock()
        self._enabled = False
        self._listeners: list[Callable[[str], None]] = []
        self._mediapipe_ok = self._init_mediapipe()

    # ----------- init / status ----------- #

    def _init_mediapipe(self) -> bool:
        """Try the legacy `mp.solutions.hands` API first; on newer mediapipe
        (where `solutions` was removed) fall through to the Tasks API using
        the project's bundled hand_landmarker.task model."""
        try:
            import mediapipe as mp
        except Exception as e:
            log.info("[gestures] mediapipe missing: %s", e)
            return False
        # Legacy path
        try:
            if hasattr(mp, "solutions"):
                self._mp_hands = mp.solutions.hands.Hands(
                    model_complexity=0,
                    max_num_hands=1,
                    min_detection_confidence=0.7,
                    min_tracking_confidence=0.5,
                )
                self._backend = "legacy"
                return True
        except Exception as e:
            log.info("[gestures] legacy hands init failed: %s", e)
        # Tasks API path
        try:
            from mediapipe.tasks import python as mp_py
            from mediapipe.tasks.python import vision as mp_vis
            import os as _os
            model_path = _os.path.join(
                _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                "data", "models", "hand_landmarker.task",
            )
            if not _os.path.exists(model_path):
                log.warning("[gestures] hand_landmarker.task missing at %s", model_path)
                return False
            base_opts = mp_py.BaseOptions(model_asset_path=model_path)
            opts = mp_vis.HandLandmarkerOptions(
                base_options=base_opts,
                running_mode=mp_vis.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.7,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._mp_hands = mp_vis.HandLandmarker.create_from_options(opts)
            self._backend = "tasks"
            return True
        except Exception as e:
            log.warning("[gestures] tasks API init failed: %s", e)
            return False

    def is_available(self) -> bool:
        return self._mediapipe_ok

    def is_enabled(self) -> bool:
        return self._enabled

    # ----------- public start/stop ----------- #

    def start(self) -> bool:
        if not self._mediapipe_ok:
            return False
        with self._lock:
            if self._enabled:
                return True
            ok = get_vision_engine().subscribe("gestures", self._on_frame)
            if not ok:
                return False
            self._enabled = True
            return True

    def stop(self) -> None:
        with self._lock:
            if not self._enabled:
                return
            get_vision_engine().unsubscribe("gestures")
            self._enabled = False

    def add_listener(self, fn: Callable[[str], None]) -> None:
        """Register a UI callback fired whenever a gesture is recognized."""
        self._listeners.append(fn)

    # ----------- per-frame ----------- #

    def _on_frame(self, frame_bgr) -> None:
        try:
            import cv2
        except Exception:
            return
        try:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        except Exception:
            return

        lms = None
        hand_label = "Right"

        if getattr(self, "_backend", "legacy") == "tasks":
            try:
                import mediapipe as mp
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = int(time.monotonic() * 1000)
                res = self._mp_hands.detect_for_video(mp_image, ts_ms)
            except Exception:
                return
            if not res.hand_landmarks:
                self._state.palm_track.clear()
                return
            lms = res.hand_landmarks[0]
            try:
                if res.handedness and res.handedness[0]:
                    hand_label = res.handedness[0][0].category_name
            except Exception:
                pass
        else:
            try:
                res = self._mp_hands.process(rgb)
            except Exception:
                return
            if not res.multi_hand_landmarks:
                self._state.palm_track.clear()
                return
            lms = res.multi_hand_landmarks[0].landmark
            if res.multi_handedness:
                try:
                    hand_label = res.multi_handedness[0].classification[0].label
                except Exception:
                    pass

        static = _classify_static(lms, hand_label)
        now = time.monotonic()
        st = self._state

        # ----- swipe (open_palm motion) -----
        if static == "open_palm":
            wrist_x = lms[_WRIST].x
            st.palm_track.append((now, wrist_x))
            self._maybe_emit_swipe(now)
            if st.palm_hold_since == 0.0:
                st.palm_hold_since = now
            elif now - st.palm_hold_since >= _PALM_HOLD_S and not self._is_palm_moving():
                self._emit("open_palm_hold")
                st.palm_hold_since = 0.0
        else:
            st.palm_track.clear()
            st.palm_hold_since = 0.0

        # ----- fist hold = lock -----
        if static == "fist":
            if st.last_static == "fist" and now - st.last_static_at >= _FIST_HOLD_S:
                self._emit("fist")
                st.last_static_at = now + _GESTURE_COOLDOWN_S  # extra grace
            elif st.last_static != "fist":
                st.last_static_at = now
        elif static in ("thumbs_up", "thumbs_down"):
            self._emit(static)

        st.last_static = static

    def _is_palm_moving(self) -> bool:
        track = self._state.palm_track
        if len(track) < 4:
            return False
        xs = [x for _, x in track]
        return (max(xs) - min(xs)) > 0.05

    def _maybe_emit_swipe(self, now: float) -> None:
        track = self._state.palm_track
        if len(track) < 6:
            return
        # Use the oldest entry within the last ~0.6s as the start.
        cutoff = now - 0.6
        recent = [(t, x) for t, x in track if t >= cutoff]
        if len(recent) < 4:
            return
        x_start, x_end = recent[0][1], recent[-1][1]
        dx = x_end - x_start
        if abs(dx) < 0.18:
            return
        # Mirror because webcam horizontally inverts user POV; swipe with the
        # right hand from user POV (left in image) is "swipe_right".
        if dx > 0:
            self._emit("swipe_left")
        else:
            self._emit("swipe_right")
        self._state.palm_track.clear()

    def _emit(self, name: str) -> None:
        now = time.monotonic()
        last = self._state.last_emit_at.get(name, 0.0)
        if now - last < _GESTURE_COOLDOWN_S:
            return
        self._state.last_emit_at[name] = now
        action = self._actions.get(name)
        if action:
            try:
                action()
            except Exception as e:
                log.warning("[gestures] action %s raised: %s", name, e)
        for fn in self._listeners:
            try:
                fn(name)
            except Exception:
                pass


# Singleton.
_DEFAULT_ENGINE: Optional[GestureEngine] = None


def get_gesture_engine() -> GestureEngine:
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = GestureEngine()
    return _DEFAULT_ENGINE
