"""Design tokens for JARVIS v3.1 — colors, state specs, font helpers.

Mirrors jv3-tokens.jsx exactly. Key differences vs the older aeris_v4 set:
  - PROCESSING uses MAGENTA (not cyan)
  - No ERROR state (only IDLE / LISTENING / PROCESSING / SPEAKING)
  - Added MAGENTA color for the BAT corner card and the THINKING pill
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt5.QtGui import QColor, QFont


# ─── Colors ──────────────────────────────────────────────────────────── #

class J:
    BG       = QColor(10, 15, 28)        # window bg              (#0A0F1C)
    BG_ELE   = QColor(15, 23, 42)        # elevated surfaces      (#0F172A)
    PANEL    = QColor(13, 21, 37)        # dock / chat / cards
    BORDER   = QColor(30, 41, 59)
    CYAN     = QColor(0, 212, 255)
    MAGENTA  = QColor(255, 45, 149)      # NEW vs aeris — used for PROCESSING + BAT
    PURPLE   = QColor(168, 85, 247)
    GREEN    = QColor(16, 185, 129)
    AMBER    = QColor(251, 191, 36)
    RED      = QColor(248, 113, 113)
    TEXT_PRI = QColor(234, 234, 234)
    TEXT_SEC = QColor(148, 163, 184)
    TEXT_MUT = QColor(100, 116, 139)
    WHITE    = QColor(255, 255, 255)
    BLACK    = QColor(0, 0, 0)


def rgba(color: QColor, alpha: float) -> QColor:
    """Return a copy of `color` with alpha clamped to [0,1]."""
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


# ─── AI states ───────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class StateSpec:
    label: str
    color: QColor
    ring_r1_ms: int
    ring_r2_ms: int
    ring_r3_ms: int
    pulse_ms: int
    glow_op: float


JSTATES: dict[str, StateSpec] = {
    "IDLE":       StateSpec("IDLE",       J.CYAN,    13000, 9000, 6000, 4000, 0.32),
    "LISTENING":  StateSpec("LISTENING",  J.GREEN,    8000, 5000, 3500, 1400, 0.70),
    "PROCESSING": StateSpec("PROCESSING", J.MAGENTA,  2000, 1400,  900,  700, 0.60),
    "SPEAKING":   StateSpec("SPEAKING",   J.PURPLE,   5000, 3500, 2200, 1800, 0.50),
}


# ─── Fonts ───────────────────────────────────────────────────────────── #

def inter(size: int, weight: int = 500) -> QFont:
    """Inter (UI) with Segoe UI fallback. weight: 400=Reg / 500=Med / 700=Bold."""
    f = QFont("Inter", size)
    if not f.exactMatch():
        f = QFont("Segoe UI", size)
    f.setWeight(_w(weight))
    f.setStyleStrategy(QFont.PreferAntialias)
    return f


def mono(size: int, weight: int = 500) -> QFont:
    """JetBrains Mono with Consolas/Courier New fallback."""
    f = QFont("JetBrains Mono", size)
    if not f.exactMatch():
        f = QFont("Consolas", size)
        if not f.exactMatch():
            f = QFont("Courier New", size)
    f.setWeight(_w(weight))
    f.setStyleStrategy(QFont.PreferAntialias)
    return f


def _w(w: int) -> int:
    table = {
        300: QFont.Light,    400: QFont.Normal,   500: QFont.Medium,
        600: QFont.DemiBold, 700: QFont.Bold,     800: QFont.ExtraBold,
    }
    return table.get(w, QFont.Medium)
