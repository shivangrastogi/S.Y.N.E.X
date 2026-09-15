"""CommandPalette — the ⌘K / Ctrl+K fuzzy launcher (jv6-command-palette.jsx).

A full-window dimmed overlay with a centered search field and a filtered
result list spanning navigation, quick asks, and registered skills. Type to
filter, ↑/↓ to move, Enter to run, Esc to close. Emits ``command(dict)`` with
shapes ``{"type":"nav","to":key}`` / ``{"type":"ask","text":...}`` /
``{"type":"mic"}``.
"""
from __future__ import annotations

from PyQt5.QtCore import QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QKeyEvent, QPainter
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget,
)

from ui.aeris_v6.tokens import (
    J, W_BOLD, W_MEDIUM, col, font_mono, font_ui, rgba_str,
)
from ui.aeris_v6.widgets import IconWidget


def _base_commands():
    nav = [
        ("Go to Home", "home", {"type": "nav", "to": "home"}),
        ("Open Conversations", "chat", {"type": "nav", "to": "chat"}),
        ("Open Automations", "auto", {"type": "nav", "to": "auto"}),
        ("Open Brain", "brain", {"type": "nav", "to": "brain"}),
        ("Open Memory", "memory", {"type": "nav", "to": "memory"}),
        ("Open System", "system", {"type": "nav", "to": "system"}),
        ("Open Settings", "settings", {"type": "nav", "to": "settings"}),
    ]
    quick = [
        ("Ask: What did I do today?", "chat", {"type": "ask", "text": "What did I do today?"}),
        ("Ask: System health check", "system", {"type": "ask", "text": "system health check"}),
        ("Ask: Resume my last task", "chat", {"type": "ask", "text": "resume my last task"}),
        ("Start voice capture", "mic", {"type": "mic"}),
    ]
    return nav + quick


def _skill_commands(limit=40):
    out = []
    try:
        from core.skill_registry import all_skills
        for s in list(all_skills().values())[:limit]:
            label = f"Run skill: {s.name.replace('_', ' ')}"
            out.append((label, "auto", {"type": "ask", "text": s.name.replace("_", " ")}))
    except Exception:
        pass
    return out


class _ResultRow(QFrame):
    def __init__(self, label, icon, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        lay = QHBoxLayout(self); lay.setContentsMargins(14, 0, 14, 0); lay.setSpacing(12)
        self._icon = IconWidget(icon, 15, col("textMut"))
        lay.addWidget(self._icon)
        self._label = QLabel(label); self._label.setFont(font_ui(11, W_MEDIUM))
        self._label.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        lay.addWidget(self._label); lay.addStretch(1)
        self._set(False)

    def _set(self, active):
        if active:
            self.setStyleSheet(f"_ResultRow{{background:{rgba_str('cyan',0.1)};"
                               f"border:1px solid {rgba_str('cyan',0.3)};border-radius:8px;}}")
            self._icon.set_color(col("cyan"))
            self._label.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
        else:
            self.setStyleSheet("_ResultRow{background:transparent;border:1px solid transparent;}")
            self._icon.set_color(col("textMut"))
            self._label.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")


class CommandPalette(QWidget):
    command = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self._all = _base_commands() + _skill_commands()
        self._filtered = list(self._all)
        self._sel = 0
        self._rows = []

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 90, 0, 0)
        outer.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self._panel = QFrame()
        self._panel.setFixedWidth(560)
        self._panel.setStyleSheet(
            f"QFrame{{background:{rgba_str((10,15,28), 0.98)};"
            f"border:1px solid {rgba_str('cyan', 0.25)};border-radius:14px;}}"
        )
        pl = QVBoxLayout(self._panel); pl.setContentsMargins(0, 0, 0, 8); pl.setSpacing(0)

        search_row = QFrame()
        search_row.setStyleSheet("background:transparent;border-bottom:1px solid "
                                 f"{rgba_str('border',0.6)};")
        sl = QHBoxLayout(search_row); sl.setContentsMargins(16, 12, 16, 12); sl.setSpacing(10)
        sl.addWidget(IconWidget("search", 16, col("cyan")))
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or search…")
        self._input.setFont(font_ui(13))
        self._input.setStyleSheet(f"QLineEdit{{background:transparent;border:0;"
                                  f"color:{rgba_str('textPri',1)};}}")
        self._input.textChanged.connect(self._refilter)
        sl.addWidget(self._input, 1)
        esc = QLabel("ESC"); esc.setFont(font_mono(8, W_BOLD))
        esc.setStyleSheet(f"color:{rgba_str('textMut',1)};background:{rgba_str('border',0.5)};"
                          "border-radius:4px;padding:2px 6px;")
        sl.addWidget(esc)
        pl.addWidget(search_row)

        self._results = QVBoxLayout(); self._results.setContentsMargins(8, 8, 8, 0)
        self._results.setSpacing(2)
        pl.addLayout(self._results)

        outer.addWidget(self._panel)
        outer.addStretch(1)
        self._rebuild_rows()

    # ── open/close ─────────────────────────────────────────────────
    def open(self):
        self._input.clear()
        self._refilter("")
        self.setVisible(True)
        self.raise_()
        self._input.setFocus()

    def close_palette(self):
        self.setVisible(False)

    # ── filtering ──────────────────────────────────────────────────
    def _refilter(self, text):
        q = (text or "").lower().strip()
        if not q:
            self._filtered = list(self._all)
        else:
            self._filtered = [c for c in self._all if all(tok in c[0].lower() for tok in q.split())]
        self._sel = 0
        self._rebuild_rows()

    def _rebuild_rows(self):
        while self._results.count():
            it = self._results.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._rows = []
        for i, (label, icon, _action) in enumerate(self._filtered[:8]):
            row = _ResultRow(label, icon)
            self._rows.append(row)
            self._results.addWidget(row)
        self._highlight()

    def _highlight(self):
        for i, row in enumerate(self._rows):
            row._set(i == self._sel)

    # ── keys ───────────────────────────────────────────────────────
    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key_Escape:
            self.close_palette(); return
        if e.key() in (Qt.Key_Down, Qt.Key_Tab):
            self._sel = (self._sel + 1) % max(1, len(self._rows)); self._highlight(); return
        if e.key() == Qt.Key_Up:
            self._sel = (self._sel - 1) % max(1, len(self._rows)); self._highlight(); return
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._run(); return
        super().keyPressEvent(e)

    def _run(self):
        if 0 <= self._sel < len(self._filtered):
            action = self._filtered[self._sel][2]
            self.close_palette()
            self.command.emit(action)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 150))
        p.end()

    def mousePressEvent(self, e):
        # click outside the panel closes
        if not self._panel.geometry().contains(e.pos()):
            self.close_palette()
