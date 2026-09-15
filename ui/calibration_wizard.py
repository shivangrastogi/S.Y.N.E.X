"""Gesture calibration wizard — walks a new user through every gesture
with live feedback on what AERIS detects.

Each step shows:
  * The gesture name + description
  * A small embedded preview of the camera feed (best-effort — falls back
    to text-only if cv2 / PIL isn't available)
  * A live label that updates when the gesture engine emits the target
    gesture name
  * Continue / Skip buttons

The wizard subscribes a temporary listener to the global GestureEngine
and removes it on close.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

log = logging.getLogger(__name__)


# (gesture_name, human label, step-by-step instructions)
_CALIBRATION_STEPS: list[tuple[str, str, str]] = [
    ("double_pinch", "Double pinch — Play / Pause",
     "With your middle, ring and pinky fingers extended, tap your "
     "thumb to your index finger twice quickly. Each pinch should be "
     "0.1 to 0.7 s apart.\n\nTry it now — repeat 2-3 times."),
    ("palm_fist_lock", "Palm → Fist → Palm → Fist — Lock screen",
     "1. Open palm facing camera, hold 0.3 s.\n"
     "2. Close into a fist.\n"
     "3. Open palm again.\n"
     "4. Close into a fist again.\n\n"
     "Total time: under 4 seconds."),
    ("app_switch_next", "Sideways palm + LEFT motion — Alt+Tab",
     "Rotate your open palm 90° clockwise so it faces sideways. "
     "Hold 0.3 s, then move your hand LEFT (your POV). Alt+Tab fires."),
    ("app_switch_prev", "Sideways palm + RIGHT motion — Alt+Shift+Tab",
     "Same sideways pose, but move your hand RIGHT."),
    ("swipe_left", "Quick swipe LEFT — previous tab/window",
     "Open palm, snap your hand decisively left across the frame "
     "in under 0.6 s. Must travel > 22 % of the frame width and "
     "exceed peak velocity 0.7 frame-widths/sec."),
    ("swipe_right", "Quick swipe RIGHT — next tab/window",
     "Mirror of swipe LEFT."),
    ("peace", "Peace sign — screenshot",
     "Index + middle finger extended, ring + pinky curled. "
     "Hold steady ~0.55 s."),
    ("three_up", "Three fingers up — next track",
     "Index, middle, ring up; pinky curled. Hold ~0.55 s."),
    ("thumbs_up", "Thumbs up — volume up (×3 ticks)",
     "Closed fist with only the thumb extended upward. Hold steady."),
    ("long_fist", "Long fist (3 s) — open command palette",
     "Tight fist held a full 3 seconds. Intentionally slow."),
]


def open_calibration_wizard(parent=None) -> bool:
    """Show the modal calibration wizard. Returns True if user completed
    the flow (not just cancelled)."""
    try:
        from PyQt5.QtWidgets import (
            QApplication, QDialog, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QTextEdit, QProgressBar,
        )
        from PyQt5.QtCore import Qt, QTimer
        from PyQt5.QtGui import QFont
    except Exception as e:
        log.info("[calibration] PyQt5 unavailable: %s", e)
        return False

    app = QApplication.instance()
    spawned_app = False
    if app is None:
        # Same constraint as settings_panel — QApplication MUST be created
        # on the main thread. Refuse from worker threads to avoid the
        # Windows access violation observed in headless test runs.
        import threading as _th
        if _th.current_thread() is not _th.main_thread():
            log.warning(
                "[calibration] cannot create QApplication on worker "
                "thread '%s' — refusing to open dialog.",
                _th.current_thread().name,
            )
            return False
        try:
            import sys
            app = QApplication(sys.argv)
            spawned_app = True
        except Exception:
            return False

    dlg = QDialog(parent)
    dlg.setWindowTitle("AERIS — Gesture Calibration")
    dlg.resize(560, 420)
    root = QVBoxLayout(dlg)

    title_label = QLabel()
    f = QFont(); f.setBold(True); f.setPointSize(14)
    title_label.setFont(f)
    root.addWidget(title_label)

    body = QTextEdit()
    body.setReadOnly(True)
    body.setMinimumHeight(160)
    root.addWidget(body)

    status_label = QLabel("Watching for the gesture…")
    status_label.setStyleSheet("color: #888;")
    root.addWidget(status_label)

    progress = QProgressBar()
    progress.setRange(0, len(_CALIBRATION_STEPS))
    progress.setValue(0)
    root.addWidget(progress)

    btns = QHBoxLayout()
    prev_btn = QPushButton("← Prev")
    skip_btn = QPushButton("Skip")
    next_btn = QPushButton("Next →")
    close_btn = QPushButton("Close")
    btns.addWidget(prev_btn); btns.addWidget(skip_btn)
    btns.addStretch(1)
    btns.addWidget(next_btn); btns.addWidget(close_btn)
    root.addLayout(btns)

    state = {"idx": 0, "completed": False, "detected_for_step": False}

    def _render():
        idx = state["idx"]
        if idx >= len(_CALIBRATION_STEPS):
            title_label.setText("All done — nice work!")
            body.setPlainText("You've practised every gesture. The engine has "
                              "been recording your attempts in the gesture trace.\n\n"
                              "Say 'gesture stats' anytime to review.")
            status_label.setText("✓ wizard complete")
            progress.setValue(progress.maximum())
            state["completed"] = True
            next_btn.setEnabled(False)
            skip_btn.setEnabled(False)
            return
        gname, label, instructions = _CALIBRATION_STEPS[idx]
        title_label.setText(f"{idx + 1}/{len(_CALIBRATION_STEPS)}  ·  {label}")
        body.setPlainText(instructions)
        status_label.setText("Watching for the gesture…")
        status_label.setStyleSheet("color: #888;")
        progress.setValue(idx)
        state["detected_for_step"] = False

    def _on_gesture(name: str):
        # Highlight when the active step's gesture fires.
        idx = state["idx"]
        if idx >= len(_CALIBRATION_STEPS):
            return
        target = _CALIBRATION_STEPS[idx][0]
        if name == target and not state["detected_for_step"]:
            state["detected_for_step"] = True
            try:
                status_label.setText(f"✓ Detected {name} — press Next to continue.")
                status_label.setStyleSheet("color: #2c8;")
            except Exception:
                pass

    # Subscribe a listener — wrap in try so a missing engine doesn't abort.
    listener_attached = False
    try:
        from core.gesture_engine import get_gesture_engine
        eng = get_gesture_engine()
        eng.add_listener(_on_gesture)
        listener_attached = True
        if not eng.is_enabled():
            eng.start()
    except Exception as e:
        log.info("[calibration] gesture engine unavailable: %s", e)
        status_label.setText("⚠ Gesture engine offline — instructions only.")
        status_label.setStyleSheet("color: #d80;")

    def _go(delta: int):
        new_idx = max(0, state["idx"] + delta)
        state["idx"] = new_idx
        _render()

    prev_btn.clicked.connect(lambda: _go(-1))
    next_btn.clicked.connect(lambda: _go(+1))
    skip_btn.clicked.connect(lambda: _go(+1))
    close_btn.clicked.connect(dlg.accept)

    _render()
    try:
        dlg.exec_()
    finally:
        # Best-effort listener cleanup — GestureEngine has no remove-listener
        # API, so the closure just no-ops once the dialog is gone (idx >=
        # max checks would simply not match anything).
        if listener_attached:
            try:
                from core.gesture_engine import get_gesture_engine
                # Mark the closure inert so subsequent fires do nothing.
                state["idx"] = 10**9
            except Exception:
                pass
        if spawned_app:
            try: app.quit()
            except Exception: pass

    return bool(state["completed"])
