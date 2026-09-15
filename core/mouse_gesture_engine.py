"""V-cursor mouse-gesture engine.

While ON, the engine drives the system cursor with the user's hand:

  - **V-pose** = index + middle EXTENDED and STUCK TOGETHER + thumb out
    + ring/pinky folded. Different from "peace" (which spreads the V).
    The midpoint of index-tip and middle-tip is mapped from the
    normalised camera frame into screen pixels — moving the hand moves
    the cursor.

  - **Thumb tap on folded fingers** (thumb tip approaches the ring/pinky
    cluster) fires a click — *left click if the LEFT hand did it, right
    click if the RIGHT hand did it.* (User explicitly asked for this
    asymmetry — easier than reaching for two different buttons.)

  - **Peace sign** (open V, not stuck-together V) → ARM / DISARM toggle.
    Same safety gate as Maps mode.

Movement is smoothed with an EMA so MediaPipe jitter doesn't shake the
cursor. Click is edge-triggered with a cooldown to avoid double-fires.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from core import hand_landmarks as HL

log = logging.getLogger(__name__)


_EMA_ALPHA = 0.45              # 0 = no smoothing, 1 = no movement
_CLICK_COOLDOWN_S = 0.5
_PEACE_COOLDOWN_S = 0.8
_FRAME_SKIP = 2


class MouseGestureEngine:
    _instance: "MouseGestureEngine | None" = None

    def __init__(self):
        self._lock = threading.RLock()
        self._running = False
        self._armed = True
        self._mp_hands = None
        self._frame_idx = 0
        # smoothed cursor target in normalised coords
        self._smooth_xy: Optional[tuple[float, float]] = None
        # click state per hand
        self._click_state = {"left": "open", "right": "open"}
        self._last_click_ts = {"left": 0.0, "right": 0.0}
        self._last_peace_ts = 0.0
        self._counts = {"move": 0, "left_click": 0, "right_click": 0,
                        "arm_toggle": 0, "frames": 0}

    # ─ singleton ────────────────────────────────────────────

    @classmethod
    def instance(cls) -> "MouseGestureEngine":
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
        log.info("[mouse_gesture] armed=%s", self._armed)

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
                    "mouse_gestures", self._on_frame)
                if not ok:
                    return False, "Camera unavailable."
            except Exception as e:
                return False, f"Camera subscription failed: {e}"
            self._running = True
            self._smooth_xy = None
            log.info("[mouse_gesture] started (armed=%s)", self._armed)
            return True, "Mouse gestures ON."

    def stop(self) -> tuple[bool, str]:
        with self._lock:
            if not self._running:
                return True, "Already stopped."
            try:
                from core.vision_engine import get_vision_engine
                get_vision_engine().unsubscribe("mouse_gestures")
            except Exception:
                pass
            self._running = False
            self._smooth_xy = None
            log.info("[mouse_gesture] stopped")
            return True, "Mouse gestures OFF."

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
            log.warning("[mouse_gesture] mediapipe init failed: %s", e)
            return False

    # ─ frame callback ───────────────────────────────────────

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
        self._dispatch(hands, time.time())

    def _extract_hands(self, mp_result) -> list[dict]:
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

    def _dispatch(self, hands: list[dict], now_s: float) -> None:
        # Peace = arm/disarm
        if any(HL.is_peace(h["lm"]) for h in hands):
            if now_s - self._last_peace_ts > _PEACE_COOLDOWN_S:
                self._armed = not self._armed
                self._counts["arm_toggle"] += 1
                self._last_peace_ts = now_s
                log.info("[mouse_gesture] peace → armed=%s", self._armed)
                return

        # Pick the active hand: prefer the one in V-cursor pose.
        movers = [h for h in hands
                  if HL.is_mouse_pose(h["lm"], h["handedness"])]
        if not movers:
            # No V-pose: drop smoothing so re-acquisition is fresh.
            self._smooth_xy = None
            return

        active = movers[0]
        nx, ny = HL.mouse_pose_pointer(active["lm"])
        self._move_cursor(nx, ny)
        # Click detection on the active hand only.
        self._maybe_click(active, now_s)

    # ─ Actions ──────────────────────────────────────────────

    def _pyautogui(self):
        try:
            import pyautogui  # noqa
            pyautogui.FAILSAFE = False
            return pyautogui
        except Exception:
            return None

    def _move_cursor(self, nx: float, ny: float) -> None:
        if self._smooth_xy is None:
            self._smooth_xy = (nx, ny)
        else:
            sx, sy = self._smooth_xy
            self._smooth_xy = (sx * (1 - _EMA_ALPHA) + nx * _EMA_ALPHA,
                               sy * (1 - _EMA_ALPHA) + ny * _EMA_ALPHA)
        self._counts["move"] += 1
        if not self._armed:
            return
        pg = self._pyautogui()
        if pg is None:
            return
        sw, sh = pg.size()
        # Mirror x so user's hand-right = cursor-right (selfie cam).
        ex = int((1.0 - self._smooth_xy[0]) * sw)
        ey = int(self._smooth_xy[1] * sh)
        try:
            pg.moveTo(ex, ey, duration=0.0)
        except Exception as e:
            log.info("[mouse_gesture] move failed: %s", e)

    def _maybe_click(self, hand: dict, now_s: float) -> None:
        side = "left" if hand["handedness"].startswith("l") else "right"
        touching = HL.thumb_touches_folded_fingers(hand["lm"])
        prev = self._click_state[side]
        if touching and prev == "open":
            self._click_state[side] = "closed"
            if now_s - self._last_click_ts[side] > _CLICK_COOLDOWN_S:
                self._last_click_ts[side] = now_s
                self._fire_click(side)
        elif not touching and prev == "closed":
            self._click_state[side] = "open"

    def _fire_click(self, side: str) -> None:
        button = "left" if side == "left" else "right"
        self._counts[f"{side}_click"] += 1
        log.info("[mouse_gesture] %s click (armed=%s)", side, self._armed)
        if not self._armed:
            return
        pg = self._pyautogui()
        if pg is None:
            return
        try:
            pg.click(button=button)
        except Exception as e:
            log.info("[mouse_gesture] click dispatch failed: %s", e)


def get_mouse_gesture_engine() -> MouseGestureEngine:
    return MouseGestureEngine.instance()
