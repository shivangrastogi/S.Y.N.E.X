"""Telemetry dashboard — PyQt5 tabbed view of usage stats.

Tabs:
  * Overview   — single-line counters (memos, journal, KG triples, faces)
  * Gestures   — fire/block counts + per-name table (last hour)
  * Skills     — top-fired skill names (last hour)
  * Workspace  — per-app totals (last hour) from the workspace tracker

All data sourced from ``core.telemetry`` — the dashboard is pure
presentation.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


def open_telemetry_dashboard(parent=None) -> bool:
    try:
        from PyQt5.QtWidgets import (
            QApplication, QDialog, QTabWidget, QVBoxLayout,
            QLabel, QTextEdit, QTableWidget, QTableWidgetItem,
            QHeaderView, QPushButton, QHBoxLayout,
        )
        from PyQt5.QtCore import Qt, QTimer
        from PyQt5.QtGui import QFont
    except Exception as e:
        log.info("[telemetry_dashboard] PyQt5 unavailable: %s", e)
        return False

    if QApplication.instance() is None:
        import threading as _th
        if _th.current_thread() is not _th.main_thread():
            log.warning("[telemetry_dashboard] off-main-thread refused.")
            return False
        try:
            import sys
            QApplication(sys.argv)
        except Exception:
            return False

    try:
        from core import telemetry as tel
    except Exception as e:
        log.info("[telemetry_dashboard] telemetry import failed: %s", e)
        return False

    dlg = QDialog(parent)
    dlg.setWindowTitle("AERIS — Telemetry Dashboard")
    dlg.resize(700, 480)
    root = QVBoxLayout(dlg)

    tabs = QTabWidget()
    root.addWidget(tabs)

    # ── Overview tab ──
    over = QTextEdit()
    over.setReadOnly(True)
    over.setFont(QFont("Consolas", 10))
    tabs.addTab(over, "Overview")

    # ── Gestures tab ──
    gest_box = QTextEdit()
    gest_box.setReadOnly(True)
    gest_box.setFont(QFont("Consolas", 10))
    tabs.addTab(gest_box, "Gestures")

    # ── Skills tab ──
    skill_box = QTextEdit()
    skill_box.setReadOnly(True)
    skill_box.setFont(QFont("Consolas", 10))
    tabs.addTab(skill_box, "Skills")

    # ── Workspace tab ──
    ws_box = QTextEdit()
    ws_box.setReadOnly(True)
    ws_box.setFont(QFont("Consolas", 10))
    tabs.addTab(ws_box, "Workspace")

    btns = QHBoxLayout()
    refresh_btn = QPushButton("Refresh")
    close_btn = QPushButton("Close")
    btns.addStretch(1); btns.addWidget(refresh_btn); btns.addWidget(close_btn)
    root.addLayout(btns)

    def _render():
        snap = tel.snapshot(window_h=1.0)
        over.setPlainText(
            f"Memos:           {snap['memos']}\n"
            f"Journal entries: {snap['journal']}\n"
            f"KG triples:      {snap['kg']}\n"
            f"Faces enrolled:  {snap['faces']}\n"
            f"Workspace events:{snap['workspace']['events']}\n"
            f"Last 1 h gestures: {snap['gesture']['total']} total "
            f"({snap['gesture']['fired']} fired, "
            f"{snap['gesture']['blocked']} blocked)\n"
            f"Last 1 h skills:   {snap['skill']['total']} fired"
        )
        g = snap["gesture"]
        lines = [f"Last {g['window_h']:.1f} h · "
                 f"{g['fired']} fired · {g['blocked']} blocked"]
        for name, n in g["ranked"][:20]:
            lines.append(f"  {n:4d}  {name}")
        gest_box.setPlainText("\n".join(lines) if g["total"] else
                              "No gesture trace events in the last hour.")
        s = snap["skill"]
        if s["ranked"]:
            sk_lines = [f"Top fired skills (last hour, {s['total']} total):"]
            for name, n in s["ranked"][:20]:
                sk_lines.append(f"  {n:4d}  {name}")
            skill_box.setPlainText("\n".join(sk_lines))
        else:
            skill_box.setPlainText("No skill fires in the last hour.")
        ws_box.setPlainText(snap["workspace"]["summary"] or "(empty)")

    refresh_btn.clicked.connect(_render)
    close_btn.clicked.connect(dlg.accept)

    # Auto-refresh every 5 s while the dialog is open.
    timer = QTimer(dlg)
    timer.timeout.connect(_render)
    timer.start(5000)

    _render()
    try:
        dlg.exec_()
    finally:
        timer.stop()
    return True
