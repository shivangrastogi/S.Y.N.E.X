"""JARVIS v3.1 — right-panel tab pages.

One glass panel per dock tab. Each is 390px wide and uses the same
translucent-dark design language as GlassChatPanel. Backend wiring
is not implemented — these are complete UI shells.

Tabs: home · chat · auto · brain · memory · system · settings
"""
from __future__ import annotations

import math
import platform
import sys
import time

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPen,
)
from PyQt5.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from .tokens import J, inter, mono, rgba


# ─── Shared primitives ────────────────────────────────────────── #

class _GlassPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(390)

    def paintEvent(self, _):
        p = QPainter(self)
        bg = QColor(J.PANEL); bg.setAlphaF(0.75)
        p.fillRect(self.rect(), bg)
        p.setPen(QPen(rgba(J.BORDER, 0.6), 1))
        p.drawLine(0, 0, 0, self.height())
        p.setPen(QPen(rgba(J.CYAN, 0.06), 1))
        p.drawLine(1, 0, 1, self.height())


class _PanelHeader(QFrame):
    def __init__(self, title: str, sub: str, color: QColor, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self._color = color
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 16, 0); lay.setSpacing(8)
        left = QVBoxLayout(); left.setSpacing(2)
        t = QLabel(title); t.setFont(inter(11, 700))
        t.setStyleSheet(f"color:{J.TEXT_PRI.name()};letter-spacing:2px;")
        s = QLabel(sub); s.setFont(mono(10, 400))
        s.setStyleSheet(f"color:{J.TEXT_MUT.name()};")
        left.addWidget(t); left.addWidget(s)
        lay.addLayout(left); lay.addStretch(1)
        lay.addWidget(_BlinkDot(color))

    def paintEvent(self, _):
        p = QPainter(self)
        bg = QColor(J.BG); bg.setAlphaF(0.4)
        p.fillRect(self.rect(), bg)
        p.setPen(QPen(rgba(J.BORDER, 0.7), 1))
        p.drawLine(0, self.height()-1, self.width(), self.height()-1)


class _BlinkDot(QWidget):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color; self._start = time.monotonic()
        self.setFixedSize(8, 8)
        t = QTimer(self); t.timeout.connect(self.update); t.start(60)

    def paintEvent(self, _):
        ph = (time.monotonic()-self._start)*2*math.pi/1.8
        a = 0.4+0.6*(0.5+0.5*math.sin(ph))
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(self._color, a*0.35)); p.drawEllipse(self.rect())
        p.setBrush(rgba(self._color, a)); p.drawEllipse(self.rect().adjusted(2,2,-2,-2))


def _scrollable(content: QWidget) -> QScrollArea:
    sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.NoFrame)
    sa.setStyleSheet(
        "QScrollArea{background:transparent;border:none;}"
        "QScrollBar:vertical{background:transparent;width:4px;}"
        "QScrollBar::handle:vertical{background:rgba(0,212,255,0.18);border-radius:2px;}"
        "QScrollBar::add-line,QScrollBar::sub-line{height:0;}"
    )
    content.setStyleSheet("background:transparent;")
    sa.setWidget(content); return sa


def _sec(text: str) -> QLabel:
    l = QLabel(text); l.setFont(mono(9, 700))
    l.setStyleSheet(f"color:{J.TEXT_MUT.name()};letter-spacing:1.5px;")
    return l


def _divider() -> QWidget:
    w = QWidget(); w.setFixedHeight(1)
    w.setStyleSheet(f"background:rgba({J.BORDER.red()},{J.BORDER.green()},{J.BORDER.blue()},0.30);")
    return w


class _Card(QWidget):
    def __init__(self, color: QColor = None, parent=None):
        super().__init__(parent)
        self._color = color or J.BORDER

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        bg = QColor(J.BG_ELE); bg.setAlphaF(0.60)
        p.setPen(QPen(rgba(self._color, 0.22), 1))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0.5,0.5,self.width()-1,self.height()-1), 10, 10)


class _StatCard(QWidget):
    def __init__(self, value: str, label: str, color: QColor, parent=None):
        super().__init__(parent)
        self._color = color
        lay = QVBoxLayout(self); lay.setContentsMargins(12,10,12,10); lay.setSpacing(3)
        v = QLabel(value); v.setFont(inter(22, 700))
        v.setStyleSheet(f"color:{color.name()};"); v.setAlignment(Qt.AlignCenter)
        l = QLabel(label); l.setFont(mono(9, 400))
        l.setStyleSheet(f"color:{J.TEXT_MUT.name()};letter-spacing:0.4px;")
        l.setAlignment(Qt.AlignCenter); l.setWordWrap(True)
        lay.addWidget(v); lay.addWidget(l)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        bg = QColor(J.BG_ELE); bg.setAlphaF(0.55)
        p.setPen(QPen(rgba(self._color, 0.20), 1))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0.5,0.5,self.width()-1,self.height()-1), 10, 10)


class _StatusRow(QWidget):
    def __init__(self, label: str, status: str, ok: bool = True, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 4, 0, 4); lay.setSpacing(8)
        col = J.GREEN if ok else J.RED
        dot = QWidget(); dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"background:{col.name()};border-radius:3px;")
        lay.addWidget(dot, 0, Qt.AlignVCenter)
        lbl = QLabel(label); lbl.setFont(mono(10, 400))
        lbl.setStyleSheet(f"color:{J.TEXT_SEC.name()};")
        lay.addWidget(lbl, 1)
        st = QLabel(status); st.setFont(mono(9, 700))
        st.setStyleSheet(f"color:{col.name()};")
        lay.addWidget(st)


class _Toggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, on: bool = False, parent=None):
        super().__init__(parent)
        self._on = on
        self.setFixedSize(42, 24)
        self.setCursor(Qt.PointingHandCursor)
        t = QTimer(self); t.timeout.connect(self.update); t.start(16)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._on = not self._on; self.toggled.emit(self._on)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        track = J.CYAN if self._on else rgba(J.BORDER, 1.0)
        p.setBrush(rgba(track, 0.35 if self._on else 0.20))
        p.drawRoundedRect(QRectF(0, 5, 42, 14), 7, 7)
        cx = 32.0 if self._on else 10.0
        p.setBrush(J.CYAN if self._on else J.TEXT_MUT)
        p.drawEllipse(QPointF(cx, 12), 8, 8)


class _ToggleRow(QWidget):
    def __init__(self, label: str, sub: str, on: bool, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 4, 0, 4); lay.setSpacing(10)
        left = QVBoxLayout(); left.setSpacing(1)
        t = QLabel(label); t.setFont(inter(12, 500))
        t.setStyleSheet(f"color:{J.TEXT_PRI.name()};")
        left.addWidget(t)
        if sub:
            s = QLabel(sub); s.setFont(mono(9, 400))
            s.setStyleSheet(f"color:{J.TEXT_MUT.name()};")
            left.addWidget(s)
        lay.addLayout(left); lay.addStretch(1)
        lay.addWidget(_Toggle(on))


# ─── Home panel ───────────────────────────────────────────────── #

class HomePanel(_GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(_PanelHeader("JARVIS HOME", "Dashboard · welcome back", J.CYAN))

        inner = QWidget()
        lay = QVBoxLayout(inner); lay.setContentsMargins(16,18,16,18); lay.setSpacing(16)

        lay.addWidget(_sec("QUICK STATS"))
        grid = QGridLayout(); grid.setSpacing(8)
        for i, (v, l, c) in enumerate([
            ("0",    "Commands\nToday",  J.CYAN),
            ("0",    "Memory\nFacts",    J.PURPLE),
            ("100%", "Brain\nHealth",    J.GREEN),
            ("0:00", "Session\nUptime",  J.AMBER),
        ]):
            grid.addWidget(_StatCard(v, l, c), i//2, i%2)
        lay.addLayout(grid)

        lay.addWidget(_divider())
        lay.addWidget(_sec("QUICK ACTIONS"))
        for label, hint in (
            ("Open Chrome",    "automation"),
            ("Check Weather",  "skill"),
            ("System Stats",   "system"),
            ("Play Music",     "automation"),
        ):
            rw = QWidget()
            rl = QHBoxLayout(rw); rl.setContentsMargins(0, 3, 0, 3)
            n = QLabel(label); n.setFont(inter(12, 500))
            n.setStyleSheet(f"color:{J.TEXT_PRI.name()};")
            rl.addWidget(n); rl.addStretch(1)
            h = QLabel(hint); h.setFont(mono(9, 400))
            h.setStyleSheet(f"color:{J.TEXT_MUT.name()};")
            rl.addWidget(h)
            lay.addWidget(rw)

        lay.addWidget(_divider())
        lay.addWidget(_sec("RECENT COMMANDS"))
        e = QLabel("No commands yet this session.")
        e.setFont(mono(10, 400))
        e.setStyleSheet(f"color:{J.TEXT_MUT.name()};")
        e.setAlignment(Qt.AlignCenter)
        lay.addWidget(e)
        lay.addStretch(1)
        root.addWidget(_scrollable(inner), 1)


# ─── Brain panel ──────────────────────────────────────────────── #

class BrainPanel(_GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(_PanelHeader("NEURAL BRAIN", "Intent engine · model info", J.MAGENTA))

        inner = QWidget()
        lay = QVBoxLayout(inner); lay.setContentsMargins(16,18,16,18); lay.setSpacing(16)

        lay.addWidget(_sec("MODEL STACK"))
        card = _Card(J.MAGENTA)
        cl = QVBoxLayout(card); cl.setContentsMargins(14,12,14,12); cl.setSpacing(7)
        for k, v in (
            ("Encoder",    "paraphrase-multilingual-MiniLM-L12-v2"),
            ("Classifier", "NearestNeighbors · cosine · k=5"),
            ("Voting",     "exp-weighted · temperature=10"),
            ("Cache",      "data/models/intent_index.pkl"),
            ("Intents",    "21 classes · ~14 Hinglish patterns each"),
        ):
            rw = QHBoxLayout(); rw.setSpacing(8)
            kl = QLabel(k); kl.setFont(mono(9, 700))
            kl.setStyleSheet(f"color:{J.MAGENTA.name()};"); kl.setFixedWidth(72)
            vl = QLabel(v); vl.setFont(mono(9, 400))
            vl.setStyleSheet(f"color:{J.TEXT_SEC.name()};"); vl.setWordWrap(True)
            rw.addWidget(kl); rw.addWidget(vl, 1)
            cl.addLayout(rw)
        lay.addWidget(card)

        lay.addWidget(_divider())
        lay.addWidget(_sec("ACTIVE INTENTS  ·  21"))
        for intent in ("greet", "farewell", "weather_check", "open_app",
                       "play_music", "system_stats", "time_query", "chit_chat",
                       "set_timer", "take_note", "recall_fact", "+ 10 more"):
            rw = QHBoxLayout(); rw.setContentsMargins(0, 2, 0, 2)
            n = QLabel(intent); n.setFont(mono(10, 400))
            n.setStyleSheet(f"color:{J.TEXT_SEC.name()};")
            rw.addWidget(n); rw.addStretch(1)
            col = J.TEXT_MUT if intent.startswith("+") else J.GREEN
            b = QLabel("—" if intent.startswith("+") else "ACTIVE"); b.setFont(mono(8, 700))
            b.setStyleSheet(f"color:{col.name()};")
            rw.addWidget(b)
            lay.addLayout(rw)

        lay.addStretch(1)
        root.addWidget(_scrollable(inner), 1)


# ─── Memory panel ─────────────────────────────────────────────── #

class MemoryPanel(_GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(_PanelHeader("USER MEMORY", "Persistent facts · learned data", J.PURPLE))

        inner = QWidget()
        lay = QVBoxLayout(inner); lay.setContentsMargins(16,18,16,18); lay.setSpacing(16)

        grid = QGridLayout(); grid.setSpacing(8)
        for i, (v, l, c) in enumerate([
            ("0", "Total Facts",  J.PURPLE),
            ("0", "Categories",   J.CYAN),
        ]):
            grid.addWidget(_StatCard(v, l, c), 0, i)
        lay.addLayout(grid)

        lay.addWidget(_divider())
        lay.addWidget(_sec("STORED FACTS"))

        card = _Card(J.PURPLE)
        ecl = QVBoxLayout(card); ecl.setContentsMargins(14, 24, 14, 24); ecl.setSpacing(10)
        icon = QLabel("◈"); icon.setFont(inter(30, 700))
        icon.setStyleSheet(f"color:{J.PURPLE.name()};")
        icon.setAlignment(Qt.AlignCenter)
        ecl.addWidget(icon)
        msg = QLabel("No facts stored yet.\nTell me something —\ne.g. \"My name is Shivang\"")
        msg.setFont(mono(10, 400)); msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet(f"color:{J.TEXT_MUT.name()};"); msg.setWordWrap(True)
        ecl.addWidget(msg)
        lay.addWidget(card)

        lay.addWidget(_divider())
        lay.addWidget(_sec("HOW IT WORKS"))
        for tip in (
            "Say facts naturally in conversation",
            "\"My name is…\" · \"I prefer…\" · \"I work at…\"",
            "Jarvis remembers across sessions",
            "Ask \"what do you know about me?\"",
        ):
            tl = QLabel(f"  {tip}"); tl.setFont(mono(9, 400))
            tl.setStyleSheet(f"color:{J.TEXT_MUT.name()};")
            lay.addWidget(tl)

        lay.addStretch(1)
        root.addWidget(_scrollable(inner), 1)


# ─── System panel ─────────────────────────────────────────────── #

class SystemPanel(_GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(_PanelHeader("SYSTEM STATUS", "Runtime · module health", J.GREEN))

        inner = QWidget()
        lay = QVBoxLayout(inner); lay.setContentsMargins(16,18,16,18); lay.setSpacing(16)

        lay.addWidget(_sec("RUNTIME"))
        card = _Card(J.GREEN)
        cl = QVBoxLayout(card); cl.setContentsMargins(14,12,14,12); cl.setSpacing(7)
        try:
            pv = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        except Exception:
            pv = "?"
        for k, v in (
            ("OS",      platform.system() + " " + platform.release()),
            ("Python",  pv),
            ("Arch",    platform.machine()),
            ("Build",   "JARVIS v3.1 · 2025"),
        ):
            rw = QHBoxLayout(); rw.setSpacing(8)
            kl = QLabel(k); kl.setFont(mono(9, 700))
            kl.setStyleSheet(f"color:{J.GREEN.name()};"); kl.setFixedWidth(52)
            vl = QLabel(v); vl.setFont(mono(9, 400))
            vl.setStyleSheet(f"color:{J.TEXT_SEC.name()};")
            rw.addWidget(kl); rw.addWidget(vl, 1)
            cl.addLayout(rw)
        lay.addWidget(card)

        lay.addWidget(_divider())
        lay.addWidget(_sec("MODULE STATUS"))
        for label, status, ok in (
            ("NLU Brain",     "online",   True),
            ("Edge TTS",      "online",   True),
            ("Google STT",    "online",   True),
            ("Vosk Fallback", "standby",  True),
            ("Ollama LLM",    "offline",  False),
            ("Memory DB",     "online",   True),
            ("Feedback Log",  "online",   True),
            ("Entity NER",    "online",   True),
        ):
            lay.addWidget(_StatusRow(label, status, ok))

        lay.addStretch(1)
        root.addWidget(_scrollable(inner), 1)


# ─── Settings panel ───────────────────────────────────────────── #

class SettingsPanel(_GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(_PanelHeader("SETTINGS", "Preferences · configuration", J.AMBER))

        inner = QWidget()
        lay = QVBoxLayout(inner); lay.setContentsMargins(16,18,16,18); lay.setSpacing(14)

        lay.addWidget(_sec("VOICE"))
        for lbl, sub, on in (
            ("Speech-to-Text",  "Google STT · en-IN + Vosk fallback",  True),
            ("Text-to-Speech",  "Edge-TTS Neerja · pyttsx3 fallback",  True),
            ("Wake Word",       "Say 'Jarvis' to activate mic",         False),
            ("Auto Sleep",      "Pauses mic after 30 s silence",        True),
        ):
            lay.addWidget(_ToggleRow(lbl, sub, on))

        lay.addWidget(_divider())
        lay.addWidget(_sec("INTELLIGENCE"))
        for lbl, sub, on in (
            ("Hinglish Mode",    "Mixed Hindi + English input",          True),
            ("LLM Fallback",     "Ollama chit-chat for unknown intents", False),
            ("Feedback Learn",   "Improve thresholds from corrections",  True),
            ("Disambiguate",     "Ask when top intents are close",       True),
        ):
            lay.addWidget(_ToggleRow(lbl, sub, on))

        lay.addWidget(_divider())
        lay.addWidget(_sec("INTERFACE"))
        for lbl, sub, on in (
            ("Debug Logs",    "Show verbose logs bar at bottom",  True),
            ("Animations",    "Particle field + reactor rings",   True),
            ("Sound FX",      "UI sounds (coming soon)",          False),
        ):
            lay.addWidget(_ToggleRow(lbl, sub, on))

        lay.addWidget(_divider())
        lay.addWidget(_sec("ABOUT"))
        for line in (
            "JARVIS v3.1  ·  build 2025",
            "Powered by sentence-transformers + Qt5",
            "Hinglish-native · fully local",
        ):
            l = QLabel(line); l.setFont(mono(9, 400))
            l.setStyleSheet(f"color:{J.TEXT_MUT.name()};")
            lay.addWidget(l)

        lay.addStretch(1)
        root.addWidget(_scrollable(inner), 1)


# ─── Right-panel stack ────────────────────────────────────────── #

_TAB_INDEX = {
    "home":     0,
    "chat":     1,
    "auto":     1,   # automation chips shown inside GlassChatPanel
    "brain":    2,
    "memory":   3,
    "system":   4,
    "settings": 5,
}


class RightPanelStack(QWidget):
    """Hosts all tab panels; exposes `chat_panel` and `switch_tab(key)`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(390)

        from .glass_chat_panel import GlassChatPanel
        self.chat_panel = GlassChatPanel()

        self._stack = QStackedWidget(self)
        self._stack.setFixedWidth(390)
        self._stack.addWidget(HomePanel())         # 0
        self._stack.addWidget(self.chat_panel)     # 1
        self._stack.addWidget(BrainPanel())        # 2
        self._stack.addWidget(MemoryPanel())       # 3
        self._stack.addWidget(SystemPanel())       # 4
        self._stack.addWidget(SettingsPanel())     # 5
        self._stack.setCurrentIndex(1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        lay.addWidget(self._stack)

    def switch_tab(self, key: str) -> None:
        self._stack.setCurrentIndex(_TAB_INDEX.get(key, 1))
        self.chat_panel.set_automation_visible(key == "auto")
