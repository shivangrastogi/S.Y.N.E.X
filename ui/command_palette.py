"""Command palette — Spotlight-style fuzzy launcher for every skill.

Pops up over the current desktop. Type a few characters, see ranked
matches, press Enter to fire the selected skill. The brain pipeline is
bypassed for speed; the palette calls the skill handler directly.

Backed by a tiny fuzzy-match scorer that walks the registered skills
once per keystroke — fine for ~200 skills.

Public entry points:
    open_command_palette()             — show the modal palette
    fuzzy_rank(query, skills) -> list  — pure helper, easily testable
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

log = logging.getLogger(__name__)


# ── pure helpers (used by tests + the dialog) ─────────────────────


def _score(query: str, name: str, patterns: list[str]) -> float:
    """Return a fuzzy score in [0, 1+] — higher is a better match.

    Scoring tiers:
      1.0  — query is a prefix of the skill name
      0.9  — query exactly matches one of the patterns
      0.8  — query is a substring of the skill name
      0.7  — every query token appears in name or first pattern
      0.5  — every query character appears in order somewhere in name
      0.0  — no match
    """
    if not query:
        return 0.0
    q = query.strip().lower()
    n = (name or "").lower()
    if not q:
        return 0.0
    if n.startswith(q):
        return 1.0
    pat_lo = [p.lower() for p in (patterns or [])]
    if any(p == q for p in pat_lo):
        return 0.9
    if q in n:
        return 0.8
    tokens = [t for t in re.split(r"[\s_\-]+", q) if t]
    if tokens:
        hay = n + " " + " ".join(pat_lo[:6])
        if all(t in hay for t in tokens):
            return 0.7
    # Subsequence — characters in order, not necessarily contiguous.
    i = 0
    for ch in n:
        if i < len(q) and ch == q[i]:
            i += 1
    if i == len(q):
        return 0.5
    return 0.0


def fuzzy_rank(query: str, skills_dict) -> list[tuple[str, float, str]]:
    """Rank the given ``{name: Skill}`` dict against ``query``.
    Returns a list of (name, score, first-pattern) tuples,
    sorted by score desc then alpha. Top 20 only."""
    results: list[tuple[str, float, str]] = []
    for name in sorted(skills_dict.keys()):
        sk = skills_dict[name]
        s = _score(query, name, list(getattr(sk, "patterns", []) or []))
        if s <= 0.0:
            continue
        first_pat = (sk.patterns[0] if getattr(sk, "patterns", None) else "")[:60]
        results.append((name, s, first_pat))
    results.sort(key=lambda t: (-t[1], t[0]))
    return results[:20]


# ── PyQt5 dialog (lazy imports, main-thread guard) ───────────────


def open_command_palette(parent=None) -> bool:
    """Show the modal command palette. Returns True if a skill was fired."""
    try:
        from PyQt5.QtWidgets import (
            QApplication, QDialog, QVBoxLayout, QLineEdit,
            QListWidget, QListWidgetItem, QShortcut,
        )
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QFont, QKeySequence
    except Exception as e:
        log.info("[command_palette] PyQt5 unavailable: %s", e)
        return False
    try:
        from core.skill_registry import all_skills
    except Exception as e:
        log.info("[command_palette] skill registry unavailable: %s", e)
        return False

    # Main-thread guard — same constraint as the other dialogs.
    app = QApplication.instance()
    spawned_app = False
    if app is None:
        import threading as _th
        if _th.current_thread() is not _th.main_thread():
            log.warning("[command_palette] cannot create QApplication off main thread.")
            return False
        try:
            import sys
            app = QApplication(sys.argv)
            spawned_app = True
        except Exception:
            return False

    skills = all_skills()
    dlg = QDialog(parent)
    dlg.setWindowFlags(dlg.windowFlags() | Qt.FramelessWindowHint)
    dlg.setWindowTitle("AERIS — Command Palette")
    dlg.resize(560, 360)
    root = QVBoxLayout(dlg)
    root.setContentsMargins(12, 12, 12, 12)

    edit = QLineEdit()
    edit.setPlaceholderText("Type a skill or command…")
    f = QFont(); f.setPointSize(13)
    edit.setFont(f)
    root.addWidget(edit)

    listw = QListWidget()
    listw.setFont(QFont("Consolas", 10))
    root.addWidget(listw)

    state = {"fired": False, "selected": None}

    def _refresh():
        listw.clear()
        q = edit.text().strip()
        if not q:
            for name in sorted(skills.keys())[:20]:
                sk = skills[name]
                desc = (sk.description or "")[:60]
                listw.addItem(QListWidgetItem(f"{name:30s}  {desc}"))
        else:
            for name, score, pat in fuzzy_rank(q, skills):
                listw.addItem(QListWidgetItem(f"{name:30s}  {score:.2f}  e.g. {pat!r}"))
        if listw.count() > 0:
            listw.setCurrentRow(0)

    def _fire():
        row = listw.currentRow()
        if row < 0:
            return
        item = listw.item(row).text()
        name = item.split()[0]
        sk = skills.get(name)
        if sk is None:
            return
        try:
            result = sk.run({"raw_text": edit.text().strip()})
            log.info("[command_palette] %s → %s", name, (result or "")[:80])
        except Exception as e:
            log.warning("[command_palette] %s raised: %s", name, e)
        state["fired"] = True
        state["selected"] = name
        dlg.accept()

    edit.textChanged.connect(lambda _t: _refresh())
    edit.returnPressed.connect(_fire)
    listw.itemActivated.connect(lambda _i: _fire())
    QShortcut(QKeySequence(Qt.Key_Escape), dlg, activated=dlg.reject)

    _refresh()
    edit.setFocus()
    try:
        dlg.exec_()
    finally:
        if spawned_app:
            try: app.quit()
            except Exception: pass

    return bool(state["fired"])
