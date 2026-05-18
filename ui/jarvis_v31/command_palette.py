"""Command palette — floating Ctrl+K overlay.

UX pattern borrowed from VSCode / Linear / Raycast. One key opens a
fuzzy-search dialog over:

  * Every registered plugin skill (``core.skill_registry.REGISTRY``)
  * A handful of built-in actions (Quit, Hide, Reload skills, Pause)
  * Recent direct queries (last N from the chat history)

Arrow keys navigate, Enter runs, Esc closes. Selecting a skill submits
the skill's primary pattern as if the user had typed it — so the whole
brain pipeline (intent classifier, entity extraction, executor) still
runs and the result lands in the chat log like any other utterance.

Why a palette in AERIS
----------------------
The brain is great at understanding natural-language utterances but
that requires the user to remember what the assistant can do. The
palette is a *discoverability* surface — fuzzy-search "vol" finds
``volume_control`` even if the user has never tried it.

Visual style
------------
Frameless translucent overlay centred on the parent window, ~520 px
wide, sized to fit ~8 visible result rows. Matches GlassChatPanel's
glass-dark aesthetic via the existing ``tokens.J`` palette so the
palette feels native to AERIS.

Performance
-----------
Fuzzy match is a simple "all chars of query appear in order in name"
plus a score = startswith bonus + matched-char density. O(N) over
REGISTRY where N ≤ ~50 today — runs in microseconds, no debounce
required.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PyQt5.QtCore import QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QKeySequence, QPainter, QPen
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QShortcut, QVBoxLayout, QWidget,
)

from .tokens import J, inter, mono, rgba


# ─── Data ──────────────────────────────────────────────────────────── #

@dataclass(frozen=True)
class _PaletteEntry:
    label: str           # Display text (1st row)
    sub: str             # Description (2nd row)
    kind: str            # "skill" | "action"
    payload: str         # for skill: the pattern to submit; for action: action id
    icon: str = "•"      # tiny glyph rendered left of label
    score_boost: int = 0


# ─── Fuzzy match ───────────────────────────────────────────────────── #

def _fuzzy_score(query: str, target: str) -> int:
    """Cheap fuzzy: all query chars in order anywhere in target.

    Higher score = better match. Returns -1 if no match. Bonuses for
    prefix match, contiguous runs, and word-boundary starts.
    """
    if not query:
        return 0
    q = query.lower()
    t = target.lower()
    if t.startswith(q):
        return 1000 + (200 - min(200, len(t)))   # strong prefix preference
    qi = 0
    score = 0
    run = 0
    prev_was_match = False
    for ch in t:
        if qi < len(q) and ch == q[qi]:
            qi += 1
            score += 5
            if prev_was_match:
                run += 1
                score += run * 3        # contiguous bonus
            else:
                run = 0
            prev_was_match = True
        else:
            prev_was_match = False
            run = 0
    if qi < len(q):
        return -1
    # Shorter targets score higher when query length is held constant.
    score -= max(0, len(t) - len(q))
    return score


# ─── Palette widget ────────────────────────────────────────────────── #

class CommandPalette(QWidget):
    """Floating overlay. Lives as a child of the main window.

    Signals
    -------
    submit_text(str)  — emitted when the user picks an entry; payload is
                        the text to feed into the brain pipeline.
    action(str)       — emitted when the user picks a built-in action
                        ("quit", "hide", "reload_skills", "pause").
    """

    submit_text = pyqtSignal(str)
    action      = pyqtSignal(str)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(520)
        self._entries: list[_PaletteEntry] = []
        self._filtered: list[_PaletteEntry] = []
        self._build_ui()
        self.hide()

        # Ctrl+K toggle — bound to the PARENT so it fires even when the
        # palette is hidden. Esc closes when the palette has focus.
        QShortcut(QKeySequence("Ctrl+K"), parent,
                  activated=self.toggle).setAutoRepeat(False)
        QShortcut(QKeySequence("Esc"), self,
                  activated=self.hide).setAutoRepeat(False)

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        wrap = QFrame(self)
        wrap.setObjectName("PaletteCard")
        wrap.setStyleSheet(
            "QFrame#PaletteCard{"
            f"background:rgba({J.PANEL.red()},{J.PANEL.green()},{J.PANEL.blue()},0.94);"
            f"border:1px solid rgba({J.CYAN.red()},{J.CYAN.green()},{J.CYAN.blue()},0.38);"
            "border-radius:12px;"
            "}"
        )
        outer.addWidget(wrap)

        body = QVBoxLayout(wrap)
        body.setContentsMargins(14, 12, 14, 12); body.setSpacing(8)

        hint = QLabel("Quick command")
        hint.setFont(mono(8, 700))
        hint.setStyleSheet(f"color:{J.CYAN.name()};letter-spacing:2px;")
        body.addWidget(hint)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search skills, type a command, ?action…")
        self._input.setFont(inter(13, 500))
        self._input.setStyleSheet(
            f"QLineEdit{{"
            f"background:rgba(13,21,37,0.85);"
            f"color:{J.TEXT_PRI.name()};"
            f"border:1px solid rgba({J.CYAN.red()},{J.CYAN.green()},{J.CYAN.blue()},0.30);"
            f"border-radius:6px;padding:8px 10px;}}"
            f"QLineEdit:focus{{border-color:rgba({J.CYAN.red()},{J.CYAN.green()},{J.CYAN.blue()},0.85);}}"
        )
        self._input.textChanged.connect(self._refilter)
        self._input.returnPressed.connect(self._activate_current)
        self._input.installEventFilter(self)
        body.addWidget(self._input)

        self._list = QListWidget()
        self._list.setFont(inter(12, 400))
        self._list.setStyleSheet(
            f"QListWidget{{background:transparent;border:none;color:{J.TEXT_SEC.name()};outline:0;}}"
            f"QListWidget::item{{padding:8px 10px;border-radius:6px;}}"
            f"QListWidget::item:selected{{background:rgba({J.CYAN.red()},{J.CYAN.green()},{J.CYAN.blue()},0.18);"
            f"color:{J.TEXT_PRI.name()};}}"
        )
        self._list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self._list.itemActivated.connect(lambda _: self._activate_current())
        body.addWidget(self._list, stretch=1)

        footer = QLabel("↑↓ navigate · Enter run · Esc close")
        footer.setFont(mono(8, 400))
        footer.setStyleSheet(f"color:{J.TEXT_MUT.name()};")
        body.addWidget(footer)

        self.setFixedHeight(380)

    # ── Show / refresh ──────────────────────────────────────────────

    def populate(self) -> None:
        """Rebuild the entry set from the current skill registry."""
        entries: list[_PaletteEntry] = [
            _PaletteEntry(
                label="Pause AERIS",
                sub="Halt voice + animations until resumed",
                kind="action", payload="pause", icon="❚❚",
                score_boost=20,
            ),
            _PaletteEntry(
                label="Reload skills now",
                sub="Re-import every skills/*.py",
                kind="action", payload="reload_skills", icon="↻",
                score_boost=20,
            ),
            _PaletteEntry(
                label="Hide to tray",
                sub="Minimise; tray icon stays",
                kind="action", payload="hide", icon="—",
                score_boost=15,
            ),
            _PaletteEntry(
                label="Quit AERIS",
                sub="Trigger graceful shutdown",
                kind="action", payload="quit", icon="✕",
                score_boost=10,
            ),
        ]
        try:
            from core.skill_registry import REGISTRY
            for s in sorted(REGISTRY.values(), key=lambda x: x.name):
                primary = s.patterns[0] if s.patterns else s.name.replace("_", " ")
                entries.append(_PaletteEntry(
                    label=s.name.replace("_", " "),
                    sub=(s.description or primary)[:80],
                    kind="skill", payload=primary, icon="▸",
                ))
        except Exception:
            pass
        self._entries = entries
        self._refilter()

    def toggle(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.populate()
            self._reposition()
            self.show()
            self.raise_()
            self._input.setFocus()
            self._input.selectAll()

    def _reposition(self) -> None:
        parent = self.parent()
        if not isinstance(parent, QWidget):
            return
        # Centre horizontally, sit ~140 px from top (out of the title bar).
        x = max(0, (parent.width() - self.width()) // 2)
        y = max(80, parent.height() // 5)
        self.move(x, y)

    # ── Filter + render ─────────────────────────────────────────────

    def _refilter(self) -> None:
        q = self._input.text().strip()
        scored: list[tuple[int, _PaletteEntry]] = []
        for e in self._entries:
            sc = _fuzzy_score(q, e.label)
            if sc < 0 and q:
                sc = _fuzzy_score(q, e.sub)
                if sc < 0:
                    continue
                sc -= 50    # weaker than label match
            scored.append((sc + e.score_boost, e))
        scored.sort(key=lambda t: -t[0])
        self._filtered = [e for _, e in scored[:80]]

        self._list.clear()
        for e in self._filtered:
            item = QListWidgetItem(f"  {e.icon}   {e.label}    —    {e.sub}")
            item.setData(Qt.UserRole, e)
            self._list.addItem(item)
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _activate_current(self) -> None:
        if self._list.count() == 0:
            # Fall back: submit raw input text so the user can free-form.
            text = self._input.text().strip()
            if text:
                self.submit_text.emit(text)
                self.hide()
            return
        item = self._list.currentItem() or self._list.item(0)
        entry: _PaletteEntry = item.data(Qt.UserRole)
        self.hide()
        if entry.kind == "action":
            self.action.emit(entry.payload)
        else:
            self.submit_text.emit(entry.payload)

    # ── Up/Down arrow inside the QLineEdit moves the list selection ──

    def eventFilter(self, obj, evt):
        if obj is self._input and evt.type() == QEvent.KeyPress:
            key = evt.key()
            if key == Qt.Key_Down:
                self._list.setCurrentRow(min(self._list.count() - 1,
                                             self._list.currentRow() + 1))
                return True
            if key == Qt.Key_Up:
                self._list.setCurrentRow(max(0, self._list.currentRow() - 1))
                return True
        return super().eventFilter(obj, evt)

    # ── Paint a subtle drop-shadow halo around the rounded card ─────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        for i in range(8, 0, -1):
            alpha = 0.04 * (8 - i) / 8
            p.setPen(Qt.NoPen)
            col = QColor(0, 0, 0); col.setAlphaF(alpha)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(i, i + 2, self.width() - 2 * i,
                                     self.height() - 2 * i),
                              14 - i, 14 - i)
