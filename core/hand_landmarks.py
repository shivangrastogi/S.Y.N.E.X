"""Pure-math helpers for MediaPipe hand-landmark shapes.

Kept dependency-free (numpy only) so unit tests don't need MediaPipe / OpenCV /
a webcam. Every detector returns a plain bool or a small dict; no side effects.

A "landmarks" arg is the 21-row x 3-col array MediaPipe gives you for one
hand. Coordinates are normalised: x and y in [0,1], z relative to the wrist.
Index meaning (subset we care about):

    0 = wrist
    4 = thumb tip
    3 = thumb IP joint
    8 = index tip            6 = index PIP
    12 = middle tip          10 = middle PIP
    16 = ring tip            14 = ring PIP
    20 = pinky tip           18 = pinky PIP
    5 = index MCP (base)
    9 = middle MCP
    13 = ring MCP
    17 = pinky MCP
"""
from __future__ import annotations

import math
from typing import Sequence


def dist(p1: Sequence[float], p2: Sequence[float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def finger_extended(lm, tip: int, pip: int) -> bool:
    """Tip is higher in frame (smaller y) than its PIP → finger extended.
    For thumb use ``thumb_extended`` instead — thumb opens sideways, not up."""
    return lm[tip][1] < lm[pip][1] - 0.02


def thumb_extended(lm, handedness: str) -> bool:
    """Thumb tip far enough out from its IP joint horizontally."""
    if handedness.lower().startswith("r"):
        return lm[4][0] < lm[3][0] - 0.02
    return lm[4][0] > lm[3][0] + 0.02


def fingertip_cluster_center(lm) -> tuple[float, float]:
    """Mean of (ring tip, pinky tip). Useful as the "thumb tap target"
    when the user folds those fingers down to form a fist or V."""
    return ((lm[16][0] + lm[20][0]) / 2, (lm[16][1] + lm[20][1]) / 2)


def palm_center(lm) -> tuple[float, float]:
    """Mean of MCP joints + wrist = a stable palm centroid."""
    xs = [lm[0][0], lm[5][0], lm[9][0], lm[13][0], lm[17][0]]
    ys = [lm[0][1], lm[5][1], lm[9][1], lm[13][1], lm[17][1]]
    return (sum(xs) / 5, sum(ys) / 5)


# ── Gesture predicates ──────────────────────────────────────────


def is_ok_sign(lm, handedness: str = "right") -> bool:
    """Thumb and index tips touching (small ring), other 3 fingers extended."""
    pinch = dist(lm[4], lm[8])
    if pinch > 0.06:
        return False
    return (finger_extended(lm, 12, 10)
            and finger_extended(lm, 16, 14)
            and finger_extended(lm, 20, 18))


def is_open_palm(lm) -> bool:
    """All five fingers extended (thumb judged generously)."""
    if not (finger_extended(lm, 8, 6)
            and finger_extended(lm, 12, 10)
            and finger_extended(lm, 16, 14)
            and finger_extended(lm, 20, 18)):
        return False
    # Thumb: tip x clearly outside the index MCP (works for either hand).
    if abs(lm[4][0] - lm[5][0]) <= 0.06:
        return False
    # Reject OK sign — thumb and index tips would be touching.
    return dist(lm[4], lm[8]) > 0.08


def is_peace(lm) -> bool:
    """Index + middle extended, ring + pinky folded. Used for ARM/DISARM."""
    return (finger_extended(lm, 8, 6)
            and finger_extended(lm, 12, 10)
            and not finger_extended(lm, 16, 14)
            and not finger_extended(lm, 20, 18)
            and dist(lm[8], lm[12]) > 0.05)


def is_mouse_pose(lm, handedness: str) -> bool:
    """V-cursor pose — index + middle EXTENDED and STUCK TOGETHER, ring +
    pinky folded. Different from peace (peace has the V spread). Thumb may
    be extended OR tucked toward the folded fingers (during a click)."""
    if not (finger_extended(lm, 8, 6)
            and finger_extended(lm, 12, 10)
            and not finger_extended(lm, 16, 14)
            and not finger_extended(lm, 20, 18)):
        return False
    # Stuck together: tip-to-tip distance small.
    return dist(lm[8], lm[12]) < 0.04


def mouse_pose_pointer(lm) -> tuple[float, float]:
    """Midpoint between index and middle tips → screen-mapped cursor target."""
    return ((lm[8][0] + lm[12][0]) / 2, (lm[8][1] + lm[12][1]) / 2)


def thumb_touches_folded_fingers(lm) -> bool:
    """Thumb tip near the ring/pinky tip cluster — the click trigger in
    mouse mode."""
    return dist(lm[4], fingertip_cluster_center(lm)) < 0.05


# ── Double-tap detector ─────────────────────────────────────────


class DoubleTapDetector:
    """Edge-triggered detector for *two* fast thumb-index pinch events.

    Fires when the user pinches twice with the gap between releases under
    ``window_ms`` and the pinch held briefly (< ``hold_ms``)."""

    CLOSE = 0.05      # pinch closed when dist < this
    OPEN = 0.09       # released when dist > this (hysteresis)

    def __init__(self, window_ms: int = 350, hold_ms: int = 200):
        self.window_ms = window_ms
        self.hold_ms = hold_ms
        self._closes: list[float] = []
        self._state = "open"
        self._close_started: float | None = None

    def observe(self, lm, now_ms: float) -> bool:
        d = dist(lm[4], lm[8])
        if self._state == "open" and d < self.CLOSE:
            self._state = "closed"
            self._close_started = now_ms
        elif self._state == "closed" and d > self.OPEN:
            if (self._close_started is not None
                    and now_ms - self._close_started < self.hold_ms):
                self._closes.append(now_ms)
            self._state = "open"
            self._close_started = None
        # Trim window
        self._closes = [t for t in self._closes
                        if now_ms - t <= self.window_ms]
        if len(self._closes) >= 2:
            self._closes.clear()
            return True
        return False
