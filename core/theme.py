"""Theme switcher — applies QApplication-wide stylesheets.

Three built-in themes:
  * ``dark``   — default — deep slate background, cyan accents
  * ``light``  — high-contrast white background
  * ``cyber``  — neon-on-black hacker aesthetic

Persists choice via settings ``ui_theme``. The main window reads
``get_active_stylesheet()`` at boot; runtime switches call
``apply_theme()`` which calls ``QApplication.setStyleSheet``.

Public API:
    apply_theme(name) -> tuple[bool, str]
    current_theme()   -> str
    list_themes()     -> list[str]
    get_active_stylesheet() -> str
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


_DARK_QSS = """
QWidget {
    background-color: #0e1117;
    color: #e6edf3;
    font-family: 'Segoe UI', sans-serif;
}
QPushButton {
    background-color: #21262d;
    border: 1px solid #30363d;
    padding: 6px 14px;
    border-radius: 6px;
}
QPushButton:hover { background-color: #30363d; }
QPushButton:pressed { background-color: #1f6feb; }
QLineEdit, QTextEdit, QListWidget {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #1f6feb;
}
QComboBox {
    background-color: #21262d;
    border: 1px solid #30363d;
    padding: 4px;
    border-radius: 6px;
}
"""

_LIGHT_QSS = """
QWidget {
    background-color: #ffffff;
    color: #1f2328;
    font-family: 'Segoe UI', sans-serif;
}
QPushButton {
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    padding: 6px 14px;
    border-radius: 6px;
}
QPushButton:hover { background-color: #eaeef2; }
QPushButton:pressed { background-color: #0969da; color: white; }
QLineEdit, QTextEdit, QListWidget {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #0969da;
    selection-color: white;
}
"""

_CYBER_QSS = """
QWidget {
    background-color: #000010;
    color: #00ff95;
    font-family: 'Consolas', 'Courier New', monospace;
}
QPushButton {
    background-color: #001525;
    border: 1px solid #00ff95;
    padding: 6px 14px;
    border-radius: 4px;
    color: #00ff95;
}
QPushButton:hover { background-color: #003344; }
QPushButton:pressed { background-color: #00ff95; color: #000010; }
QLineEdit, QTextEdit, QListWidget {
    background-color: #000018;
    border: 1px solid #00aa66;
    border-radius: 4px;
    padding: 4px;
    color: #00ffaa;
    selection-background-color: #00ff95;
    selection-color: #000010;
}
"""


_THEMES: dict[str, str] = {
    "dark":  _DARK_QSS,
    "light": _LIGHT_QSS,
    "cyber": _CYBER_QSS,
}


def list_themes() -> list[str]:
    return sorted(_THEMES.keys())


def current_theme() -> str:
    try:
        from core import settings as _settings
        v = (_settings.get("ui_theme") or "dark").strip().lower()
    except Exception:
        v = "dark"
    return v if v in _THEMES else "dark"


def get_active_stylesheet() -> str:
    return _THEMES.get(current_theme(), _DARK_QSS)


def apply_theme(name: str) -> tuple[bool, str]:
    """Persist + apply the named theme. Returns (ok, msg)."""
    name = (name or "").strip().lower()
    if name not in _THEMES:
        return False, (f"Unknown theme '{name}'. Options: "
                       + ", ".join(list_themes()))
    try:
        from core import settings as _settings
        _settings.set_("ui_theme", name)
    except Exception:
        pass
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(_THEMES[name])
    except Exception as e:
        log.info("[theme] applied to settings but Qt unreachable: %s", e)
    log.info("[theme] active → %s", name)
    return True, f"Theme → {name}."


def cycle_theme() -> tuple[str, str]:
    """Rotate to the next theme in list order. Returns (new_theme, msg)."""
    themes = list_themes()
    try:
        cur = themes.index(current_theme())
    except ValueError:
        cur = -1
    nxt = themes[(cur + 1) % len(themes)]
    _, msg = apply_theme(nxt)
    return nxt, msg
