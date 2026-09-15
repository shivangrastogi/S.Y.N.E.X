"""First-run setup wizard — walks a fresh user through the basics.

Five steps:
  1. Welcome + dependency report
  2. Face enrollment (uses ``i_am_master``)
  3. TTS voice picker (uses ``tts_voice_set``)
  4. Theme picker (uses ``theme_dark`` / etc.)
  5. Done — run diagnose for a final health check

Each step is independent — if a subsystem isn't available we mark the
step "skipped" and continue. PyQt5-only, main-thread enforced.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def open_first_run_wizard(parent=None) -> bool:
    try:
        from PyQt5.QtWidgets import (
            QApplication, QDialog, QVBoxLayout, QHBoxLayout,
            QLabel, QPushButton, QTextEdit, QComboBox, QProgressBar,
        )
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont
    except Exception as e:
        log.info("[first_run_wizard] PyQt5 unavailable: %s", e)
        return False

    if QApplication.instance() is None:
        import threading as _th
        if _th.current_thread() is not _th.main_thread():
            log.warning("[first_run_wizard] off-main-thread refused.")
            return False
        try:
            import sys
            QApplication(sys.argv)
        except Exception:
            return False

    dlg = QDialog(parent)
    dlg.setWindowTitle("AERIS — First-run setup")
    dlg.resize(620, 480)
    root = QVBoxLayout(dlg)

    title = QLabel()
    title.setFont(QFont("Segoe UI", 14, QFont.Bold))
    root.addWidget(title)

    body = QTextEdit()
    body.setReadOnly(True)
    body.setFont(QFont("Consolas", 10))
    root.addWidget(body)

    # Step 3 voice / step 4 theme pickers — added per-step.
    voice_combo = QComboBox()
    voice_combo.addItems([
        "en-IN-NeerjaNeural", "en-IN-PrabhatNeural",
        "hi-IN-SwaraNeural",  "hi-IN-MadhurNeural",
        "en-US-AriaNeural",   "en-US-GuyNeural",
        "en-GB-SoniaNeural",  "en-GB-RyanNeural",
    ])
    voice_combo.setVisible(False)
    root.addWidget(voice_combo)

    theme_combo = QComboBox()
    theme_combo.addItems(["dark", "light", "cyber"])
    theme_combo.setVisible(False)
    root.addWidget(theme_combo)

    progress = QProgressBar()
    progress.setRange(0, 5)
    root.addWidget(progress)

    btns = QHBoxLayout()
    back_btn = QPushButton("← Back")
    skip_btn = QPushButton("Skip")
    next_btn = QPushButton("Next →")
    btns.addStretch(1)
    btns.addWidget(back_btn); btns.addWidget(skip_btn); btns.addWidget(next_btn)
    root.addLayout(btns)

    state = {"step": 0, "completed": False}

    # ── step renderers ────────────────────────────────────────────

    def _step_welcome():
        title.setText("1. Welcome")
        try:
            from core.dep_validator import health_score, list_deps
            score = health_score()
            missing = [r for r in list_deps() if not r["installed"]]
        except Exception:
            score, missing = 100, []
        text = (
            f"Welcome to AERIS!\n\n"
            f"Dependency health: {score}/100.\n"
            + (f"{len(missing)} optional dep(s) missing — that's OK, the rest "
               f"still work. Say 'dep check' anytime for the list.\n"
               if missing else "All optional dependencies present.\n")
            + "\n"
            "This wizard takes you through:\n"
            "  • enrolling your face as the master user\n"
            "  • picking a TTS voice\n"
            "  • picking a UI theme\n"
            "  • a final health check\n"
        )
        body.setPlainText(text)
        voice_combo.setVisible(False)
        theme_combo.setVisible(False)

    def _step_face():
        title.setText("2. Enroll your face (master user)")
        body.setPlainText(
            "Click Next while looking at the camera. We'll enroll your face "
            "+ mark it as a master user so only you can fire gestures.\n\n"
            "If you don't have a camera (or insightface isn't installed), "
            "click Skip — you can do this later with 'i am master'."
        )
        voice_combo.setVisible(False)
        theme_combo.setVisible(False)

    def _do_face():
        try:
            from skills.master_users import i_am_master
            return i_am_master({"raw_text": "i am master"})
        except Exception as e:
            return f"face enroll fail: {e}"

    def _step_voice():
        title.setText("3. Pick your TTS voice")
        body.setPlainText(
            "Pick the AERIS voice. en-IN-NeerjaNeural (default) is great "
            "for Hinglish; pick a different locale if you prefer.\n\n"
            "Click Next to save the selection."
        )
        voice_combo.setVisible(True)
        theme_combo.setVisible(False)

    def _do_voice():
        try:
            from core import settings as _settings
            _settings.set_("tts_voice", voice_combo.currentText().strip())
            return f"TTS voice → {voice_combo.currentText()}."
        except Exception as e:
            return f"voice save fail: {e}"

    def _step_theme():
        title.setText("4. Pick your UI theme")
        body.setPlainText(
            "Three built-in themes:\n"
            "  • dark   — slate background, cyan accents (default)\n"
            "  • light  — high-contrast white background\n"
            "  • cyber  — neon-on-black hacker aesthetic\n\n"
            "Click Next to apply."
        )
        voice_combo.setVisible(False)
        theme_combo.setVisible(True)

    def _do_theme():
        try:
            from core.theme import apply_theme
            _, msg = apply_theme(theme_combo.currentText().strip())
            return msg
        except Exception as e:
            return f"theme apply fail: {e}"

    def _step_done():
        title.setText("5. Done — running diagnose…")
        try:
            from skills.diagnostics import diagnostics
            report = diagnostics({})
        except Exception as e:
            report = f"(diagnose unavailable: {e})"
        body.setPlainText(
            "You're set up! Try a voice command or open the command palette "
            "(Ctrl+Shift+P).\n\n"
            "── Diagnostics ──\n" + report
        )
        voice_combo.setVisible(False)
        theme_combo.setVisible(False)
        state["completed"] = True
        next_btn.setText("Finish")

    # ── flow controller ──────────────────────────────────────────

    renderers = [_step_welcome, _step_face, _step_voice, _step_theme, _step_done]

    def _render():
        idx = max(0, min(state["step"], len(renderers) - 1))
        renderers[idx]()
        progress.setValue(idx + 1)
        back_btn.setEnabled(idx > 0)
        skip_btn.setEnabled(idx < len(renderers) - 1)

    def _commit(idx: int):
        """Run the side-effect for step ``idx`` (the one just completed)."""
        try:
            if idx == 1:
                msg = _do_face()
            elif idx == 2:
                msg = _do_voice()
            elif idx == 3:
                msg = _do_theme()
            else:
                return
            log.info("[first_run_wizard] step %d → %s", idx, msg)
        except Exception as e:
            log.warning("[first_run_wizard] step %d commit raised: %s", idx, e)

    def _advance(commit: bool):
        if commit and state["step"] in (1, 2, 3):
            _commit(state["step"])
        if state["step"] >= len(renderers) - 1:
            dlg.accept()
            return
        state["step"] += 1
        _render()

    def _retreat():
        if state["step"] > 0:
            state["step"] -= 1
            _render()

    next_btn.clicked.connect(lambda: _advance(commit=True))
    skip_btn.clicked.connect(lambda: _advance(commit=False))
    back_btn.clicked.connect(_retreat)

    _render()
    try:
        dlg.exec_()
    except Exception as e:
        log.warning("[first_run_wizard] exec failed: %s", e)
    return bool(state["completed"])
