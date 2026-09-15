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
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from core.vision_engine import get_vision_engine

log = logging.getLogger(__name__)


def camera_idle_seconds() -> float:
    """Seconds of no-hand-in-frame before the webcam is released.

    ``AERIS_CAMERA_IDLE_S``; **0 (the default) disables the release**, so
    behaviour is unchanged unless you opt in. Read at call time so it can be
    changed without a restart, and so tests can set it.

    Off by default on purpose: releasing the camera means gestures stop
    working until they are switched back on. That is a product decision, not
    a technical one — the machinery is here, the choice is the user's.
    """
    raw = os.environ.get("AERIS_CAMERA_IDLE_S")
    if raw is None or not str(raw).strip():
        return 0.0
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        log.warning("[gestures] bad AERIS_CAMERA_IDLE_S=%r — ignoring", raw)
        return 0.0


@dataclass
class _LandmarkPoint:
    x: float
    y: float
    z: float = 0.0


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


def _foreground_exe_name() -> str:
    """Return the foreground window's process exe name (e.g. 'code.exe'),
    lowercased. '' on any failure / non-Windows host."""
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = ctypes.c_ulong()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            import psutil  # type: ignore
            return (psutil.Process(int(pid.value)).name() or "").lower()
        except Exception:
            return ""
    except Exception:
        return ""


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


def _alt_tab_forward() -> None:
    """Alt+Tab — switch to the next (right-side) app in the alt-tab list."""
    _alt_tab(reverse=False)


def _alt_tab_backward() -> None:
    """Alt+Shift+Tab — cycle backward (toward the left side of the alt-tab list)."""
    _alt_tab(reverse=True)


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


_VOLUME_FALLBACK_STATE: dict = {
    "warned": False,         # only log the missing-pycaw warning once
    "last_pct": None,        # last percentage we tried to push
}


def _set_volume_pct(pct: int) -> bool:
    """Set absolute speaker volume (0..100). Returns True when applied.

    Three-tier strategy:
      1. Modern pycaw — ``AudioDevice.EndpointVolume`` attribute (already cast).
      2. Legacy pycaw — ``.Activate(IAudioEndpointVolume._iid_, ...)``.
      3. Fallback when pycaw is missing — convert the percentage delta into
         a proportional burst of VK_VOLUME_UP / VK_VOLUME_DOWN key taps
         (each tap ≈ 2 % on Windows). Less smooth than pycaw but means the
         gesture works without the extra dependency.
    """
    pct = int(max(0, min(100, pct)))
    level = pct / 100.0
    # ── 1. Modern pycaw ──
    try:
        from pycaw.pycaw import AudioUtilities  # type: ignore
        sp = AudioUtilities.GetSpeakers()
        vol = getattr(sp, "EndpointVolume", None)
        if vol is not None:
            vol.SetMasterVolumeLevelScalar(level, None)
            _VOLUME_FALLBACK_STATE["last_pct"] = pct
            return True
    except Exception:
        pass
    # ── 2. Legacy pycaw ──
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL  # type: ignore
        devices = AudioUtilities.GetSpeakers()
        iface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(iface, POINTER(IAudioEndpointVolume))
        vol.SetMasterVolumeLevelScalar(level, None)
        _VOLUME_FALLBACK_STATE["last_pct"] = pct
        return True
    except Exception as e:
        if not _VOLUME_FALLBACK_STATE["warned"]:
            log.warning(
                "[gestures] pycaw unavailable (%s) — using VK_VOLUME_UP/DOWN "
                "key-tap fallback. Install pycaw + comtypes for smooth "
                "absolute-volume control.", e
            )
            _VOLUME_FALLBACK_STATE["warned"] = True
    # ── 3. Key-tap fallback (delta-driven). Each Windows volume tap ≈ 2 %. ──
    last = _VOLUME_FALLBACK_STATE["last_pct"]
    if last is None:
        last = 50
    delta = pct - last
    n_taps = max(-10, min(10, int(round(delta / 2.0))))
    if n_taps > 0:
        for _ in range(n_taps):
            _tap(_VK_VOLUME_UP); time.sleep(0.01)
    elif n_taps < 0:
        for _ in range(-n_taps):
            _tap(_VK_VOLUME_DN); time.sleep(0.01)
    _VOLUME_FALLBACK_STATE["last_pct"] = pct
    return True


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
        # Discriminate sideways palm (rotated ~90° so the four MCP joints line
        # up vertically) from a front-facing palm. Used to gate the
        # sideways-palm app-switch gesture.
        mcp_i = lm[_MCPS["index"]]
        mcp_p = lm[_MCPS["pinky"]]
        dx_mcp = abs(mcp_i.x - mcp_p.x)
        dy_mcp = abs(mcp_i.y - mcp_p.y)
        if dy_mcp > dx_mcp * 1.3:
            return "sideways_palm"
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
    static_window: deque = field(default_factory=lambda: deque(maxlen=_STATIC_CONSENSUS_WINDOW))
    armed: bool = True
    neutral_frames: int = 0
    smoothed_hands: list = field(default_factory=list)
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
    # ── Lock-screen sequence (palm → fist → palm → fist) ──
    # 0=waiting for palm, 1=palm-held 0.3s, 2=palm→fist seen, 3=fist→palm seen.
    # Step advances to 4 (fires) on the second fist transition.
    lock_seq_step: int = 0
    lock_palm_started_at: float = 0.0
    lock_last_progress_at: float = 0.0
    # ── Double-pinch (play/pause) — rising edges of thumb-index touch ──
    last_pinch_state: bool = False
    pinch_events: deque = field(default_factory=lambda: deque(maxlen=4))
    # ── Continuous volume gesture (closed fingers + thumb↔index distance) ──
    volume_armed: bool = False
    volume_arm_started_at: float = 0.0
    volume_last_emit_at: float = 0.0
    volume_last_pct: int = -1
    # ── Sideways-palm app switch (rotated palm + horizontal motion) ──
    side_palm_stable_since: float = 0.0
    side_palm_anchor_x: float = 0.0
    side_palm_anchored: bool = False


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
    # ── Sequenced gestures — collision-free, intentional ──
    "palm_fist_lock":   _lock_screen,           # palm(0.3s) → fist → palm → fist
    "double_pinch":     _media_play_pause,      # 2 quick pinches in OK-sign region
    "app_switch_next":  _alt_tab_forward,       # sideways palm + motion left
    "app_switch_prev":  _alt_tab_backward,      # sideways palm + motion right

    # ── Open-palm motion gestures ──
    "swipe_left":      lambda: _smart_swipe("left"),
    "swipe_right":     lambda: _smart_swipe("right"),
    "swipe_up":        lambda: _scroll_page("up"),
    "swipe_down":      lambda: _scroll_page("down"),
    "wave":            _esc_dismiss,            # rapid L↔R wave → Esc

    # ── Quick volume taps (still useful, non-colliding) ──
    "thumbs_up":       lambda: _volume("up", 3),
    "thumbs_down":     lambda: _volume("down", 3),

    # ── One-shot static poses ──
    "peace":           _screenshot_snip,
    "three_up":        _media_next_track,
    "long_fist":       _open_palette_action,    # 3s fist → command palette

    # ── Two-handed gestures ──
    "two_palm_spread": _zoom_in,
    "two_palm_pinch":  _zoom_out,
    "clap":            _clap_wake_action,

    # ── Air strokes (index-finger draw) ──
    "stroke_circle":      _refresh_page,
    "stroke_x":           _close_tab,
    "stroke_check":       _enter_confirm,
    "stroke_arrow_right": _arrow_right,
}

# Sensitivity multiplier maps a small set of named levels to a single
# scaling factor that the swipe gate (and similar motion thresholds)
# multiply against their base values. Higher = harder to fire.
_SENSITIVITY_LEVELS: dict[str, float] = {
    "very_sensitive": 0.7,    # easier to fire — for users with limited motion
    "sensitive":      0.85,
    "normal":         1.0,    # default
    "relaxed":        1.2,    # harder to fire — fewer false positives
    "very_relaxed":   1.5,
}


def _sensitivity_multiplier() -> float:
    """Read the user-chosen sensitivity level from settings. Falls back to
    1.0 (default) on any error so a missing settings file never breaks
    the engine."""
    try:
        from core import settings as _settings
        level = str(_settings.get("gesture_sensitivity") or "normal").lower()
    except Exception:
        return 1.0
    return _SENSITIVITY_LEVELS.get(level, 1.0)


_GESTURE_COOLDOWN_S = 1.4
_FIST_HOLD_S = 1.0           # short fist (1.0s)  = lock screen
_LONG_FIST_S = 3.0           # long  fist (3.0s) = palette toggle (deliberate)
_PALM_HOLD_S = 0.9           # palm steady for ~0.9s = play/pause toggle
_HOLD_S = 0.55               # static-pose gestures (peace, ok_sign, pinch,
                             #   three_up) need this much steady time before
                             #   firing — avoids misfires during natural hand
                             #   transitions through these poses.

# Human-intent gates. A raw pose can flicker while the user is forming it,
# so we only act on a gesture after it dominates a short rolling window.
_STATIC_CONSENSUS_WINDOW = 5
_STATIC_CONSENSUS_REQUIRED = 4
_REARM_NEUTRAL_FRAMES = 10
_LANDMARK_SMOOTH_ALPHA = 0.55

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

# ── Lock-screen sequence (palm → fist → palm → fist) ──
_LOCK_INITIAL_PALM_HOLD_S = 0.30   # initial palm must be held this long to "arm"
_LOCK_SEQ_TIMEOUT_S = 4.0          # whole sequence must finish within this
                                   # (bumped 3 → 4s — gives breathing room
                                   # to perform the 4-step sequence without
                                   # rushing; user feedback was "awkward").

# ── Double-pinch play/pause ──
_DOUBLE_PINCH_MIN_INTERVAL_S = 0.08
_DOUBLE_PINCH_MAX_INTERVAL_S = 0.80
_DOUBLE_PINCH_WINDOW_S = 1.2

# ── Continuous volume gesture ──
_VOLUME_ARM_HOLD_S = 0.20          # how long the fist+pinch must be held to arm
_VOLUME_EMIT_INTERVAL_S = 0.08     # throttle updates to ~12 Hz
_VOLUME_MIN_PCT_DELTA = 3          # don't repeat if % barely changed
_VOLUME_FULL_NORM = 2.5            # thumb↔index distance / palm width at 100%

# ── Sideways-palm app switch ──
_SIDE_PALM_HOLD_S = 0.30         # bumped 0.20 → 0.30 — gives a clearer
                                 # "commit" beat before motion is read
_SIDE_PALM_SWIPE_THRESH = 0.12   # bumped 0.10 → 0.12 — needs a more
                                 # deliberate sideways motion to switch app


class GestureEngine:
    def __init__(self, actions: Optional[dict] = None):
        self._actions = dict(DEFAULT_ACTIONS)
        if actions:
            self._actions.update(actions)
        self._state = _GestureState()
        self._mp_hands = None
        self._lock = threading.RLock()
        self._enabled = False
        # Idle camera release (see camera_idle_seconds / _maybe_idle_release).
        self._last_hand_at = 0.0
        self._idle_release_pending = False
        self._listeners: list[Callable[[str], None]] = []
        self._mediapipe_ok = self._init_mediapipe()
        # Cursor-mode toggle (independent of `_enabled` — gesture
        # recognition stays on; the per-frame loop also drives the
        # mouse when this is True).
        self._cursor_mode = False
        self._screen_w, self._screen_h = _screen_size()
        # Cached most-recent frame so the face gate can re-identify the
        # user on demand without re-subscribing to the VisionEngine.
        self._latest_frame = None

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
            self._state = _GestureState()
            self._enabled = True
            self._last_hand_at = time.monotonic()
            self._idle_release_pending = False
            return True

    # ── idle camera release (opt-in) ──────────────────────────────
    #
    # VisionEngine already holds the webcam open only while something is
    # subscribed, and releases it when the last consumer leaves — that part
    # was always right. The gap was here: GestureEngine never unsubscribed on
    # its own, so enabling gestures once kept the camera (and MediaPipe
    # inference at ~30 fps) running until the app closed, whether or not a
    # hand had been in front of it for hours.
    #
    # OFF BY DEFAULT, deliberately. Auto-releasing means gestures silently
    # stop working until re-enabled, which is a product decision rather than
    # a technical one — `AERIS_CAMERA_IDLE_S=<seconds>` opts in.

    def _note_hand_seen(self) -> None:
        self._last_hand_at = time.monotonic()

    def _maybe_idle_release(self) -> None:
        window = camera_idle_seconds()
        if window <= 0 or self._idle_release_pending or not self._enabled:
            return
        if time.monotonic() - getattr(self, "_last_hand_at", 0.0) < window:
            return
        self._idle_release_pending = True
        log.info("[gestures] no hand for %.0fs — releasing the camera", window)

        # MUST hand off: this runs on the VisionEngine capture thread, and
        # stop() -> unsubscribe() -> VisionEngine.stop() joins that very
        # thread. Joining yourself raises; a one-shot worker avoids it.
        def _release():
            try:
                self.stop()
            except Exception as e:
                log.warning("[gestures] idle release failed: %s", e)
            finally:
                self._idle_release_pending = False

        threading.Thread(target=_release, name="gesture-idle-release",
                         daemon=True).start()

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

    def _clear_tracks(self) -> None:
        st = self._state
        st.palm_track.clear()
        st.wave_track.clear()
        st.two_hand_track.clear()
        st.stroke_track = []
        st.palm_hold_since = 0.0
        st.static_window.clear()
        st.smoothed_hands = []
        # New gesture state — hand left frame, reset every in-progress chain.
        st.lock_seq_step = 0
        st.lock_palm_started_at = 0.0
        st.last_pinch_state = False
        st.pinch_events.clear()
        st.volume_armed = False
        st.volume_arm_started_at = 0.0
        st.volume_last_pct = -1
        st.side_palm_stable_since = 0.0
        st.side_palm_anchored = False

    def _mark_neutral_frame(self) -> None:
        # Reached only on frames with no hand in them — the natural place to
        # notice the camera has nothing to watch (see _maybe_idle_release).
        self._maybe_idle_release()
        st = self._state
        if st.armed:
            st.neutral_frames = 0
            return
        st.neutral_frames += 1
        if st.neutral_frames >= _REARM_NEUTRAL_FRAMES:
            st.armed = True
            st.neutral_frames = 0
            st.last_static = "none"
            st.last_static_at = 0.0

    def _stable_static(self, raw_static: str) -> str:
        """Return a pose only after K-frame consensus.

        This is the human-friendly part: while the user's hand is moving
        toward a final pose, intermediate shapes show up for a frame or two.
        Those are treated as "none" until one pose wins the rolling window.
        """
        st = self._state
        st.static_window.append(raw_static)
        if len(st.static_window) < _STATIC_CONSENSUS_WINDOW:
            return "none"
        for name in set(st.static_window):
            if name == "none":
                continue
            if sum(1 for x in st.static_window if x == name) >= _STATIC_CONSENSUS_REQUIRED:
                return name
        return "none"

    def _smooth_hands(self, hands: list[tuple]) -> list[tuple]:
        """EMA-smooth landmark coordinates to reduce visible pose jitter."""
        st = self._state
        if len(st.smoothed_hands) != len(hands):
            st.smoothed_hands = []
            for lms, _label in hands:
                st.smoothed_hands.append([
                    _LandmarkPoint(float(p.x), float(p.y), float(getattr(p, "z", 0.0)))
                    for p in lms
                ])
            return [(st.smoothed_hands[i], hands[i][1]) for i in range(len(hands))]

        alpha = _LANDMARK_SMOOTH_ALPHA
        for hand_idx, (lms, _label) in enumerate(hands):
            smoothed = st.smoothed_hands[hand_idx]
            for i, p in enumerate(lms):
                smoothed[i].x += alpha * (float(p.x) - smoothed[i].x)
                smoothed[i].y += alpha * (float(p.y) - smoothed[i].y)
                smoothed[i].z += alpha * (float(getattr(p, "z", 0.0)) - smoothed[i].z)
        return [(st.smoothed_hands[i], hands[i][1]) for i in range(len(hands))]

    def _on_frame(self, frame_bgr) -> None:
        # Cache the most recent BGR frame so the face-gate (which runs
        # on-demand from _emit / _fire_continuous) can refresh its
        # "who's in front of the camera" answer without re-subscribing
        # to the VisionEngine.
        self._latest_frame = frame_bgr
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
                self._clear_tracks()
                self._mark_neutral_frame()
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
                self._clear_tracks()
                self._mark_neutral_frame()
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
        self._note_hand_seen()          # a hand is in frame — reset idle clock
        st = self._state
        hands = self._smooth_hands(hands)

        # ── Two-handed gestures (zoom + clap) ──
        if len(hands) >= 2:
            self._handle_two_hands(hands, now)
        else:
            st.two_hand_track.clear()

        # ── Single-hand gestures use the FIRST hand only ──
        lms = hands[0][0]
        hand_label = hands[0][1]
        raw_static = _classify_static(lms, hand_label)
        static = self._stable_static(raw_static)

        # ── Custom user-trained gestures ──
        # Runs even before the armed gate so recording can happen while
        # the engine cycles. A successful fire goes through the regular
        # _emit path so face-gate / cooldown still apply.
        try:
            from core.custom_gestures import get_custom_gesture_engine
            cg_result = get_custom_gesture_engine().feed(lms)
            if cg_result and not cg_result.startswith(("recorded:", "saved:")):
                # Match fired — surface as a "custom:<name>" gesture so
                # bindings can target it (e.g. bind custom:my-pose to X).
                self._emit(f"custom:{cg_result}")
        except Exception as _cg_err:
            log.debug("[gestures] custom gesture feed failed: %s", _cg_err)

        # ── Continuous gestures (bypass the arm/neutral-rest gate) ──
        # Volume control and sideways-palm app switching are designed to
        # repeat while the user holds the pose, so they don't go through
        # the disarm/rearm cycle.
        self._handle_volume_continuous(lms, hand_label, now)
        self._handle_sideways_palm_switch(lms, static, now)

        if not st.armed:
            if static == "none":
                self._mark_neutral_frame()
            else:
                st.neutral_frames = 0
            st.last_static = static
            return

        if static == "none":
            self._mark_neutral_frame()
        else:
            st.neutral_frames = 0

        # ── Sequenced gestures (respect the arm/neutral-rest gate) ──
        # Lock-screen sequence accumulates pose transitions; double-pinch
        # counts rapid thumb-index touch onsets in OK-sign region.
        self._update_lock_sequence(static, now)
        self._detect_double_pinch(lms, hand_label, now)

        # ── Cursor mode (advanced) — drives mouse from index finger ──
        if self._cursor_mode:
            self._handle_cursor(lms)

        # ----- swipe (open_palm motion: horizontal OR vertical) + wave -----
        # Note: lock screen and play/pause are NO LONGER bound here — they
        # require the dedicated sequenced gestures (palm_fist_lock and
        # double_pinch respectively).
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
        else:
            st.palm_track.clear()
            st.palm_hold_since = 0.0
            st.wave_track.clear()

        # ----- fist hold: 3.0s = long_fist (palette toggle) -----
        # Plain 1-second fist no longer fires lock — that's now the
        # palm→fist→palm→fist sequence (see _update_lock_sequence).
        if static == "fist":
            if st.last_static != "fist":
                st.last_static_at = now
            held = now - st.last_static_at
            if held >= _LONG_FIST_S:
                self._emit("long_fist")
                st.last_static_at = now + 1e6   # parked until release

        # ----- thumbs up / down — deliberate hold -----
        elif static in ("thumbs_up", "thumbs_down"):
            if st.last_static == static:
                if now - st.last_static_at >= _HOLD_S:
                    self._emit(static)
                    st.last_static_at = now + _GESTURE_COOLDOWN_S
            else:
                st.last_static_at = now

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

        # ----- hold-required static poses (peace, three_up) -----
        # Fire only after the pose has been STEADY for _HOLD_S. This kills
        # spurious matches during natural hand motion through these
        # configurations.
        #
        # `pinch` and `ok_sign` are deliberately NOT in this list — they
        # are intermediate states of the double-pinch (play/pause) and
        # continuous-volume gestures and should not fire on their own.
        elif static in ("peace", "three_up"):
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

    # ── Sequenced gesture: lock-screen (palm → fist → palm → fist) ─

    def _update_lock_sequence(self, static: str, now: float) -> None:
        """Progress the four-step palm/fist sequence that fires the
        ``palm_fist_lock`` event.

        Steps:
          0 → waiting for the initial open palm
          1 → palm held ≥ _LOCK_INITIAL_PALM_HOLD_S
          2 → first fist seen
          3 → palm again
          (next fist) → emit lock and reset

        Any unrelated stable pose resets the machine. ``none`` is
        ignored so the inevitable in-between frames don't break the
        chain. The whole sequence must complete within
        _LOCK_SEQ_TIMEOUT_S of the previous step.
        """
        st = self._state

        # Step-timeout (skip when nothing has progressed yet).
        if st.lock_seq_step > 0 and st.lock_last_progress_at > 0.0:
            if now - st.lock_last_progress_at > _LOCK_SEQ_TIMEOUT_S:
                st.lock_seq_step = 0
                st.lock_palm_started_at = 0.0

        if static == "none":
            return

        if st.lock_seq_step == 0:
            if static == "open_palm":
                if st.lock_palm_started_at == 0.0:
                    st.lock_palm_started_at = now
                elif now - st.lock_palm_started_at >= _LOCK_INITIAL_PALM_HOLD_S:
                    st.lock_seq_step = 1
                    st.lock_last_progress_at = now
            else:
                st.lock_palm_started_at = 0.0
        elif st.lock_seq_step == 1:
            if static == "fist":
                st.lock_seq_step = 2
                st.lock_last_progress_at = now
            elif static != "open_palm":
                st.lock_seq_step = 0
                st.lock_palm_started_at = 0.0
        elif st.lock_seq_step == 2:
            if static == "open_palm":
                st.lock_seq_step = 3
                st.lock_last_progress_at = now
            elif static != "fist":
                st.lock_seq_step = 0
                st.lock_palm_started_at = 0.0
        elif st.lock_seq_step == 3:
            if static == "fist":
                self._emit("palm_fist_lock")
                st.lock_seq_step = 0
                st.lock_palm_started_at = 0.0
            elif static != "open_palm":
                st.lock_seq_step = 0
                st.lock_palm_started_at = 0.0

    # ── Sequenced gesture: double-pinch (play/pause) ──────────────

    def _detect_double_pinch(self, lms, hand_label: str, now: float) -> None:
        """Count thumb-index touch onsets while the hand is in OK-sign
        region (≥2 of middle/ring/pinky extended). Two onsets spaced
        between _DOUBLE_PINCH_MIN_INTERVAL_S and _DOUBLE_PINCH_MAX_INTERVAL_S
        emit ``double_pinch``.
        """
        st = self._state

        states = {f: _finger_extended(lms, f, hand_label) for f in _TIPS}
        n_other = sum(1 for f in ("middle", "ring", "pinky") if states[f])
        if n_other < 2:
            st.last_pinch_state = False
            st.pinch_events.clear()
            return

        d = _dist(lms[_TIPS["thumb"]], lms[_TIPS["index"]])
        pinched_now = d < _PINCH_TOUCH_DIST

        # Rising edge: thumb-index just touched.
        if pinched_now and not st.last_pinch_state:
            cutoff = now - _DOUBLE_PINCH_WINDOW_S
            while st.pinch_events and st.pinch_events[0] < cutoff:
                st.pinch_events.popleft()
            st.pinch_events.append(now)
            if len(st.pinch_events) >= 2:
                interval = st.pinch_events[-1] - st.pinch_events[-2]
                if _DOUBLE_PINCH_MIN_INTERVAL_S <= interval <= _DOUBLE_PINCH_MAX_INTERVAL_S:
                    self._emit("double_pinch")
                    st.pinch_events.clear()

        st.last_pinch_state = pinched_now

    # ── Continuous gesture: volume control ─────────────────────────

    def _handle_volume_continuous(self, lms, hand_label: str, now: float) -> None:
        """Closed-fingers + thumb-index pinch held _VOLUME_ARM_HOLD_S =
        ARMED. Once armed, the thumb-index distance (normalised by palm
        width) is mapped continuously to absolute system volume.

        Stays armed as long as middle/ring/pinky remain curled, so the
        user can sweep volume smoothly. The gesture disarms instantly
        when those fingers extend — preventing accidental volume jumps
        when transitioning to a different pose.
        """
        st = self._state

        states = {f: _finger_extended(lms, f, hand_label) for f in _TIPS}
        others_curled = (
            (not states["middle"])
            and (not states["ring"])
            and (not states["pinky"])
        )

        if not others_curled:
            if st.volume_armed:
                log.debug("[gestures] volume disarmed (fingers extended)")
            st.volume_armed = False
            st.volume_arm_started_at = 0.0
            st.volume_last_pct = -1
            return

        d = _dist(lms[_TIPS["thumb"]], lms[_TIPS["index"]])
        pinched_now = d < _PINCH_TOUCH_DIST

        if not st.volume_armed:
            if pinched_now:
                if st.volume_arm_started_at == 0.0:
                    st.volume_arm_started_at = now
                elif now - st.volume_arm_started_at >= _VOLUME_ARM_HOLD_S:
                    st.volume_armed = True
                    st.volume_last_pct = -1
                    log.info("[gestures] volume armed")
            else:
                st.volume_arm_started_at = 0.0
            return

        # Armed — throttled emit.
        if (now - st.volume_last_emit_at) < _VOLUME_EMIT_INTERVAL_S:
            return

        # Normalise thumb-index distance by palm width for scale-invariance.
        mcp_i = lms[_MCPS["index"]]
        mcp_p = lms[_MCPS["pinky"]]
        palm_w = ((mcp_i.x - mcp_p.x) ** 2 + (mcp_i.y - mcp_p.y) ** 2) ** 0.5
        if palm_w < 0.01:
            return
        norm = d / palm_w
        pct = int(max(0, min(100, (norm / _VOLUME_FULL_NORM) * 100)))

        if st.volume_last_pct < 0 or abs(pct - st.volume_last_pct) >= _VOLUME_MIN_PCT_DELTA:
            st.volume_last_pct = pct
            st.volume_last_emit_at = now
            _set_volume_pct(pct)
            # Synthetic listener event so UIs can surface the new value.
            event = f"volume_set:{pct}"
            for fn in self._listeners:
                try:
                    fn(event)
                except Exception:
                    pass

    # ── Continuous gesture: sideways-palm app switch ───────────────

    def _handle_sideways_palm_switch(self, lms, static: str, now: float) -> None:
        """Sideways palm (rotated ~90° so MCP joints are vertical) held
        _SIDE_PALM_HOLD_S anchors the wrist position. Subsequent
        horizontal motion past _SIDE_PALM_SWIPE_THRESH cycles apps:

          * raw dx > 0 (user moves hand LEFT in their POV) → Alt+Tab
            (next / right-side app in the alt-tab list)
          * raw dx < 0 (user moves hand RIGHT in their POV) → Alt+Shift+Tab
            (previous / left-side app)

        After each fire the anchor moves to the current wrist position so
        the user can keep moving in the same direction to cycle further.
        """
        st = self._state
        if static != "sideways_palm":
            st.side_palm_stable_since = 0.0
            st.side_palm_anchored = False
            return

        if st.side_palm_stable_since == 0.0:
            st.side_palm_stable_since = now
            st.side_palm_anchored = False
            return

        if now - st.side_palm_stable_since < _SIDE_PALM_HOLD_S:
            return

        wrist_x = lms[_WRIST].x
        if not st.side_palm_anchored:
            st.side_palm_anchor_x = wrist_x
            st.side_palm_anchored = True
            return

        dx = wrist_x - st.side_palm_anchor_x
        if dx > _SIDE_PALM_SWIPE_THRESH:
            self._fire_continuous("app_switch_next")
            st.side_palm_anchor_x = wrist_x
        elif dx < -_SIDE_PALM_SWIPE_THRESH:
            self._fire_continuous("app_switch_prev")
            st.side_palm_anchor_x = wrist_x

    def _fire_continuous(self, name: str) -> None:
        """Fire an action with only a per-name cooldown — bypasses the
        arm/neutral-rest gate. Used by repeatable gestures (sideways-palm
        app switching) so the user can sweep through many apps without
        having to drop and re-raise their hand between each switch.
        """
        now = time.monotonic()
        last = self._state.last_emit_at.get(name, 0.0)
        if now - last < _GESTURE_COOLDOWN_S * 0.5:
            return
        if not self._face_gate_allows(name):
            self._record_block(name, "face_gate")
            return
        self._state.last_emit_at[name] = now
        action = self._resolve_action(name)
        if action:
            try:
                action()
            except Exception as e:
                log.warning("[gestures] action %s raised: %s", name, e)
        self._record_fire(name)
        for fn in self._listeners:
            try:
                fn(name)
            except Exception:
                pass

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

        # ── Revamped swipe gate: BOTH delta AND velocity must qualify ──
        # The static distance check alone fires too eagerly for casual
        # hand motion ("just resting on my chin while I think"). Demand
        # peak velocity > 0.7 frame-widths/sec so a slow drift across
        # the window doesn't count — only a snappy, deliberate flick.
        # The sensitivity multiplier scales BOTH thresholds — higher
        # multiplier = harder to trigger = more relaxed gestures.
        mult = _sensitivity_multiplier()
        DELTA_THRESH = 0.22 * mult       # base 0.22
        VELOCITY_THRESH = 0.7 * mult     # base 0.7 frame-widths/sec

        # Peak per-segment velocity along the chosen axis. Skip the
        # check entirely when fewer than 3 samples (window too short).
        def _peak_velocity(axis: int) -> float:
            peak = 0.0
            for i in range(1, len(recent)):
                t0, t1 = recent[i - 1][0], recent[i][0]
                dt = t1 - t0
                if dt <= 0:
                    continue
                d = abs(recent[i][axis] - recent[i - 1][axis]) / dt
                peak = max(peak, d)
            return peak

        if abs(dx) >= DELTA_THRESH and abs(dx) > abs(dy) and _peak_velocity(1) >= VELOCITY_THRESH:
            # Mirror because webcam horizontally inverts user POV; swipe
            # with the right hand from user POV (left in image) reads as
            # "swipe_right" from the user's perspective.
            self._emit("swipe_left" if dx > 0 else "swipe_right")
            self._state.palm_track.clear()
        elif abs(dy) >= DELTA_THRESH and abs(dy) > abs(dx) and _peak_velocity(2) >= VELOCITY_THRESH:
            # Y axis: smaller-y is HIGHER on screen, so dy < 0 = upward.
            self._emit("swipe_up" if dy < 0 else "swipe_down")
            self._state.palm_track.clear()

    def _emit(self, name: str) -> None:
        now = time.monotonic()
        if not self._state.armed:
            return
        last = self._state.last_emit_at.get(name, 0.0)
        if now - last < _GESTURE_COOLDOWN_S:
            return
        if not self._face_gate_allows(name):
            self._record_block(name, "face_gate")
            return
        self._state.last_emit_at[name] = now
        self._state.armed = False
        self._state.neutral_frames = 0
        self._state.static_window.clear()
        action = self._resolve_action(name)
        if action:
            try:
                action()
            except Exception as e:
                log.warning("[gestures] action %s raised: %s", name, e)
        self._record_fire(name)
        for fn in self._listeners:
            try:
                fn(name)
            except Exception:
                pass

    def _face_gate_allows(self, gesture: str = "") -> bool:
        """Consult core.face_gate. Two layers:
          1. ``is_master_present`` — is *any* master in frame?
          2. ``gesture_allowed_for`` — does that master have permission
             for *this* gesture (kid-mode allowlist)?

        Fails OPEN on any error so a broken face stack never locks the
        user out of their own assistant.
        """
        try:
            from core import face_gate
            if not face_gate.is_master_present(self._latest_frame):
                return False
            faces = face_gate.last_identified()
            if not faces:
                # Master gate said OK but we have no identified names yet
                # (grace window / no recent inference). Allow — there's
                # nothing to check against.
                return True
            return face_gate.gesture_allowed_for(faces, gesture)
        except Exception as e:
            log.debug("[gestures] face_gate raised: %s — allowing.", e)
            return True

    def _resolve_action(self, name: str):
        """Pick the action callable for a gesture. Resolution order:

          1. Per-app profile override — ``gesture_profiles_per_app[<app>][<gesture>]``
             lets the user bind "peace = format-document" in VS Code while
             keeping "peace = screenshot" everywhere else.
          2. Global binding override — ``gesture_binding.<name>`` (written
             by the gesture_bind skill).
          3. Built-in default action from DEFAULT_ACTIONS.
        """
        override_skill = self._per_app_override(name)
        if not override_skill:
            try:
                from core import settings as _settings
                override_skill = _settings.get(f"gesture_binding.{name}")
            except Exception:
                override_skill = None
        if override_skill:
            try:
                from core.skill_registry import get_skill
                sk = get_skill(str(override_skill))
                if sk is not None:
                    return lambda: sk.run({"raw_text": f"gesture:{name}"})
            except Exception as e:
                log.debug("[gestures] override skill %s lookup failed: %s",
                          override_skill, e)
        return self._actions.get(name)

    def _per_app_override(self, gesture: str) -> Optional[str]:
        """Look up ``gesture_profiles_per_app[<foreground_app>][gesture]``.
        Returns the skill name or None. Match keys against the foreground
        process exe name (case-insensitive substring), so 'code' / 'code.exe'
        both match Visual Studio Code.
        """
        try:
            from core import settings as _settings
            profiles = _settings.get("gesture_profiles_per_app") or {}
            if not isinstance(profiles, dict) or not profiles:
                return None
        except Exception:
            return None
        exe = _foreground_exe_name().lower()
        if not exe:
            return None
        stem = exe.rsplit(".", 1)[0]
        for key, mapping in profiles.items():
            if not isinstance(mapping, dict):
                continue
            kl = str(key).strip().lower()
            if kl == exe or kl == stem or kl in exe:
                val = mapping.get(gesture)
                if val:
                    return str(val)
        return None

    def _record_fire(self, name: str) -> None:
        try:
            from core import gesture_trace
            gesture_trace.log_fire(name)
        except Exception:
            pass

    def _record_block(self, name: str, reason: str) -> None:
        try:
            from core import gesture_trace
            gesture_trace.log_block(name, reason)
        except Exception:
            pass
        # Count the block for the diagnostics surface.
        try:
            from core import face_gate
            if reason == "face_gate":
                face_gate.record_block(name)
        except Exception:
            pass


# Singleton.
_DEFAULT_ENGINE: Optional[GestureEngine] = None


def get_gesture_engine() -> GestureEngine:
    """The process-wide gesture engine.

    With ``AERIS_SPLIT_VISION=1`` this returns a `RemoteGestureEngine` instead
    — the same seven-method surface every caller outside `core/` uses, backed
    by the camera + MediaPipe running in a child process (§6.30). Deciding it
    here rather than at each call site is what makes the cutover one line
    instead of edits across five files.

    Note `main_window` deliberately *peeks* at `_DEFAULT_ENGINE` rather than
    calling this (constructing the engine on the GUI thread freezes it), so the
    split object has to land in the same variable — which it does.
    """
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        try:
            from core.remote_gesture_engine import (
                RemoteGestureEngine, split_vision_enabled,
            )
            if split_vision_enabled():
                _DEFAULT_ENGINE = RemoteGestureEngine()
                log.info("[gestures] split mode — camera runs in a child process")
                return _DEFAULT_ENGINE
        except Exception as e:
            # A broken split must not cost the user gestures entirely.
            log.warning("[gestures] split mode unavailable (%s) — in-process", e)
        _DEFAULT_ENGINE = GestureEngine()
    return _DEFAULT_ENGINE
