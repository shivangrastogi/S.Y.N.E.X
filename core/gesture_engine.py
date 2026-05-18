"""Real-time hand gesture controller — 12 useful gestures, MediaPipe-driven.

Subscribes to VisionEngine, runs MediaPipe Hands on each frame, classifies
discrete gestures, and emits a high-level event. A debouncer prevents
rapid re-fire of the same gesture.

Full action map (see DEFAULT_ACTIONS)
-------------------------------------

  GESTURE              REAL-WORLD USE CASE                    ACTION
  -----------------    ------------------------------------   --------------------------
  fist (hold)          Step away from desk fast               LockWorkStation
  open palm (hold)     Mid-cooking, finished a video step     Media play/pause
  swipe ← / →          One-hand window cycling                Alt+Tab / Ctrl+Tab (browser)
  swipe ↑ / ↓          Reading a recipe with wet hands        PgUp / PgDn (scroll)
  thumbs up / down     Hands on keyboard, music too loud      Volume up / down
  peace (V)            Capture a chord chart / recipe step    Win+Shift+S snip-tool
  pinch (thumb+index)  Kids burst in mid-call                 Toggle mic mute (pycaw)
  three fingers up     Current song is bad                    VK_MEDIA_NEXT_TRACK
  OK sign (👌)         Want to launch something fast          Open AERIS command palette

Browser-aware: GetForegroundWindow + GetWindowText looks for chrome /
brave / edge / firefox / opera / vivaldi / arc in the title; matched →
horizontal swipes route to Ctrl+Tab / Ctrl+Shift+Tab so we cycle tabs
instead of windows.

Detection details
-----------------
* Static gestures (peace, three_up, pinch, ok_sign) require ~0.35 s of
  steady hold before firing — keeps natural hand transitions from
  triggering accidental actions.
* Pinch threshold: thumb-tip ↔ index-tip distance < ~0.045 of frame
  width. Discriminates from incidental proximity but loose enough to
  not require perfect contact.
* Vertical swipes use the same wrist-position track as horizontal
  ones, with axis selection by dominant displacement.
* All actions sit behind a 1.4 s cooldown so a held gesture doesn't
  fire repeatedly.

Fail-safes
----------
* mediapipe missing  → engine stays disabled, helpful install message
* camera unavailable → ditto
* pycaw missing      → pinch falls back to VK_F19 (user can map their
                       meeting-app mic-mute hotkey to that key)
* any exception inside the per-frame callback is logged and swallowed
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
_VK_LWIN       = 0x5B
_VK_S          = 0x53
_VK_W          = 0x57
_VK_ESCAPE     = 0x1B
_VK_RETURN     = 0x0D   # Enter
_VK_F5         = 0x74
_VK_RIGHT      = 0x27
_VK_LEFT       = 0x25
_VK_OEM_PLUS   = 0xBB   # '=' / '+' key (for Ctrl+= zoom in)
_VK_OEM_MINUS  = 0xBD   # '-' / '_' key (for Ctrl+- zoom out)
_VK_PRIOR      = 0x21   # Page Up
_VK_NEXT       = 0x22   # Page Down
_VK_VOLUME_UP  = 0xAF
_VK_VOLUME_DN  = 0xAE
_VK_MEDIA_PLAY_PAUSE = 0xB3
_VK_MEDIA_NEXT_TRACK = 0xB0
_VK_MEDIA_PREV_TRACK = 0xB1

# mouse_event flags for cursor-mode click simulation
_MOUSEEVENTF_LEFTDOWN  = 0x0002
_MOUSEEVENTF_LEFTUP    = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP   = 0x0010

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


def _media_next_track() -> None:
    _tap(_VK_MEDIA_NEXT_TRACK)


def _media_prev_track() -> None:
    _tap(_VK_MEDIA_PREV_TRACK)


def _scroll_page(direction: str) -> None:
    """direction ∈ {'up','down'}. Sends PgUp / PgDn to the foreground window —
    most browsers / readers / PDF viewers scroll by one viewport per press.
    """
    _tap(_VK_PRIOR if direction == "up" else _VK_NEXT)


def _screenshot_snip() -> None:
    """Open the Windows Snipping Tool (Win+Shift+S). Captures any region; the
    snip is auto-copied to the clipboard and a toast notification offers to
    edit it. Less intrusive than full-screen Win+PrtScn and is the modern
    Windows-native way to grab a region.
    """
    _press(_VK_LWIN); _press(_VK_LSHIFT)
    try:
        _tap(_VK_S)
    finally:
        _release(_VK_LSHIFT); _release(_VK_LWIN)


def _ctrl_key(vk: int) -> None:
    """Press Ctrl + ``vk`` then release. Used for zoom in/out shortcuts."""
    _press(_VK_LCONTROL)
    try:
        _tap(vk)
    finally:
        _release(_VK_LCONTROL)


def _zoom_in() -> None:
    _ctrl_key(_VK_OEM_PLUS)


def _zoom_out() -> None:
    _ctrl_key(_VK_OEM_MINUS)


def _esc_dismiss() -> None:
    """Send Escape — closes most dialogs, dismisses notifications."""
    _tap(_VK_ESCAPE)


def _set_cursor_pos(x: int, y: int) -> None:
    try:
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    except Exception:
        pass


def _mouse_click_left() -> None:
    try:
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.04)
        ctypes.windll.user32.mouse_event(_MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    except Exception:
        pass


def _screen_size() -> tuple[int, int]:
    try:
        u32 = ctypes.windll.user32
        # SM_CXVIRTUALSCREEN / SM_CYVIRTUALSCREEN — full multi-monitor bounding box.
        return (u32.GetSystemMetrics(78), u32.GetSystemMetrics(79))
    except Exception:
        return (1920, 1080)


def _focus_aeris_window() -> None:
    """Bring the AERIS GUI to front. Used by clap = wake."""
    try:
        # Reuse the same WM_USER message the single-instance focus path
        # uses, posted to every visible window — only AERIS' nativeEvent
        # responds.
        from core.single_instance import WM_AERIS_FOCUS
        u32 = ctypes.windll.user32
        from ctypes import wintypes
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        buf = ctypes.create_unicode_buffer(256)
        def _cb(hwnd, _lparam):
            if not u32.IsWindowVisible(hwnd):
                return True
            u32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.startswith("A.E.R.I.S"):
                u32.PostMessageW(hwnd, WM_AERIS_FOCUS, 0, 0)
            return True
        u32.EnumWindows(EnumWindowsProc(_cb), 0)
    except Exception as e:
        log.warning("[gestures] focus_aeris failed: %s", e)


def _mute_mic_toggle() -> str | None:
    """Toggle the default-input device's mute via pycaw if available.

    Returns the new state ("muted" / "unmuted") so the gesture-engine
    listener can surface a toast. Returns None when pycaw is missing —
    the caller can decide to fall back (e.g. simulate the user's mic-mute
    hotkey in their meeting app).
    """
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL  # type: ignore
    except Exception:
        return None
    try:
        # GetMicrophone() returns the default capture endpoint.
        mic = AudioUtilities.GetMicrophone()
        if mic is None:
            return None
        interface = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        muted = bool(vol.GetMute())
        vol.SetMute(not muted, None)
        return "unmuted" if muted else "muted"
    except Exception as e:
        log.warning("[gestures] mic mute toggle failed: %s", e)
        return None


# --------------------------------------------------------------------------- #
#  Gesture classification                                                     #
# --------------------------------------------------------------------------- #

# MediaPipe Hand landmark indices we care about.
_WRIST = 0
_TIPS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
_PIPS = {"thumb": 3, "index": 6, "middle": 10, "ring": 14, "pinky": 18}
_MCPS = {"thumb": 2, "index": 5, "middle": 9, "ring": 13, "pinky": 17}

# Pinch threshold: tip-to-tip distance < this many units (landmark
# coordinates are normalised 0..1 across the image) counts as a
# touch. 0.045 ≈ 18 px on a 480-tall frame — tighter than incidental
# proximity, looser than perfect contact.
_PINCH_TOUCH_DIST = 0.045


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


def _dist(a, b) -> float:
    """Euclidean distance in the (x,y) plane of two MediaPipe landmarks."""
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _classify_static(lm, hand_label: str) -> str:
    """Classify into one of:
        fist, open_palm, thumbs_up, thumbs_down, point,
        peace, three_up, pinch, ok_sign, none
    """
    states = {f: _finger_extended(lm, f, hand_label) for f in _TIPS}
    n_ext = sum(1 for f, v in states.items() if f != "thumb" and v)

    # Compute index↔thumb tip distance early — pinch & ok_sign both
    # require the fingertips to be touching.
    thumb_index_d = _dist(lm[_TIPS["thumb"]], lm[_TIPS["index"]])
    pinched = thumb_index_d < _PINCH_TOUCH_DIST

    if n_ext == 0:
        if pinched:
            # Closed fist with thumb+index touching reads as a generic
            # "fist" — keep the original semantics so the lock-screen
            # binding still works as expected.
            return "fist"
        if states["thumb"]:
            tip_y = lm[_TIPS["thumb"]].y
            wrist_y = lm[_WRIST].y
            return "thumbs_up" if tip_y < wrist_y - 0.03 else "thumbs_down"
        return "fist"

    # ── OK sign — thumb+index touching, other three fingers extended ──
    # Distinct from "pinch" by requiring the middle/ring/pinky to be UP.
    if pinched and states["middle"] and states["ring"] and states["pinky"]:
        return "ok_sign"

    # ── Pinch — thumb+index touching, other three CURLED ──
    # Reads as a "delicate hold" — perfect for a mute-toggle gesture
    # (small, easy to do silently in a meeting).
    if pinched and not states["middle"] and not states["ring"] and not states["pinky"]:
        return "pinch"

    # ── Peace sign (V) — index + middle extended, ring + pinky curled ──
    # The thumb is don't-care because people vary in whether they tuck it.
    if states["index"] and states["middle"] and not states["ring"] and not states["pinky"]:
        return "peace"

    # ── Three fingers up — index + middle + ring extended, pinky curled,
    #     thumb don't-care. Distinct from open_palm (which is 4+).
    if (states["index"] and states["middle"] and states["ring"]
            and not states["pinky"]):
        return "three_up"

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
    # Wave detection: track x-velocity sign changes inside a sliding window.
    wave_track: deque = field(default_factory=lambda: deque(maxlen=20))
    # Two-handed gestures: rolling distance between the two hand wrists.
    two_hand_track: deque = field(default_factory=lambda: deque(maxlen=20))
    # Cursor mode: smoothed cursor position + last pinch state.
    cursor_x: float = 0.0
    cursor_y: float = 0.0
    cursor_initialised: bool = False
    cursor_was_pinched: bool = False
    # Air-stroke recognition: index-fingertip trail while in pointing pose.
    stroke_track: list = field(default_factory=list)   # list of (t, x, y)
    stroke_started_at: float = 0.0


def _mute_mic_action() -> None:
    """Bound to the pinch gesture. Reports via toast if pycaw missing."""
    res = _mute_mic_toggle()
    if res is None:
        # Fall back: tap a rare key combo a user can map to mic-mute in
        # their meeting app's hotkey settings (Teams / Zoom / Meet).
        # F19 is rarely bound — safe default.
        _tap(0x82)   # VK_F19
        return
    log.info("[gestures] mic %s", res)


def _open_palette_action() -> None:
    """The actual palette UI lives in main_window; this handler just
    emits a no-op key tap so the listener wakes the GUI. main_window
    subscribes to the "ok_sign" listener event and toggles its own
    CommandPalette in response — see GestureEngine.add_listener.
    """
    pass


def _clap_wake_action() -> None:
    """Bring AERIS to front (the GUI's nativeEvent handler picks up the
    posted WM_AERIS_FOCUS and restores+activates the window).
    """
    _focus_aeris_window()


def _refresh_page() -> None:
    """F5 — air-circle binding. Works in most browsers and explorers."""
    _tap(_VK_F5)


def _close_tab() -> None:
    """Ctrl+W — air-X binding (close window/tab in most apps)."""
    _ctrl_key(_VK_W)


def _enter_confirm() -> None:
    """Enter — air-check binding (confirm dialog / submit form)."""
    _tap(_VK_RETURN)


def _arrow_right() -> None:
    """Right arrow — air-arrow binding (next slide / next photo / etc.)."""
    _tap(_VK_RIGHT)


DEFAULT_ACTIONS: dict[str, Callable[[], None]] = {
    # ── original 6 ──
    "fist":            _lock_screen,
    "swipe_left":      lambda: _smart_swipe("left"),
    "swipe_right":     lambda: _smart_swipe("right"),
    "thumbs_up":       lambda: _volume("up", 3),
    "thumbs_down":     lambda: _volume("down", 3),
    "open_palm_hold":  _media_play_pause,
    # ── round 2 (6) ──
    "peace":           _screenshot_snip,
    "pinch":           _mute_mic_action,
    "three_up":        _media_next_track,
    "ok_sign":         _open_palette_action,
    "swipe_up":        lambda: _scroll_page("up"),
    "swipe_down":      lambda: _scroll_page("down"),
    # ── round 3 (advanced) — 5 new ──
    "two_palm_spread": _zoom_in,           # Both palms apart → Ctrl++
    "two_palm_pinch":  _zoom_out,          # Both palms together → Ctrl+-
    "clap":            _clap_wake_action,  # Both hands clap → focus AERIS
    "wave":            _esc_dismiss,       # Open palm rapid L/R → Esc
    "long_fist":       _open_palette_action,  # Fist held 3s+ → palette toggle
    # ── round 4 (stroke recognition) — 4 new ──
    "stroke_circle":      _refresh_page,    # Index-finger circle → F5
    "stroke_x":           _close_tab,       # Index-finger X → Ctrl+W
    "stroke_check":       _enter_confirm,   # Index-finger check → Enter
    "stroke_arrow_right": _arrow_right,     # Index-finger arrow → Right
}

_GESTURE_COOLDOWN_S = 1.4
_FIST_HOLD_S = 0.6           # short fist (0.6s)  = lock screen
_LONG_FIST_S = 3.0           # long  fist (3.0s) = palette toggle (deliberate)
_PALM_HOLD_S = 0.9           # palm steady for ~0.9s = play/pause toggle
_HOLD_S = 0.35               # static-pose gestures (peace, ok_sign, pinch,
                             #   three_up) need this much steady time before
                             #   firing — avoids misfires during natural hand
                             #   transitions through these poses.

# Two-handed zoom: distance between wrist centers, normalised 0..1.
_TWO_HAND_DELTA_THRESH = 0.15   # ≥15% rapid change in distance = zoom event
_TWO_HAND_WINDOW_S = 0.5

# Wave detection: x-direction reversals.
_WAVE_REVERSALS = 2             # ≥2 sign-flips in window
_WAVE_AMPLITUDE = 0.15          # min x-spread to count
_WAVE_WINDOW_S = 0.6

# Clap: hand-distance rapid drop to inside this absolute threshold.
_CLAP_CONVERGE_DIST = 0.18      # final inter-hand distance considered "clap"
_CLAP_CONVERGE_DROP = 0.20      # distance must drop by this much in 0.4s

# Air-stroke recognition: track index fingertip when in "point" pose
# (only index extended). Buffer fills until either the time limit OR
# the user transitions out of point — then we classify.
_STROKE_MIN_POINTS = 12
_STROKE_MAX_DURATION_S = 2.0
_STROKE_MIN_BBOX = 0.10         # tiny strokes don't count — needs ≥10% of frame


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
        # Cursor-mode toggle (independent of `_enabled` — gesture
        # recognition stays on; the per-frame loop also drives the
        # mouse when this is True).
        self._cursor_mode = False
        self._screen_w, self._screen_h = _screen_size()

    # ----------- init / status ----------- #

    def _init_mediapipe(self) -> bool:
        """Initialise MediaPipe Hands with ``max_num_hands=2`` so the
        engine can recognise two-handed gestures (zoom / clap) AND
        single-hand gestures alike.

        Tries the legacy ``mp.solutions.hands`` API first; on newer
        mediapipe (where ``solutions`` was removed) falls through to
        the Tasks API using the project's bundled
        ``hand_landmarker.task`` model.
        """
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
                    max_num_hands=2,
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
                num_hands=2,
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

    # ── cursor-mode toggle (advanced) ──────────────────────────────

    def is_cursor_mode(self) -> bool:
        with self._lock:
            return self._cursor_mode

    def set_cursor_mode(self, on: bool) -> bool:
        """Turn cursor mode on/off. Returns the new state. Requires the
        gesture engine to be running (``start()``) so frames flow.
        """
        with self._lock:
            self._cursor_mode = bool(on)
            # Reset smoothing state on toggle so the cursor doesn't
            # snap from a stale position.
            self._state.cursor_initialised = False
            self._state.cursor_was_pinched = False
        log.info("[gestures] cursor mode %s", "ON" if on else "OFF")
        return self._cursor_mode

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

        # ── Detect 1-2 hands ──
        hands: list[tuple] = []   # list of (landmarks, hand_label) pairs

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
                self._state.wave_track.clear()
                self._state.two_hand_track.clear()
                return
            for i, lms in enumerate(res.hand_landmarks):
                label = "Right"
                try:
                    if res.handedness and i < len(res.handedness):
                        label = res.handedness[i][0].category_name
                except Exception:
                    pass
                hands.append((lms, label))
        else:
            try:
                res = self._mp_hands.process(rgb)
            except Exception:
                return
            if not res.multi_hand_landmarks:
                self._state.palm_track.clear()
                self._state.wave_track.clear()
                self._state.two_hand_track.clear()
                return
            for i, h in enumerate(res.multi_hand_landmarks):
                label = "Right"
                if res.multi_handedness and i < len(res.multi_handedness):
                    try:
                        label = res.multi_handedness[i].classification[0].label
                    except Exception:
                        pass
                hands.append((h.landmark, label))

        now = time.monotonic()
        st = self._state

        # ── Two-handed gestures (zoom + clap) ──
        if len(hands) >= 2:
            self._handle_two_hands(hands, now)
        else:
            st.two_hand_track.clear()

        # ── Single-hand gestures use the FIRST hand only ──
        lms = hands[0][0]
        hand_label = hands[0][1]
        static = _classify_static(lms, hand_label)

        # ── Cursor mode (advanced) — drives mouse from index finger ──
        if self._cursor_mode:
            self._handle_cursor(lms)

        # ----- swipe (open_palm motion: horizontal OR vertical) + wave -----
        if static == "open_palm":
            wrist_x = lms[_WRIST].x
            wrist_y = lms[_WRIST].y
            st.palm_track.append((now, wrist_x, wrist_y))
            # Wave detection: rapid x-direction reversals while palm open.
            st.wave_track.append((now, wrist_x))
            if self._is_waving(now):
                self._emit("wave")
                st.wave_track.clear()
            else:
                # Only emit swipes if NOT in the middle of a wave.
                self._maybe_emit_swipe(now)
            if st.palm_hold_since == 0.0:
                st.palm_hold_since = now
            elif now - st.palm_hold_since >= _PALM_HOLD_S and not self._is_palm_moving():
                self._emit("open_palm_hold")
                st.palm_hold_since = 0.0
        else:
            st.palm_track.clear()
            st.palm_hold_since = 0.0
            st.wave_track.clear()

        # ----- fist hold: 0.6s = lock, 3.0s = long_fist (palette) -----
        # last_static_at acts as the FIST-START timestamp. We never bump
        # it forward while the fist is held — _emit's per-name cooldown
        # is what prevents rapid refire. Once long_fist fires we PARK
        # the start time far in the future so the SAME continuous hold
        # doesn't refire long_fist; it resets only when the user lets go.
        if static == "fist":
            if st.last_static != "fist":
                st.last_static_at = now
            held = now - st.last_static_at
            if held >= _LONG_FIST_S:
                self._emit("long_fist")
                st.last_static_at = now + 1e6   # parked
            elif held >= _FIST_HOLD_S:
                self._emit("fist")

        # ----- thumbs up / down — fire immediately -----
        elif static in ("thumbs_up", "thumbs_down"):
            self._emit(static)

        # ----- point: capture index-fingertip trail for air-stroke -----
        # Trail is collected while the user is in pointing pose; when
        # they transition out OR the trail gets long enough, we classify
        # the shape and emit a stroke_* event if it matches.
        if static == "point":
            tip = lms[_TIPS["index"]]
            if not st.stroke_track:
                st.stroke_started_at = now
            st.stroke_track.append((now, tip.x, tip.y))
            elapsed = now - st.stroke_started_at
            if elapsed >= _STROKE_MAX_DURATION_S:
                self._classify_and_emit_stroke()
                st.stroke_track = []
        elif st.stroke_track:
            # User left pointing pose — classify whatever we got.
            self._classify_and_emit_stroke()
            st.stroke_track = []

        # ----- hold-required static poses (peace, three_up, pinch, ok_sign)
        # Fire only after the pose has been STEADY for _HOLD_S. This kills
        # spurious matches during natural hand motion through these
        # configurations and gives the user a chance to "commit" the
        # gesture instead of triggering an action they didn't mean.
        elif static in ("peace", "three_up", "pinch", "ok_sign"):
            if st.last_static == static:
                if now - st.last_static_at >= _HOLD_S:
                    self._emit(static)
                    # Bump so we don't refire until cooldown elapses.
                    st.last_static_at = now + _GESTURE_COOLDOWN_S
            else:
                st.last_static_at = now

        st.last_static = static

    # ── Advanced: two-handed gestures ──────────────────────────────

    def _handle_two_hands(self, hands: list, now: float) -> None:
        """Detect open-palm zoom (spread/pinch) + clap (rapid converge).

        ``hands`` is a list of (landmarks, label) pairs, length 2+.
        Uses wrist x/y as the hand-center proxy (cheap, stable).
        """
        st = self._state
        lm_a = hands[0][0]; lm_b = hands[1][0]
        # Both palms open?  Required for zoom; clap can happen with any pose.
        n_a = sum(1 for f in ("index", "middle", "ring", "pinky")
                  if _finger_extended(lm_a, f, hands[0][1]))
        n_b = sum(1 for f in ("index", "middle", "ring", "pinky")
                  if _finger_extended(lm_b, f, hands[1][1]))
        both_palm = n_a >= 3 and n_b >= 3

        # Distance between wrist centers (normalised 0..1 of frame width).
        dx = lm_a[_WRIST].x - lm_b[_WRIST].x
        dy = lm_a[_WRIST].y - lm_b[_WRIST].y
        dist = (dx * dx + dy * dy) ** 0.5
        st.two_hand_track.append((now, dist))

        # Only the LAST ~_TWO_HAND_WINDOW_S of samples are interesting.
        cutoff = now - _TWO_HAND_WINDOW_S
        recent = [(t, d) for t, d in st.two_hand_track if t >= cutoff]
        if len(recent) < 4:
            return

        d_start = recent[0][1]
        d_end = recent[-1][1]
        delta = d_end - d_start

        # ── Clap: rapid converge to a small distance ──
        # Distinct from zoom-out because the END distance is very small
        # (hands actually touching) AND the drop is larger than the zoom
        # threshold.
        if (-delta) >= _CLAP_CONVERGE_DROP and d_end <= _CLAP_CONVERGE_DIST:
            self._emit("clap")
            st.two_hand_track.clear()
            return

        # ── Zoom: both palms open, big enough motion in one direction ──
        if both_palm and abs(delta) >= _TWO_HAND_DELTA_THRESH:
            if delta > 0:
                self._emit("two_palm_spread")
            else:
                self._emit("two_palm_pinch")
            st.two_hand_track.clear()

    # ── Advanced: wave detection ───────────────────────────────────

    def _is_waving(self, now: float) -> bool:
        """Open palm waving back-and-forth left↔right ≥ 2 reversals
        within ``_WAVE_WINDOW_S``. Amplitude must exceed
        ``_WAVE_AMPLITUDE`` so a tiny tremor isn't a wave."""
        st = self._state
        cutoff = now - _WAVE_WINDOW_S
        recent = [(t, x) for t, x in st.wave_track if t >= cutoff]
        if len(recent) < 6:
            return False
        xs = [x for _, x in recent]
        amp = max(xs) - min(xs)
        if amp < _WAVE_AMPLITUDE:
            return False
        # Count sign changes of finite differences.
        diffs = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        reversals = 0
        prev_sign = 0
        for d in diffs:
            sgn = 1 if d > 0.005 else (-1 if d < -0.005 else 0)
            if sgn == 0:
                continue
            if prev_sign != 0 and sgn != prev_sign:
                reversals += 1
            prev_sign = sgn
        return reversals >= _WAVE_REVERSALS

    # ── Advanced: cursor mode ──────────────────────────────────────

    def _handle_cursor(self, lms) -> None:
        """Drive the system mouse from the first hand's index fingertip.

        Smoothing: exponential moving average to kill jitter (alpha 0.4).
        Clicking: pinch (thumb tip + index tip touching) triggers a single
        left click on the falling edge of the pinch (so a long pinch
        doesn't repeat-fire).
        """
        st = self._state
        # Frame coords are 0..1 of the camera view — mirror x because the
        # camera flips left-right relative to the user POV.
        tip = lms[_TIPS["index"]]
        # Map [0.1..0.9] of camera view to [0..screen] so the user
        # doesn't have to reach the corner of the frame to hit a screen
        # edge — gives a more usable "active area" the size of the
        # central 80% of the frame.
        nx = max(0.0, min(1.0, (1.0 - tip.x - 0.1) / 0.8))
        ny = max(0.0, min(1.0, (tip.y - 0.1) / 0.8))
        target_x = nx * self._screen_w
        target_y = ny * self._screen_h

        if not st.cursor_initialised:
            st.cursor_x = target_x
            st.cursor_y = target_y
            st.cursor_initialised = True
        else:
            alpha = 0.4
            st.cursor_x += alpha * (target_x - st.cursor_x)
            st.cursor_y += alpha * (target_y - st.cursor_y)

        _set_cursor_pos(st.cursor_x, st.cursor_y)

        # Pinch → click on the falling edge of "is pinched".
        d = _dist(lms[_TIPS["thumb"]], lms[_TIPS["index"]])
        is_pinched = d < _PINCH_TOUCH_DIST
        if is_pinched and not st.cursor_was_pinched:
            _mouse_click_left()
        st.cursor_was_pinched = is_pinched

    # ── Advanced: air-stroke classifier ────────────────────────────

    def _classify_and_emit_stroke(self) -> None:
        """Classify the captured pointing-trail into one of:
        circle / X / check / arrow_right / (none).

        Pure geometric heuristics — no ML model. The four shapes were
        chosen because they have distinct enough statistics that simple
        ratios + endpoint checks separate them cleanly.
        """
        pts = self._state.stroke_track
        if len(pts) < _STROKE_MIN_POINTS:
            return
        xs = [p[1] for p in pts]
        ys = [p[2] for p in pts]
        bbox_w = max(xs) - min(xs)
        bbox_h = max(ys) - min(ys)
        if max(bbox_w, bbox_h) < _STROKE_MIN_BBOX:
            return   # too small — probably hand tremor, not a stroke

        # Mirror x (camera flips left↔right relative to the user POV).
        xs = [1.0 - x for x in xs]
        bbox_w = max(xs) - min(xs)
        x0, y0 = xs[0], ys[0]
        xN, yN = xs[-1], ys[-1]
        end_gap = ((xN - x0) ** 2 + (yN - y0) ** 2) ** 0.5

        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        radii = [((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for x, y in zip(xs, ys)]
        mean_r = sum(radii) / len(radii)
        if mean_r <= 0:
            return
        # Coefficient-of-variation: low for a circle, high for line/check/X
        cv = (sum((r - mean_r) ** 2 for r in radii) / len(radii)) ** 0.5 / mean_r

        # Net translation along x (positive = stroke moved rightward).
        net_dx = xN - x0
        # Net |y| range used to disambiguate horizontal arrow vs scribble.
        net_dy = yN - y0

        log.debug("[stroke] n=%d bbox=(%.2f,%.2f) end_gap=%.3f cv=%.2f net=(%.2f,%.2f)",
                  len(pts), bbox_w, bbox_h, end_gap, cv, net_dx, net_dy)

        # ── Circle ──
        # Trail nearly closes (end near start) AND radii are uniform.
        # bbox roughly square (aspect within 2:1) so a flat ellipse
        # doesn't pass.
        aspect = max(bbox_w, bbox_h) / max(0.001, min(bbox_w, bbox_h))
        if end_gap < 0.10 and cv < 0.30 and aspect < 2.0:
            self._emit("stroke_circle")
            return

        # ── Arrow right ──
        # Big horizontal travel, small absolute vertical drift, no
        # closure. Bbox is wide.
        if net_dx > 0.25 and abs(net_dy) < 0.12 and bbox_w > 1.8 * bbox_h:
            self._emit("stroke_arrow_right")
            return

        # ── Check mark ──
        # Goes down-then-up-right. Detect by finding the minimum-y
        # point in the trail (the "valley") and confirming the start
        # is up-and-left of it, the end is up-and-right of it.
        min_y_idx = max(range(len(ys)), key=lambda i: ys[i])  # max y = lowest screen point
        valley_x, valley_y = xs[min_y_idx], ys[min_y_idx]
        if (min_y_idx > len(ys) * 0.2 and min_y_idx < len(ys) * 0.8
                and ys[0] < valley_y - 0.05         # start above valley
                and ys[-1] < valley_y - 0.05        # end above valley
                and xs[0] < valley_x                # start left of valley
                and xs[-1] > valley_x               # end right of valley
                and (xs[-1] - xs[0]) > 0.10):
            self._emit("stroke_check")
            return

        # ── X (two crossing diagonals) ──
        # Find the trajectory's farthest-from-center point. If the trail
        # passes near the bbox center MULTIPLE times in opposite directions,
        # it's two strokes crossing.
        # Cheap proxy: count midpoint crossings of x=cx AND y=cy.
        x_cross = sum(1 for i in range(1, len(xs))
                      if (xs[i - 1] - cx) * (xs[i] - cx) < 0)
        y_cross = sum(1 for i in range(1, len(ys))
                      if (ys[i - 1] - cy) * (ys[i] - cy) < 0)
        if x_cross >= 2 and y_cross >= 2 and aspect < 2.2:
            self._emit("stroke_x")
            return
        # Otherwise: not a recognised stroke. Silent — don't spam events.

    def _is_palm_moving(self) -> bool:
        track = self._state.palm_track
        if len(track) < 4:
            return False
        # Track entries are now (t, x, y) — back-compat with the old
        # (t, x) shape just in case a subclass appends differently.
        xs = [pt[1] for pt in track]
        ys = [pt[2] if len(pt) > 2 else 0.0 for pt in track]
        return (max(xs) - min(xs)) > 0.05 or (max(ys) - min(ys)) > 0.05

    def _maybe_emit_swipe(self, now: float) -> None:
        track = self._state.palm_track
        if len(track) < 6:
            return
        # Use the oldest entry within the last ~0.6s as the start.
        cutoff = now - 0.6
        recent = [pt for pt in track if pt[0] >= cutoff]
        if len(recent) < 4:
            return
        x_start, x_end = recent[0][1], recent[-1][1]
        y_start, y_end = recent[0][2], recent[-1][2]
        dx = x_end - x_start
        dy = y_end - y_start

        # Pick the dominant axis. Threshold ≈ 18 % of normalised
        # coordinates — big enough to require a deliberate motion.
        THRESH = 0.18
        if abs(dx) >= THRESH and abs(dx) > abs(dy):
            # Mirror because webcam horizontally inverts user POV; swipe
            # with the right hand from user POV (left in image) reads as
            # "swipe_right" from the user's perspective.
            self._emit("swipe_left" if dx > 0 else "swipe_right")
            self._state.palm_track.clear()
        elif abs(dy) >= THRESH and abs(dy) > abs(dx):
            # Y axis: smaller-y is HIGHER on screen, so dy < 0 = upward.
            self._emit("swipe_up" if dy < 0 else "swipe_down")
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
