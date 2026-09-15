"""Content pages — Home / Automations / Brain / Memory / System / Settings.

Native ports of the ``jv5-page-*.jsx`` screens. Each page is a scrollable
column of cards. Data sources are wired to the *real* backend where it's cheap
and safe (psutil for system, ``core.automation`` for routines, the brain's
classifier stats, ``core.semantic_memory`` for recall) and lazily imported
inside refresh methods wrapped in try/except so a missing dependency degrades
to a placeholder line rather than crashing the GUI.

``build_page(key, window)`` is the factory the app shell calls.
"""
from __future__ import annotations

import os

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from ui.aeris_v6.tokens import (
    J, W_BOLD, W_SEMIBOLD, col, font_mono, font_ui, rgba_str,
)
from ui.aeris_v6.widgets import Card, JLabel, StatTile, hline


# ── shared page chrome ─────────────────────────────────────────────────
class _Page(QScrollArea):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        host = QWidget(); host.setStyleSheet(f"background:{rgba_str('bg',1)};")
        self.setWidget(host)
        self._root = QVBoxLayout(host)
        self._root.setContentsMargins(34, 28, 34, 28)
        self._root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(4)
        t = QLabel(title); t.setFont(font_ui(22, W_BOLD, 0.4))
        t.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
        s = QLabel(subtitle); s.setFont(font_mono(10))
        s.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        head.addWidget(t); head.addWidget(s)
        self._root.addLayout(head)

    def body(self) -> QVBoxLayout:
        return self._root

    def add_stretch(self):
        self._root.addStretch(1)


# ── HOME ────────────────────────────────────────────────────────────────
class HomePage(_Page):
    def __init__(self, window, parent=None):
        super().__init__("Welcome back, Shivang", "Your assistant at a glance", parent)
        self._win = window

        clock_card = Card(accent="cyan")
        self._clock = QLabel("--:--:--"); self._clock.setFont(font_mono(40, W_BOLD))
        self._clock.setStyleSheet(f"color:{rgba_str('cyan',1)};background:transparent;")
        self._date = QLabel(""); self._date.setFont(font_ui(12))
        self._date.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        clock_card.body().addWidget(self._clock)
        clock_card.body().addWidget(self._date)
        self.body().addWidget(clock_card)

        grid = QGridLayout(); grid.setSpacing(14)
        self._t_ram = StatTile("RAM (MB)", "—", "cyan")
        self._t_cpu = StatTile("CPU %", "—", "purple")
        self._t_bat = StatTile("BATTERY %", "—", "green")
        self._t_skills = StatTile("SKILLS", "—", "amber")
        for i, t in enumerate((self._t_ram, self._t_cpu, self._t_bat, self._t_skills)):
            grid.addWidget(t, 0, i)
        self.body().addLayout(grid)
        self.add_stretch()

        self._timer = QTimer(self); self._timer.timeout.connect(self.refresh)
        self._timer.start(1500); self.refresh()

    def refresh(self):
        import time as _t
        self._clock.setText(_t.strftime("%H:%M:%S"))
        self._date.setText(_t.strftime("%A · %d %B %Y"))
        try:
            import psutil
            vm = psutil.virtual_memory()
            self._t_ram.set_value(f"{vm.used // (1024*1024)}")
            self._t_cpu.set_value(f"{psutil.cpu_percent():.0f}")
            bat = psutil.sensors_battery()
            self._t_bat.set_value(f"{int(bat.percent)}" if bat else "AC")
        except Exception:
            pass
        try:
            from core.skill_registry import all_skills
            self._t_skills.set_value(str(len(all_skills())))
        except Exception:
            pass


# ── SYSTEM ───────────────────────────────────────────────────────────────
class SystemPage(_Page):
    def __init__(self, window, parent=None):
        super().__init__("System", "Live machine telemetry", parent)
        grid = QGridLayout(); grid.setSpacing(14)
        self._cpu = StatTile("CPU %", "—", "magenta")
        self._ram = StatTile("RAM USED %", "—", "cyan")
        self._disk = StatTile("DISK %", "—", "purple")
        self._procs = StatTile("PROCESSES", "—", "amber")
        for i, t in enumerate((self._cpu, self._ram, self._disk, self._procs)):
            grid.addWidget(t, 0, i)
        self.body().addLayout(grid)

        self._detail = Card()
        self._detail.body().addWidget(JLabel("Detail", "textMut"))
        self._lines = QLabel("Collecting…"); self._lines.setFont(font_mono(10))
        self._lines.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        self._lines.setWordWrap(True)
        self._detail.body().addWidget(self._lines)
        self.body().addWidget(self._detail)
        self.add_stretch()

        self._timer = QTimer(self); self._timer.timeout.connect(self.refresh)
        self._timer.start(2000); self.refresh()

    def refresh(self):
        try:
            import psutil
            self._cpu.set_value(f"{psutil.cpu_percent():.0f}")
            self._ram.set_value(f"{psutil.virtual_memory().percent:.0f}")
            self._disk.set_value(f"{psutil.disk_usage(os.path.expanduser('~')).percent:.0f}")
            self._procs.set_value(str(len(psutil.pids())))
            freq = psutil.cpu_freq()
            cores = psutil.cpu_count(logical=True)
            self._lines.setText(
                f"Cores: {cores}    Freq: {freq.current:.0f} MHz\n"
                f"Boot: {self._uptime()}    Platform: {os.name}"
            )
        except Exception as e:
            self._lines.setText(f"psutil unavailable: {e}")

    @staticmethod
    def _uptime():
        try:
            import psutil, time as _t
            secs = int(_t.time() - psutil.boot_time())
            h, m = divmod(secs // 60, 60)
            return f"{h}h {m}m ago"
        except Exception:
            return "—"


# ── AUTOMATIONS ───────────────────────────────────────────────────────────
class AutomationsPage(_Page):
    def __init__(self, window, parent=None):
        super().__init__("Automations", "Routines, triggers & pipelines", parent)
        self._list = QVBoxLayout(); self._list.setSpacing(10)
        self.body().addLayout(self._list)
        self.add_stretch()
        self.refresh()

    def refresh(self):
        while self._list.count():
            it = self._list.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        rows = []  # list of (name, dict)
        try:
            from core.automation import get_engine
            for rt in get_engine().list_routines():
                d = rt.to_dict() if hasattr(rt, "to_dict") else {}
                rows.append((getattr(rt, "name", d.get("name", "routine")), d))
        except Exception:
            # Fall back to reading the seed file directly.
            try:
                import json
                root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                raw = json.load(open(os.path.join(root, "data", "routines.json"), encoding="utf-8"))
                for k, v in raw.items():
                    if not k.startswith("_") and isinstance(v, dict):
                        rows.append((v.get("name", k), v))
            except Exception:
                rows = []
        if not rows:
            self._list.addWidget(self._empty("No routines found (data/routines.json)."))
            return
        for name, r in rows[:12]:
            self._list.addWidget(self._routine_card(str(name), r))

    def _routine_card(self, name, r):
        card = Card(pad=14)
        row = QHBoxLayout()
        nm = QLabel(name.replace("_", " ").title()); nm.setFont(font_ui(13, W_SEMIBOLD))
        nm.setStyleSheet(f"color:{rgba_str('textPri',1)};background:transparent;")
        row.addWidget(nm); row.addStretch(1)
        enabled = r.get("enabled", False)
        pill_key = "green" if enabled else "textMut"
        pill = QLabel("ENABLED" if enabled else "OFF"); pill.setFont(font_mono(8, W_BOLD, 1))
        pill.setStyleSheet(
            f"color:{rgba_str(pill_key,1)};background:{rgba_str(pill_key,0.1)};"
            f"border:1px solid {rgba_str(pill_key,0.3)};border-radius:5px;padding:2px 7px;")
        row.addWidget(pill)
        card.body().addLayout(row)
        desc = QLabel(r.get("description", "")); desc.setFont(font_mono(9))
        desc.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        desc.setWordWrap(True)
        card.body().addWidget(desc)
        return card

    def _empty(self, text):
        c = Card(); l = QLabel(text); l.setFont(font_mono(10))
        l.setStyleSheet(f"color:{rgba_str('textMut',1)};background:transparent;")
        c.body().addWidget(l); return c


# ── BRAIN ────────────────────────────────────────────────────────────────
class BrainPage(_Page):
    def __init__(self, window, parent=None):
        super().__init__("Brain", "Neural intent core", parent)
        self._win = window
        grid = QGridLayout(); grid.setSpacing(14)
        self._intents = StatTile("INTENT CLASSES", "—", "cyan")
        self._patterns = StatTile("PATTERNS", "—", "purple")
        self._skills = StatTile("SKILLS", "—", "green")
        for i, t in enumerate((self._intents, self._patterns, self._skills)):
            grid.addWidget(t, 0, i)
        self.body().addLayout(grid)

        info = Card()
        info.body().addWidget(JLabel("Stack", "textMut"))
        txt = QLabel(
            "• Encoder: paraphrase-multilingual-MiniLM-L12-v2\n"
            "• Classifier: sklearn k-NN over sentence embeddings\n"
            "• Entities: regex + gazetteer + spaCy en_core_web_sm\n"
            "• Sentiment: VADER + Hinglish lexicon\n"
            "• Agentic ReAct orchestrator over all skills")
        txt.setFont(font_mono(10)); txt.setWordWrap(True)
        txt.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        info.body().addWidget(txt)
        self.body().addWidget(info)
        self.add_stretch()
        QTimer.singleShot(200, self.refresh)

    def refresh(self):
        try:
            from core.skill_registry import all_skills, patterns_as_intent_dict
            sk = all_skills()
            self._skills.set_value(str(len(sk)))
            pats = patterns_as_intent_dict()
            self._intents.set_value(str(len(pats)))
            self._patterns.set_value(str(sum(len(v.get("patterns", [])) for v in pats.values())))
        except Exception:
            pass


# ── MEMORY ───────────────────────────────────────────────────────────────
class MemoryPage(_Page):
    def __init__(self, window, parent=None):
        super().__init__("Memory", "Facts, context & semantic recall", parent)
        facts = Card()
        facts.body().addWidget(JLabel("Known facts", "textMut"))
        self._facts = QLabel("Loading…"); self._facts.setFont(font_mono(10))
        self._facts.setWordWrap(True)
        self._facts.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        facts.body().addWidget(self._facts)
        self.body().addWidget(facts)

        sem = Card(accent="purple")
        sem.body().addWidget(JLabel("Semantic memory", "purple"))
        self._sem = QLabel("—"); self._sem.setFont(font_mono(10))
        self._sem.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        sem.body().addWidget(self._sem)
        self.body().addWidget(sem)
        self.add_stretch()
        QTimer.singleShot(250, self.refresh)

    def refresh(self):
        try:
            import json
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            mem = json.load(open(os.path.join(root, "data", "user_memory.json"), encoding="utf-8"))
            lines = "\n".join(f"• {k.replace('_',' ')}: {v}" for k, v in list(mem.items())[:12])
            self._facts.setText(lines or "(none yet)")
        except Exception:
            self._facts.setText("(memory store not found)")
        try:
            import numpy as np
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            npz = os.path.join(root, "data", "semantic_memory.npz")
            if os.path.exists(npz):
                d = np.load(npz, allow_pickle=True)
                n = len(d[d.files[0]]) if d.files else 0
                self._sem.setText(f"{n} recorded turns · cosine recall ready")
            else:
                self._sem.setText("no semantic store yet")
        except Exception:
            self._sem.setText("semantic memory unavailable")


# ── SETTINGS ──────────────────────────────────────────────────────────────
class SettingsPage(_Page):
    def __init__(self, window, parent=None):
        super().__init__("Settings", "Preferences & configuration", parent)
        card = Card()
        card.body().addWidget(JLabel("Configuration", "textMut"))
        self._txt = QLabel("Loading settings…"); self._txt.setFont(font_mono(10))
        self._txt.setWordWrap(True)
        self._txt.setStyleSheet(f"color:{rgba_str('textSec',1)};background:transparent;")
        card.body().addWidget(self._txt)
        self.body().addWidget(card)
        self.add_stretch()
        QTimer.singleShot(250, self.refresh)

    def refresh(self):
        try:
            import json
            root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            s = json.load(open(os.path.join(root, "data", "settings.json"), encoding="utf-8"))
            lines = "\n".join(f"• {k}: {v}" for k, v in list(s.items())[:18])
            self._txt.setText(lines or "(empty)")
        except Exception as e:
            self._txt.setText(f"settings.json not readable: {e}")


# ── factory ─────────────────────────────────────────────────────────────
_PAGES = {
    "home": HomePage,
    "system": SystemPage,
    "auto": AutomationsPage,
    "brain": BrainPage,
    "memory": MemoryPage,
    "settings": SettingsPage,
}


def build_page(key: str, window) -> QWidget:
    cls = _PAGES.get(key)
    if cls is None:
        raise KeyError(key)
    return cls(window)
