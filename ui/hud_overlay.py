"""Heads-up floating overlay — always-on-top translucent status widget.

Shows at a glance:
  * Current AERIS state (IDLE / LISTENING / PROCESSING / SPEAKING)
  * Last recognised gesture
  * Last intent + skill the brain routed to

Designed to live in a corner of the screen so the user gets feedback
without flipping to the main AERIS window.

Subscribes to GestureEngine emits + reads brain state on a 1 Hz tick.
PyQt5-only — graceful no-op when missing or off-main-thread.

Public API:
    show_hud(corner='top-right')   — display the widget
    hide_hud()                     — close it
    is_hud_visible() -> bool
    set_state(label)               — update the AERIS state pill
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

log = logging.getLogger(__name__)


_HUD_INSTANCE = None    # type: ignore   (PyQt5 widget)
_LOCK = threading.RLock()


def is_hud_visible() -> bool:
    with _LOCK:
        return _HUD_INSTANCE is not None and _HUD_INSTANCE.isVisible() if _HUD_INSTANCE else False


def hide_hud() -> bool:
    global _HUD_INSTANCE
    with _LOCK:
        if _HUD_INSTANCE is None:
            return False
        try:
            _HUD_INSTANCE.close()
        except Exception:
            pass
        _HUD_INSTANCE = None
        return True


def show_hud(corner: str = "top-right") -> bool:
    """Build + show the HUD widget at the chosen corner.
    Returns True on success."""
    global _HUD_INSTANCE
    try:
        from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
        from PyQt5.QtCore import Qt, QTimer
        from PyQt5.QtGui import QFont, QColor, QPalette
    except Exception as e:
        log.info("[hud] PyQt5 unavailable: %s", e)
        return False

    if QApplication.instance() is None:
        # HUD only makes sense alongside the main AERIS app.
        log.info("[hud] no QApplication — refusing to spawn one off-main-thread.")
        return False

    with _LOCK:
        if _HUD_INSTANCE is not None and _HUD_INSTANCE.isVisible():
            log.info("[hud] already visible.")
            return True

        w = QWidget(None,
                    Qt.FramelessWindowHint
                    | Qt.WindowStaysOnTopHint
                    | Qt.Tool)
        w.setAttribute(Qt.WA_TranslucentBackground)
        w.setAttribute(Qt.WA_ShowWithoutActivating)
        w.resize(260, 110)

        # Translucent dark card with rounded corners (CSS).
        w.setStyleSheet("""
            QWidget#hudRoot {
                background-color: rgba(15, 20, 30, 200);
                border: 1px solid rgba(100, 200, 255, 120);
                border-radius: 12px;
            }
            QLabel#hudTitle {
                color: rgba(120, 220, 255, 220);
                font-weight: 600;
            }
            QLabel#hudState {
                color: rgba(255, 255, 255, 255);
                font-weight: 700;
            }
            QLabel#hudLine {
                color: rgba(200, 220, 235, 210);
            }
        """)
        w.setObjectName("hudRoot")

        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        title = QLabel("AERIS · HUD")
        title.setObjectName("hudTitle")
        title.setFont(QFont("Segoe UI", 9))
        layout.addWidget(title)

        state_label = QLabel("IDLE")
        state_label.setObjectName("hudState")
        state_label.setFont(QFont("Segoe UI", 16))
        layout.addWidget(state_label)

        gesture_label = QLabel("gesture: —")
        gesture_label.setObjectName("hudLine")
        gesture_label.setFont(QFont("Consolas", 8))
        layout.addWidget(gesture_label)

        intent_label = QLabel("intent: —")
        intent_label.setObjectName("hudLine")
        intent_label.setFont(QFont("Consolas", 8))
        layout.addWidget(intent_label)

        # Position at the requested corner of the primary screen.
        try:
            geom = QApplication.primaryScreen().availableGeometry()
            margin = 16
            corners = {
                "top-right":    (geom.right() - w.width() - margin,
                                 geom.top() + margin),
                "top-left":     (geom.left() + margin,
                                 geom.top() + margin),
                "bottom-right": (geom.right() - w.width() - margin,
                                 geom.bottom() - w.height() - margin),
                "bottom-left":  (geom.left() + margin,
                                 geom.bottom() - w.height() - margin),
            }
            x, y = corners.get(corner, corners["top-right"])
            w.move(int(x), int(y))
        except Exception:
            pass

        # State stash for the listener (closures capture by reference)
        store = {
            "last_gesture": "—",
            "last_intent": "—",
            "state": "IDLE",
        }

        def _on_gesture(name: str) -> None:
            store["last_gesture"] = name

        # Wire up to the live engine if present.
        try:
            from core.gesture_engine import get_gesture_engine
            get_gesture_engine().add_listener(_on_gesture)
        except Exception:
            pass

        def _tick():
            try:
                gesture_label.setText(f"gesture: {store['last_gesture']}")
                intent_label.setText(f"intent: {store['last_intent']}")
                state_label.setText(store["state"])
            except Exception:
                pass

        timer = QTimer(w)
        timer.timeout.connect(_tick)
        timer.start(500)
        w._aeris_store = store      # type: ignore  (stash for external set_state)
        w._aeris_timer = timer      # type: ignore

        w.show()
        _HUD_INSTANCE = w
        log.info("[hud] shown at corner=%s", corner)
        return True


def set_state(label: str) -> None:
    """Update the big state pill — called by the main window when AERIS
    transitions IDLE → LISTENING → PROCESSING → SPEAKING."""
    with _LOCK:
        if _HUD_INSTANCE is None:
            return
        try:
            _HUD_INSTANCE._aeris_store["state"] = str(label)
        except Exception:
            pass


def set_intent(label: str) -> None:
    """Update the intent line — called by the main window's brain-responded slot."""
    with _LOCK:
        if _HUD_INSTANCE is None:
            return
        try:
            _HUD_INSTANCE._aeris_store["last_intent"] = str(label)[:40]
        except Exception:
            pass
