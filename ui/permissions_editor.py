"""Permissions matrix editor — masters × gestures grid with checkboxes.

Replaces voice-driven ``master_grant`` / ``master_block`` calls when the
user wants to make many changes at once. Each row is a master, each
column is a known gesture; checked = allowed, unchecked = blocked.
Saves to settings ``master_permissions`` on click.

Also exports a stateless helper ``build_matrix(masters, perms, gestures)``
that the tests use without a Qt event loop.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


# Conservative kid-safe default (mirrors skills/master_permissions._KID_SAFE_DEFAULT)
_DEFAULT_SAFE = {
    "double_pinch", "swipe_left", "swipe_right",
    "swipe_up", "swipe_down", "peace", "three_up",
    "thumbs_up", "thumbs_down", "wave",
}


def build_matrix(masters: list[str], perms: dict, gestures: list[str]) -> dict:
    """Return a {master: {gesture: bool}} grid suitable for rendering.
    Pure function — no Qt. Tested directly.

    A master with ``["all"]`` in perms is fully allowed.
    A master not in perms is treated as fully allowed (default open).
    """
    out: dict[str, dict[str, bool]] = {}
    for m in masters:
        m_lo = m.strip().lower()
        cur = perms.get(m_lo)
        if cur is None or "all" in cur or "*" in cur:
            out[m_lo] = {g: True for g in gestures}
        else:
            allowed = set(cur)
            out[m_lo] = {g: (g in allowed) for g in gestures}
    return out


def matrix_to_perms(matrix: dict) -> dict:
    """Inverse of build_matrix — converts {master: {gesture: bool}} back
    into the {master: [gesture, ...]} settings shape. If every gesture is
    allowed, collapses to ``["all"]``."""
    out: dict[str, list[str]] = {}
    for master, row in matrix.items():
        m_lo = master.strip().lower()
        if not row:
            continue
        if all(row.values()):
            out[m_lo] = ["all"]
        else:
            out[m_lo] = sorted(g for g, on in row.items() if on)
    return out


def open_permissions_editor(parent=None) -> bool:
    """Show the modal editor. Returns True if user saved changes."""
    try:
        from PyQt5.QtWidgets import (
            QApplication, QDialog, QTableWidget, QTableWidgetItem,
            QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox, QHeaderView,
        )
        from PyQt5.QtCore import Qt
    except Exception as e:
        log.info("[permissions_editor] PyQt5 unavailable: %s", e)
        return False

    if QApplication.instance() is None:
        # Refuse off-main-thread spawn — same constraint as the other dialogs.
        import threading as _th
        if _th.current_thread() is not _th.main_thread():
            log.warning("[permissions_editor] off-main-thread spawn refused.")
            return False
        try:
            import sys
            QApplication(sys.argv)
        except Exception:
            return False

    try:
        from core import settings as _settings
        from core.face_recognition import get_registry
        from core.gesture_engine import DEFAULT_ACTIONS
    except Exception as e:
        log.info("[permissions_editor] dependency import failed: %s", e)
        return False

    masters = list((_settings.get("master_users") or []))
    if not masters:
        # Fall back to every face known to the registry — gives the user
        # something to toggle even before they've curated a master list.
        masters = get_registry().all_names() or []
    masters = sorted({str(m).strip().lower() for m in masters if str(m).strip()})
    gestures = sorted(DEFAULT_ACTIONS.keys())
    perms = _settings.get("master_permissions") or {}
    matrix = build_matrix(masters, perms, gestures)

    dlg = QDialog(parent)
    dlg.setWindowTitle("AERIS — Permissions Editor")
    dlg.resize(720, 460)
    root = QVBoxLayout(dlg)
    root.addWidget(QLabel("Tick which gestures each master is allowed to fire. "
                          "Row of all ticks collapses to 'all'."))

    if not masters:
        root.addWidget(QLabel("(No master users registered yet — say "
                              "'i am master' first, then reopen this editor.)"))
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        root.addWidget(close)
        try: dlg.exec_()
        except Exception: pass
        return False

    table = QTableWidget(len(masters), len(gestures))
    table.setHorizontalHeaderLabels(gestures)
    table.setVerticalHeaderLabels(masters)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    # One checkbox per cell; store the checkbox widgets so we can read them.
    checks: dict[tuple[str, str], "QCheckBox"] = {}
    for r, m in enumerate(masters):
        for c, g in enumerate(gestures):
            cb = QCheckBox()
            cb.setChecked(bool(matrix[m][g]))
            table.setCellWidget(r, c, cb)
            checks[(m, g)] = cb

    root.addWidget(table)

    btns = QHBoxLayout()
    save_btn = QPushButton("Save")
    cancel_btn = QPushButton("Cancel")
    btns.addStretch(1)
    btns.addWidget(save_btn); btns.addWidget(cancel_btn)
    root.addLayout(btns)

    saved = {"ok": False}

    def _on_save():
        new_matrix: dict[str, dict[str, bool]] = {m: {} for m in masters}
        for (m, g), cb in checks.items():
            new_matrix[m][g] = bool(cb.isChecked())
        _settings.set_("master_permissions", matrix_to_perms(new_matrix))
        saved["ok"] = True
        dlg.accept()

    save_btn.clicked.connect(_on_save)
    cancel_btn.clicked.connect(dlg.reject)
    try:
        dlg.exec_()
    except Exception as e:
        log.warning("[permissions_editor] exec failed: %s", e)
    return saved["ok"]
