"""Settings panel — PyQt5 dialog for editing the most-touched preferences.

Replaces hand-editing ``data/settings.json`` for the common cases:
  * Assistant name / wake word
  * Speech rate + volume
  * TTS voice (multi-language picker)
  * Gesture sensitivity
  * Master users + gate strictness
  * Default browser

Imports PyQt5 lazily inside ``open_settings_panel()`` so the module is
safe to import in headless tests / non-GUI processes.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


_TTS_VOICES = [
    "en-IN-NeerjaNeural",
    "en-IN-PrabhatNeural",
    "hi-IN-SwaraNeural",
    "hi-IN-MadhurNeural",
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
]
_SENSITIVITIES = ["very_sensitive", "sensitive", "normal", "relaxed", "very_relaxed"]


def open_settings_panel(parent=None) -> bool:
    """Show the modal settings dialog. Returns True if user saved changes.

    On any PyQt5 import error or display problem, returns False and the
    skill caller falls back to a "GUI unavailable" message.
    """
    try:
        from PyQt5.QtWidgets import (
            QApplication, QDialog, QFormLayout, QVBoxLayout, QHBoxLayout,
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
            QPushButton, QLabel, QListWidget, QListWidgetItem,
        )
        from PyQt5.QtCore import Qt
    except Exception as e:
        log.info("[settings_panel] PyQt5 unavailable: %s", e)
        return False

    try:
        from core import settings as _settings
    except Exception as e:
        log.info("[settings_panel] settings module unavailable: %s", e)
        return False

    app = QApplication.instance()
    spawned_app = False
    if app is None:
        # No QApplication yet — must create one. But QApplication MUST
        # be created on the MAIN thread, never a worker. If we're on a
        # non-main thread (typical when launched from a skill on a
        # daemon thread), bail out cleanly — calling QApplication(sys.argv)
        # off-main on Windows triggers an immediate access violation.
        import threading as _th
        if _th.current_thread() is not _th.main_thread():
            log.warning(
                "[settings_panel] cannot create QApplication on worker "
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
    dlg.setWindowTitle("AERIS — Settings")
    dlg.resize(420, 520)
    root = QVBoxLayout(dlg)
    form = QFormLayout()

    # ── Identity ──
    name_edit = QLineEdit(str(_settings.get("assistant_name") or "AERIS"))
    wake_edit = QLineEdit(str(_settings.get("wake_word") or "aeris"))
    form.addRow("Assistant name:", name_edit)
    form.addRow("Wake word:", wake_edit)

    # ── Voice ──
    rate_spin = QSpinBox()
    rate_spin.setRange(80, 350)
    rate_spin.setValue(int(_settings.get("speech_rate") or 175))
    rate_spin.setSuffix(" wpm")
    form.addRow("Speech rate:", rate_spin)

    vol_spin = QDoubleSpinBox()
    vol_spin.setRange(0.10, 1.00)
    vol_spin.setSingleStep(0.05)
    vol_spin.setDecimals(2)
    vol_spin.setValue(float(_settings.get("voice_volume", 1.0) or 1.0))
    form.addRow("Voice volume:", vol_spin)

    voice_combo = QComboBox()
    voice_combo.setEditable(True)
    voice_combo.addItems(_TTS_VOICES)
    cur_voice = str(_settings.get("tts_voice") or "")
    if cur_voice:
        idx = voice_combo.findText(cur_voice)
        if idx >= 0:
            voice_combo.setCurrentIndex(idx)
        else:
            voice_combo.setEditText(cur_voice)
    form.addRow("TTS voice:", voice_combo)

    # ── Gestures ──
    sens_combo = QComboBox()
    sens_combo.addItems(_SENSITIVITIES)
    cur_sens = str(_settings.get("gesture_sensitivity") or "normal")
    idx = sens_combo.findText(cur_sens)
    if idx >= 0:
        sens_combo.setCurrentIndex(idx)
    form.addRow("Gesture sensitivity:", sens_combo)

    # ── Master users ──
    masters_label = QLabel("Master users (face-gated):")
    masters_list = QListWidget()
    masters_list.setSelectionMode(QListWidget.ExtendedSelection)
    try:
        from core.face_recognition import get_registry
        known_faces = get_registry().all_names()
    except Exception:
        known_faces = []
    current_masters = [str(m).strip().lower() for m
                       in (_settings.get("master_users") or [])
                       if str(m).strip()]
    for name in sorted({*[n.lower() for n in known_faces], *current_masters}):
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if name in current_masters else Qt.Unchecked)
        masters_list.addItem(item)

    strict_box = QCheckBox("Strict mode — block gestures when NO face detected")
    strict_box.setChecked(bool(_settings.get("master_gate_strict", False)))

    # ── Browser ──
    browser_combo = QComboBox()
    browser_combo.setEditable(True)
    browser_combo.addItems(["system", "chrome", "brave", "edge", "firefox"])
    cur_br = str(_settings.get("default_browser") or "system")
    idx = browser_combo.findText(cur_br)
    if idx >= 0:
        browser_combo.setCurrentIndex(idx)
    else:
        browser_combo.setEditText(cur_br)
    form.addRow("Default browser:", browser_combo)

    root.addLayout(form)
    root.addWidget(masters_label)
    root.addWidget(masters_list)
    root.addWidget(strict_box)

    # ── Buttons ──
    btns = QHBoxLayout()
    save_btn = QPushButton("Save")
    cancel_btn = QPushButton("Cancel")
    btns.addStretch(1)
    btns.addWidget(save_btn)
    btns.addWidget(cancel_btn)
    root.addLayout(btns)

    saved = {"ok": False}

    def _on_save():
        try:
            _settings.set_("assistant_name", name_edit.text().strip() or "AERIS")
            _settings.set_("wake_word", wake_edit.text().strip() or "aeris")
            _settings.set_("speech_rate", int(rate_spin.value()))
            _settings.set_("voice_volume", float(vol_spin.value()))
            v = voice_combo.currentText().strip()
            _settings.set_("tts_voice", v)
            _settings.set_("gesture_sensitivity", sens_combo.currentText().strip())
            new_masters = []
            for i in range(masters_list.count()):
                it = masters_list.item(i)
                if it.checkState() == Qt.Checked:
                    new_masters.append(it.text().strip().lower())
            _settings.set_("master_users", sorted(set(new_masters)))
            _settings.set_("master_gate_strict", bool(strict_box.isChecked()))
            _settings.set_("default_browser", browser_combo.currentText().strip() or "system")
            saved["ok"] = True
            dlg.accept()
        except Exception as e:
            log.warning("[settings_panel] save failed: %s", e)
            dlg.reject()

    save_btn.clicked.connect(_on_save)
    cancel_btn.clicked.connect(dlg.reject)

    try:
        dlg.exec_()
    except Exception as e:
        log.warning("[settings_panel] exec failed: %s", e)
        return False
    finally:
        if spawned_app:
            try: app.quit()
            except Exception: pass

    return saved["ok"]
