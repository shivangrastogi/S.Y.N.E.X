"""Design tokens — the single source of truth for the v6 look.

A faithful port of ``jv3-tokens.jsx``: the same palette (``J``), the same
four AI states with their ring speeds / pulse timing / glow opacity
(``JSTATES``), plus PyQt5-native helpers (QColor factories, fonts, the
``ca`` alpha helper, and a couple of shared QSS snippets).

Everything downstream pulls colours from here so a single edit re-themes the
whole app.
"""
from __future__ import annotations

from PyQt5.QtGui import QColor, QFont, QFontDatabase

# ── palette (mirrors the JS `J` object) ───────────────────────────────
#   stored as (r, g, b) so `ca()` can add any alpha on demand.
J = {
    "bg":      (10, 15, 28),      # #0A0F1C
    "bgEle":   (15, 23, 42),      # #0F172A
    "panel":   (13, 21, 37),
    "border":  (30, 41, 59),
    "cyan":    (0, 212, 255),
    "magenta": (255, 45, 149),
    "purple":  (168, 85, 247),
    "green":   (16, 185, 129),
    "amber":   (251, 191, 36),
    "red":     (248, 113, 113),
    "textPri": (234, 234, 234),
    "textSec": (148, 163, 184),
    "textMut": (100, 116, 139),
}


def ca(name_or_rgb, alpha: float = 1.0) -> QColor:
    """Return a QColor for a palette key (``"cyan"``) or an ``(r,g,b)`` tuple,
    with ``alpha`` in 0..1 — the PyQt equivalent of the JS ``ca()`` helper."""
    if isinstance(name_or_rgb, str):
        r, g, b = J[name_or_rgb]
    else:
        r, g, b = name_or_rgb
    c = QColor(r, g, b)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def col(name: str) -> QColor:
    """Opaque QColor for a palette key."""
    return ca(name, 1.0)


def rgba_str(name_or_rgb, alpha: float = 1.0) -> str:
    """`rgba(...)` CSS string for use inside Qt style sheets."""
    if isinstance(name_or_rgb, str):
        r, g, b = J[name_or_rgb]
    else:
        r, g, b = name_or_rgb
    return f"rgba({r},{g},{b},{alpha})"


# ── AI states (mirrors JSTATES) ───────────────────────────────────────
#   ring speeds are *seconds per full revolution* (lower = faster).
JSTATES = {
    "IDLE":       {"label": "IDLE",       "key": "cyan",
                   "ring": (13.0, 9.0, 6.0),   "pulse": 4.0,   "glowOp": 0.32},
    "LISTENING":  {"label": "LISTENING",  "key": "green",
                   "ring": (8.0, 5.0, 3.5),    "pulse": 1.4,   "glowOp": 0.70},
    "PROCESSING": {"label": "PROCESSING", "key": "magenta",
                   "ring": (2.0, 1.4, 0.9),    "pulse": 0.7,   "glowOp": 0.60},
    "SPEAKING":   {"label": "SPEAKING",   "key": "purple",
                   "ring": (5.0, 3.5, 2.2),    "pulse": 1.8,   "glowOp": 0.50},
}


def state_color(state: str) -> QColor:
    s = JSTATES.get(state, JSTATES["IDLE"])
    return col(s["key"])


# ── fonts ──────────────────────────────────────────────────────────────
#   The web build uses Inter + JetBrains Mono via Google Fonts. We try to
#   use those if installed; otherwise fall back to sane native stacks so the
#   app never renders in a serif default.
_INTER_FALLBACK = "Segoe UI"
_MONO_FALLBACK = "Consolas"


def _first_available(candidates, fallback) -> str:
    fams = set(QFontDatabase().families())
    for c in candidates:
        if c in fams:
            return c
    return fallback


def font_ui(size: int = 11, weight: int = QFont.Normal, spacing: float = 0.0) -> QFont:
    fam = _first_available(["Inter", "Segoe UI", "Roboto"], _INTER_FALLBACK)
    f = QFont(fam, size)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def font_mono(size: int = 10, weight: int = QFont.Normal, spacing: float = 0.0) -> QFont:
    fam = _first_available(["JetBrains Mono", "Cascadia Mono", "Consolas"], _MONO_FALLBACK)
    f = QFont(fam, size)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


# Qt QFont.Weight helpers (PyQt5 lacks the 100..900 numeric API of CSS)
W_REGULAR = QFont.Normal
W_MEDIUM = QFont.Medium
W_SEMIBOLD = QFont.DemiBold
W_BOLD = QFont.Bold


# ── shared QSS ──────────────────────────────────────────────────────────
SCROLLBAR_QSS = f"""
QScrollBar:vertical {{ width: 5px; background: transparent; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {rgba_str('cyan', 0.18)}; border-radius: 2px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {rgba_str('cyan', 0.35)}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 5px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: {rgba_str('cyan', 0.18)}; border-radius: 2px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""

# Window/app base — deep navy with the v6 ink colour for text.
APP_QSS = f"""
QWidget {{ color: {rgba_str('textPri', 1.0)}; background: transparent; }}
QToolTip {{
    background: {rgba_str('panel', 0.98)}; color: {rgba_str('textPri', 1.0)};
    border: 1px solid {rgba_str('cyan', 0.4)}; padding: 4px 8px;
}}
""" + SCROLLBAR_QSS


# Logical design canvas (the JS app draws at 1440×900 then scales to fit).
CANVAS_W = 1440
CANVAS_H = 900
