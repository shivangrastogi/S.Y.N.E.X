"""Maps-mode gesture engine.

While ON, the engine subscribes to the shared vision feed, runs MediaPipe
``Hands`` on each frame, and emits high-level map actions:

  - **Two-hand OK pinch** → zoom. Track inter-hand centroid distance;
    moving APART → zoom IN, moving TOGETHER → zoom OUT. Magnitude scaled
    by delta.
  - **Open palm** (one hand) → pan. Drag the map with the palm centroid as
    the "virtual cursor" (mouse down on entry, mouse up on exit).
  - **Double thumb-index tap** (OK shape but two fast pinches under 350 ms)
    → click to select location.
  - **Peace sign** → ARM / DISARM gate. When DISARMED, gestures are still
    detected and logged but the keyboard/mouse actions don't fire — useful
    for practice or to freeze when a passer-by triggers something.

Actions execute via ``pyautogui``. We avoid importing pyautogui at module
import time so unit tests / headless CI don't fail on the X-display probe.

Public API:
    start() / stop()           — subscribe / unsubscribe to vision feed
    is_running() -> bool
    is_armed() -> bool         — peace toggle state
    set_armed(on: bool)
    stats() -> dict            — recent action counts (for telemetry)
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from core import hand_landmarks as HL

log = logging.getLogger(__name__)


# Cooldowns / smoothing
_PEACE_COOLDOWN_S = 0.8       # min seconds between arm/disarm toggles
_ZOOM_MIN_DELTA = 0.012       # ignore inter-hand jitter under this
_PAN_MIN_DELTA = 0.008        # ignore palm jitter
_SELECT_COOLDOWN_S = 0.6
_FRAME_SKIP = 2               # process every Nth frame (perf)


class MapsGestureEngine:
    _instance: "MapsGestureEngine | None" = None

    def __init__(self):
        self._lock = threading.RLock()
        self._running = False
        self._armed = True
        self._mp_hands = None
        self._frame_idx = 0
        # state for zoom
        self._last_two_hand_dist: Optional[float] = None
        # state for pan
        self._panning = False
        self._last_palm_xy: Optional[tuple[float, float]] = None
        # state for double-tap
        self._dt_left = HL.DoubleTapDetector()
        self._dt_right = HL.DoubleTapDetector()
        self._last_peace_ts = 0.0
        self._last_select_ts = 0.0
        self._counts = {"zoom_in": 0, "zoom_out": 0, "pan": 0,
                        "select": 0, "arm_toggle": 0, "frames": 0}

    # ─ singleton ────────────────────────────────────────────

    @classmethod
    def instance(cls) -> "MapsGestureEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ─ public ───────────────────────────────────────────────

    def is_running(self) -> bool:
        return self._running

    def is_armed(self) -> bool:
        return self._armed

    def set_armed(self, on: bool) -> None:
        self._armed = bool(on)
        log.info("[maps_gesture] armed=%s", self._armed)

    def stats(self) -> dict:
        with self._lock:
            return {"running": self._running, "armed": self._armed,
                    **self._counts}

    def start(self) -> tuple[bool, str]:
        with self._lock:
            if self._running:
                return True, "Already running."
            if not self._init_mediapipe():
                return False, "MediaPipe not available."
            try:
                from core.vision_engine import get_vision_engine
                ok = get_vision_engine().subscribe(
                    "maps_gestures", self._on_frame)
                if not ok:
                    return False, "Camera unavailable."
            except Exception as e:
                return False, f"Camera subscription failed: {e}"
            self._running = True
            self._reset_dynamic_state()
            log.info("[maps_gesture] started (armed=%s)", self._armed)
            return True, "Maps gestures ON."

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            if not self._running:
                return True, "Already stopped."
            try:
                from core.vision_engine import get_vision_engine
                get_vision_engine().unsubscribe("maps_gestures")
            except Exception:
                pass
            self._running = False
            self._release_pan()
            log.info("[maps_gesture] stopped")
            return True, "Maps gestures OFF."

    # ─ MediaPipe init ───────────────────────────────────────

    def _init_mediapipe(self) -> bool:
        if self._mp_hands is not None:
            return True
        try:
            import mediapipe as mp
            self._mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.5,
            )
            return True
        except Exception as e:
            log.warning("[maps_gesture] mediapipe init failed: %s", e)
            return False

    # ─ per-frame callback ───────────────────────────────────

    def _on_frame(self, frame_bgr) -> None:
        self._counts["frames"] += 1
        self._frame_idx += 1
        if self._frame_idx % _FRAME_SKIP != 0:
            return
        try:
            import cv2
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        except Exception:
            return
        res = self._mp_hands.process(rgb)
        hands = self._extract_hands(res)
        now_ms = time.time() * 1000.0
        self._dispatch(hands, now_ms)

    def _extract_hands(self, mp_result) -> list[dict]:
        """Returns list of {handedness: 'left'|'right', lm: [(x,y,z), ...]}."""
        out: list[dict] = []
        if not getattr(mp_result, "multi_hand_landmarks", None):
            return out
        labels = []
        if getattr(mp_result, "multi_handedness", None):
            for h in mp_result.multi_handedness:
                try:
                    labels.append(h.classification[0].label.lower())
                except Exception:
                    labels.append("right")
        for i, hand_lms in enumerate(mp_result.multi_hand_landmarks):
            lm = [(p.x, p.y, p.z) for p in hand_lms.landmark]
            out.append({
                "handedness": labels[i] if i < len(labels) else "right",
                "lm": lm,
            })
        return out

    # ─ dispatch ─────────────────────────────────────────────

    def _dispatch(self, hands: list[dict], now_ms: float) -> None:
        # 1) Peace = arm/disarm (edge-triggered with cooldown)
        if any(HL.is_peace(h["lm"]) for h in hands):
            now_s = now_ms / 1000.0
            if now_s - self._last_peace_ts > _PEACE_COOLDOWN_S:
                self._armed = not self._armed
                self._counts["arm_toggle"] += 1
                self._last_peace_ts = now_s
                log.info("[maps_gesture] peace → armed=%s", self._armed)
                # Don't process other gestures on the same frame as the toggle.
                return

        # 2) Two-hand OK zoom
        oks = [h for h in hands if HL.is_ok_sign(h["lm"], h["handedness"])]
        if len(oks) >= 2:
            self._release_pan()
            cur = HL.dist(HL.palm_center(oks[0]["lm"]),
                          HL.palm_center(oks[1]["lm"]))
            if self._last_two_hand_dist is not None:
                delta = cur - self._last_two_hand_dist
                if abs(delta) >= _ZOOM_MIN_DELTA:
                    self._emit_zoom(delta)
            self._last_two_hand_dist = cur
            return
        else:
            self._last_two_hand_dist = None

        # 3) Open palm pan (use first detected palm)
        palms = [h for h in hands if HL.is_open_palm(h["lm"])]
        if palms:
            cx, cy = HL.palm_center(palms[0]["lm"])
            self._emit_pan(cx, cy)
            return
        else:
            self._release_pan()

        # 4) Double-tap select (per-hand detector)
        for h in hands:
            det = self._dt_left if h["handedness"].startswith("l") else self._dt_right
            if det.observe(h["lm"], now_ms):
                now_s = now_ms / 1000.0
                if now_s - self._last_select_ts > _SELECT_COOLDOWN_S:
                    self._last_select_ts = now_s
                    self._emit_select()

    # ─ Actions ──────────────────────────────────────────────

    def _pyautogui(self):
        try:
            import pyautogui  # noqa
            pyautogui.FAILSAFE = False
            return pyautogui
        except Exception as e:
            log.debug("[maps_gesture] pyautogui unavailable: %s", e)
            return None

    def _emit_zoom(self, delta: float) -> None:
        # Apart = zoom IN; together = zoom OUT.
        zoom_in = delta > 0
        self._counts["zoom_in" if zoom_in else "zoom_out"] += 1
        log.info("[maps_gesture] zoom %s delta=%.3f (armed=%s)",
                 "in" if zoom_in else "out", delta, self._armed)
        if not self._armed:
            return
        pg = self._pyautogui()
        if pg is None:
            return
        # Magnitude → number of scroll clicks. Cap aggressive moves.
        clicks = max(1, min(6, int(abs(delta) / _ZOOM_MIN_DELTA)))
        try:
            # Ctrl+wheel = Google Maps zoom on most browsers.
            pg.keyDown("ctrl")
            pg.scroll(clicks if zoom_in else -clicks)
            pg.keyUp("ctrl")
        except Exception as e:
            log.info("[maps_gesture] zoom dispatch failed: %s", e)

    def _emit_pan(self, x: float, y: float) -> None:
        self._counts["pan"] += 1
        if not self._armed:
            self._last_palm_xy = (x, y)
            self._panning = True
            return
        pg = self._pyautogui()
        if pg is None:
            return
        sw, sh = pg.size()
        # Mirror horizontally: webcam is selfie-view, but our caller
        # may already be flipping. Empirically MediaPipe gives un-flipped
        # frames; let the user-facing left/right match.
        sx = int((1.0 - x) * sw)
        sy = int(y * sh)
        try:
            if not self._panning:
                pg.moveTo(sx, sy)
                pg.mouseDown(button="left")
                self._panning = True
                self._last_palm_xy = (x, y)
                return
            assert self._last_palm_xy is not None
            dx = x - self._last_palm_xy[0]
            dy = y - self._last_palm_xy[1]
            if abs(dx) < _PAN_MIN_DELTA and abs(dy) < _PAN_MIN_DELTA:
                return
            pg.moveTo(sx, sy, duration=0.0)
            self._last_palm_xy = (x, y)
        except Exception as e:
            log.info("[maps_gesture] pan dispatch failed: %s", e)

    def _release_pan(self) -> None:
        if not self._panning:
            return
        self._panning = False
        self._last_palm_xy = None
        if not self._armed:
            return
        pg = self._pyautogui()
        if pg is None:
            return
        try:
            pg.mouseUp(button="left")
        except Exception:
            pass

    def _emit_select(self) -> None:
        self._counts["select"] += 1
        log.info("[maps_gesture] select (armed=%s)", self._armed)
        if not self._armed:
            return
        pg = self._pyautogui()
        if pg is None:
            return
        try:
            pg.click()
        except Exception as e:
            log.info("[maps_gesture] select dispatch failed: %s", e)

    # ─ housekeeping ─────────────────────────────────────────

    def _reset_dynamic_state(self) -> None:
        self._last_two_hand_dist = None
        self._last_palm_xy = None
        self._panning = False
        self._dt_left = HL.DoubleTapDetector()
        self._dt_right = HL.DoubleTapDetector()


def get_maps_gesture_engine() -> MapsGestureEngine:
    return MapsGestureEngine.instance()
