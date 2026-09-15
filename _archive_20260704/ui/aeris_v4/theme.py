"""Design tokens — colors, AI states, fonts. Mirrors aeris-core.jsx."""
from __future__ import annotations

from dataclasses import dataclass
from PyQt5.QtGui import QColor, QFont, QFontDatabase


# ── Colors ─────────────────────────────────────────────────────────────────
class C:
    BG       = QColor(10, 15, 28)        # app background
    PANEL    = QColor(15, 23, 42)        # sidebar / title-bar / chat panel
    CARD     = QColor(13, 21, 37)        # nested cards
    BORDER   = QColor(30, 41, 59)
    CYAN     = QColor(0, 212, 255)
    GREEN    = QColor(16, 185, 129)
    RED      = QColor(248, 113, 113)
    PURPLE   = QColor(168, 85, 247)
    AMBER    = QColor(251, 191, 36)
    TEXT_PRI = QColor(234, 234, 234)
    TEXT_SEC = QColor(148, 163, 184)
    TEXT_MUT = QColor(100, 116, 139)
    WHITE    = QColor(255, 255, 255)
    BLACK    = QColor(0, 0, 0)


def rgba(color: QColor, alpha: float) -> QColor:
    """Return a copy of `color` with the given alpha in [0,1]."""
    c = QColor(color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


# ── AI States ──────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class StateSpec:
    label: str
    color: QColor
    ring_r1_ms: int     # outer ring rotation period
    ring_r2_ms: int     # middle ring
    ring_r3_ms: int     # inner ring
    pulse_ms: int       # core pulse period
    glow_op: float      # base glow opacity


STATES = {
    "IDLE":       StateSpec("IDLE",       C.CYAN,   14000, 10000, 7000, 4000, 0.35),
    "LISTENING":  StateSpec("LISTENING",  C.GREEN,   9000,  6000, 4000, 1500, 0.70),
    "PROCESSING": StateSpec("PROCESSING", C.CYAN,    3000,  2000, 1200,  800, 0.55),
    "SPEAKING":   StateSpec("SPEAKING",   C.PURPLE,  6000,  4000, 2500, 2000, 0.50),
    "ERROR":      StateSpec("ERROR",      C.RED,     8000,  5000, 3000,  500, 0.60),
}


# ── Fonts ──────────────────────────────────────────────────────────────────
_FONTS_LOADED = False


def load_fonts():
    """Inter + JetBrains Mono. Silent fallback to system fonts if unavailable."""
    global _FONTS_LOADED
    if _FONTS_LOADED:
        return
    _FONTS_LOADED = True
    # If bundled font files exist we could register here; for now rely on system.


def inter(size: int, weight: int = 500) -> QFont:
    """weight: 400=Regular, 500=Medium, 600=SemiBold, 700=Bold."""
    load_fonts()
    f = QFont("Inter", size)
    if not f.exactMatch():
        f = QFont("Segoe UI", size)
    f.setWeight(_weight_to_qt(weight))
    f.setStyleStrategy(QFont.PreferAntialias)
    return f


def mono(size: int, weight: int = 500) -> QFont:
    load_fonts()
    f = QFont("JetBrains Mono", size)
    if not f.exactMatch():
        f = QFont("Consolas", size)
        if not f.exactMatch():
            f = QFont("Courier New", size)
    f.setWeight(_weight_to_qt(weight))
    f.setStyleStrategy(QFont.PreferAntialias)
    return f


def _weight_to_qt(w: int) -> int:
    table = {300: QFont.Light, 400: QFont.Normal, 500: QFont.Medium,
             600: QFont.DemiBold, 700: QFont.Bold, 800: QFont.ExtraBold}
    return table.get(w, QFont.Medium)
