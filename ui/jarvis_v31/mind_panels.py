"""MIND panels — Abilities / Intelligence / Continuity (2026-07 redesign).

Design rule (docs/GUI_CAPABILITY_AUDIT.md): these panels are PROJECTIONS
of the live mind — skill registry, brain_health, goal store, continuity
registry — never hand-listed feature snapshots. A capability added
tomorrow appears here at next boot with zero GUI edits; that is the fix
for "GUI shows broken/stale options".

Domain accents (semantic color, mirrored on the phone):
    Abilities   = ARC     (cyan)    — what I can do
    Intelligence= SYNAPSE (magenta) — how well I think
    Continuity  = ALIVE   (green)   — where I am
"""
from __future__ import annotations

import logging
import threading
import time

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from .tokens import J, inter, mono, rgba

log = logging.getLogger(__name__)


# House atoms live in tab_panels; imported lazily inside functions to dodge
# the circular import (tab_panels imports THIS module for the stack).

def _atoms():
    from . import tab_panels as t
    return t._GlassPanel, t._PanelHeader, t._scrollable


# ─────────────────────────────────────────────────────────────────────── #
#  ABILITIES — the living index (signature element)                       #
# ─────────────────────────────────────────────────────────────────────── #

def _pretty(name: str) -> str:
    return name.replace("_", " ")


def _domain_of_module(mod: str) -> str:
    """skills.phone_actions_skill → PHONE ACTIONS"""
    stem = mod.split(".")[-1]
    for suffix in ("_skill", "_skills"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem.replace("_", " ").upper() or "CORE"


def build_ability_index() -> dict[str, list[dict]]:
    """{domain: [{name, phrase, desc}]} — straight from the registry +
    legacy intents.json. Never hand-curated."""
    domains: dict[str, list[dict]] = {}
    try:
        from core.skill_registry import all_skills
        for name, sk in sorted(all_skills().items()):
            phrase = (sk.patterns[0] if sk.patterns else name.replace("_", " "))
            domains.setdefault(_domain_of_module(
                getattr(sk.handler, "__module__", "core")), []).append({
                    "name": name, "phrase": phrase,
                    "desc": sk.description or "",
                })
    except Exception as e:
        log.debug("[abilities] registry read failed: %s", e)
    try:
        import json
        import os
        root = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(root, "data", "intents.json"),
                  encoding="utf-8") as f:
            legacy = json.load(f)
        seen = {a["name"] for rows in domains.values() for a in rows}
        core_rows = [{"name": n, "phrase": (c.get("patterns") or [n])[0],
                      "desc": ""}
                     for n, c in sorted(legacy.items())
                     if n not in seen and c.get("patterns")]
        if core_rows:
            domains["CORE"] = core_rows
    except Exception as e:
        log.debug("[abilities] intents.json read failed: %s", e)

    # 120 one-skill module sections would be visual noise — clusters
    # smaller than 3 roll up into one OTHER SKILLS section (search still
    # finds everything).
    small = [k for k, v in domains.items() if len(v) < 5]
    if len(small) > 3:
        other: list[dict] = []
        for k in small:
            other.extend(domains.pop(k))
        other.sort(key=lambda a: a["name"])
        domains["OTHER SKILLS"] = other
    return domains


class _AbilityRow(QPushButton):
    """name + spoken phrase; click hands the phrase to the chat input."""

    def __init__(self, ability: dict, accent: QColor, on_use, parent=None):
        super().__init__(parent)
        self._ability = ability
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.clicked.connect(lambda: on_use(ability["phrase"]))
        self.setToolTip(ability["desc"] or "Click: phrase chat mein daalo")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 2, 10, 2)
        name = QLabel(_pretty(ability["name"]))
        name.setFont(inter(10, 600))
        name.setStyleSheet(f"color:{J.TEXT_PRI.name()};background:transparent;")
        shown = ability["phrase"]
        if len(shown) > 30:                     # 390px rail — no overflow
            shown = shown[:29] + "…"
        phrase = QLabel(f"「{shown}」")
        phrase.setFont(mono(8, 500))
        phrase.setStyleSheet(f"color:{J.TEXT_MUT.name()};background:transparent;")
        lay.addWidget(name)
        lay.addStretch(1)
        lay.addWidget(phrase)
        self.setStyleSheet(
            "QPushButton{background:transparent;border:none;"
            "border-radius:8px;text-align:left;}"
            f"QPushButton:hover{{background:{rgba(accent, 0.10).name(QColor.HexArgb)};}}")

    @property
    def search_blob(self) -> str:
        a = self._ability
        return f"{a['name']} {a['phrase']} {a['desc']}".lower()


class _DomainSection(QWidget):
    """Collapsible cluster: 'PHONE ACTIONS (7)' header + ability rows."""

    def __init__(self, title: str, abilities: list[dict], accent: QColor,
                 on_use, parent=None):
        super().__init__(parent)
        self._open = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._head = QPushButton(f"▸  {title}  ({len(abilities)})")
        self._head.setCursor(Qt.PointingHandCursor)
        self._head.setFixedHeight(34)
        self._head.setFont(mono(9, 700))
        self._head.setStyleSheet(
            f"QPushButton{{color:{accent.name()};background:transparent;"
            "border:none;text-align:left;padding-left:12px;}"
            f"QPushButton:hover{{background:{rgba(accent, 0.08).name(QColor.HexArgb)};}}")
        self._head.clicked.connect(self._toggle)
        lay.addWidget(self._head)

        self._body = QWidget()
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(0, 0, 0, 6)
        body_lay.setSpacing(1)
        self.rows: list[_AbilityRow] = []
        for a in abilities:
            row = _AbilityRow(a, accent, on_use)
            self.rows.append(row)
            body_lay.addWidget(row)
        self._body.setVisible(False)
        lay.addWidget(self._body)
        self._title = title

    def _toggle(self):
        self.set_open(not self._open)

    def set_open(self, open_: bool):
        self._open = open_
        self._body.setVisible(open_)
        arrow = "▾" if open_ else "▸"
        n = len(self.rows)
        self._head.setText(f"{arrow}  {self._title}  ({n})")

    def apply_filter(self, needle: str) -> int:
        """Show only matching rows; returns visible count."""
        if not needle:
            for r in self.rows:
                r.setVisible(True)
            self.set_open(False)
            self.setVisible(True)
            return len(self.rows)
        hits = 0
        for r in self.rows:
            ok = needle in r.search_blob
            r.setVisible(ok)
            hits += 1 if ok else 0
        self.setVisible(hits > 0)
        if hits:
            self.set_open(True)
        return hits


def make_abilities_panel():
    _GlassPanel, _PanelHeader, _scrollable = _atoms()

    class AbilitiesPanel(_GlassPanel):
        use_phrase = pyqtSignal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            self._header = _PanelHeader(
                "ABILITIES", "index ban raha hai…", J.CYAN)
            root.addWidget(self._header)

            self._search = QLineEdit()
            self._search.setPlaceholderText(
                "Search 300+ abilities…  (naam, phrase, kaam)")
            self._search.setFont(inter(10, 500))
            self._search.setFixedHeight(34)
            self._search.setStyleSheet(
                f"QLineEdit{{background:{J.BG_ELE.name()};"
                f"border:1px solid {J.BORDER.name()};border-radius:8px;"
                f"color:{J.TEXT_PRI.name()};padding:0 12px;margin:10px 14px 8px 14px;}}"
                f"QLineEdit:focus{{border-color:{J.CYAN.name()};}}")
            self._search.textChanged.connect(self._on_search)
            root.addWidget(self._search)

            self._count_lbl = QLabel("")
            self._count_lbl.setFont(mono(8, 600))
            self._count_lbl.setStyleSheet(
                f"color:{J.TEXT_MUT.name()};")
            self._count_lbl.setContentsMargins(16, 0, 16, 4)
            root.addWidget(self._count_lbl)

            self._list_host = QWidget()
            self._list_lay = QVBoxLayout(self._list_host)
            self._list_lay.setContentsMargins(4, 0, 4, 12)
            self._list_lay.setSpacing(0)
            self._list_lay.addStretch(1)
            root.addWidget(_scrollable(self._list_host), 1)

            self._sections: list[_DomainSection] = []
            self._built_count = -1
            # Registry fills as the engine boots — poll until it stabilises.
            self._build_timer = QTimer(self)
            self._build_timer.timeout.connect(self._maybe_build)
            self._build_timer.start(3000)
            QTimer.singleShot(400, self._maybe_build)

        # -- build ----------------------------------------------------- #

        def _maybe_build(self):
            index = build_ability_index()
            total = sum(len(v) for v in index.values())
            if total == self._built_count:
                if total > 300:
                    self._build_timer.stop()   # full registry seen — done
                elif total > 0:
                    self._build_timer.setInterval(30000)  # settle down
                return
            self._built_count = total
            while self._list_lay.count() > 1:
                item = self._list_lay.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            self._sections = []
            order = sorted(index.items(),
                           key=lambda kv: (-len(kv[1]), kv[0]))
            for title, abilities in order:
                sec = _DomainSection(title, abilities, J.CYAN,
                                     self.use_phrase.emit)
                self._sections.append(sec)
                self._list_lay.insertWidget(self._list_lay.count() - 1, sec)
            self._header.set_subtitle(
                f"{total} abilities · {len(order)} domains · "
                "live from the registry")
            self._count_lbl.setText(
                f"{total} ABILITIES · CLICK = PHRASE CHAT MEIN")
            self._on_search(self._search.text())

        def _on_search(self, text: str):
            needle = (text or "").strip().lower()
            shown = sum(s.apply_filter(needle) for s in self._sections)
            if needle:
                self._count_lbl.setText(
                    f"{shown} MATCH · CLICK = PHRASE CHAT MEIN")
            elif self._built_count > 0:
                self._count_lbl.setText(
                    f"{self._built_count} ABILITIES · "
                    "CLICK = PHRASE CHAT MEIN")

    return AbilitiesPanel


# ─────────────────────────────────────────────────────────────────────── #
#  INTELLIGENCE — brain health, lineage, retrain advisor                  #
# ─────────────────────────────────────────────────────────────────────── #

class _HealthDial(QWidget):
    """0-100 arc dial with a single sweep-in animation (house restraint)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(96, 96)
        self._target = 0
        self._shown = 0.0
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._step)

    def set_score(self, score) -> None:
        self._target = max(0, min(100, int(score or 0)))
        if not self._anim.isActive():
            self._anim.start(16)

    def _step(self):
        gap = self._target - self._shown
        if abs(gap) < 0.6:
            self._shown = float(self._target)
            self._anim.stop()
        else:
            self._shown += gap * 0.12
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(8, 8, -8, -8)
        base = QPen(rgba(J.BORDER, 0.9), 7)
        base.setCapStyle(Qt.RoundCap)
        p.setPen(base)
        p.drawArc(rect, 225 * 16, -270 * 16)
        frac = self._shown / 100.0
        color = (J.GREEN if self._shown >= 75 else
                 J.AMBER if self._shown >= 50 else J.RED)
        pen = QPen(color, 7)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 225 * 16, int(-270 * 16 * frac))
        p.setPen(QPen(J.TEXT_PRI))
        p.setFont(mono(18, 700))
        p.drawText(self.rect().adjusted(0, -4, 0, -4), Qt.AlignCenter,
                   f"{int(round(self._shown))}")
        p.setPen(QPen(J.TEXT_MUT))
        p.setFont(mono(7, 600))
        p.drawText(self.rect().adjusted(0, 30, 0, 0), Qt.AlignCenter,
                   "HEALTH")


def make_intelligence_panel():
    _GlassPanel, _PanelHeader, _scrollable = _atoms()

    class IntelligencePanel(_GlassPanel):
        def __init__(self, parent=None):
            super().__init__(parent)
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            root.addWidget(_PanelHeader(
                "INTELLIGENCE", "brain health · learning · lineage",
                J.MAGENTA))

            host = QWidget()
            lay = QVBoxLayout(host)
            lay.setContentsMargins(16, 12, 16, 14)
            lay.setSpacing(10)

            top = QHBoxLayout()
            self._dial = _HealthDial()
            top.addWidget(self._dial)
            self._stats = QLabel("collecting…")
            self._stats.setFont(mono(9, 500))
            self._stats.setStyleSheet(
                f"color:{J.TEXT_SEC.name()};background:transparent;")
            self._stats.setWordWrap(True)
            top.addWidget(self._stats, 1)
            lay.addLayout(top)

            self._retrain_card = QFrame()
            self._retrain_card.setStyleSheet(
                f"QFrame{{background:{rgba(J.AMBER, 0.08).name(QColor.HexArgb)};"
                f"border:1px solid {rgba(J.AMBER, 0.45).name(QColor.HexArgb)};"
                "border-radius:10px;}")
            card_lay = QVBoxLayout(self._retrain_card)
            card_lay.setContentsMargins(12, 10, 12, 10)
            card_lay.setSpacing(6)
            self._retrain_why = QLabel("RETRAIN DUE")
            self._retrain_why.setFont(mono(8, 700))
            self._retrain_why.setStyleSheet(
                f"color:{J.AMBER.name()};background:transparent;"
                "border:none;")
            self._retrain_why.setWordWrap(True)
            card_lay.addWidget(self._retrain_why)
            cmd_row = QHBoxLayout()
            cmd = QLabel("python -m core.retrain")
            cmd.setFont(mono(9, 600))
            cmd.setStyleSheet(f"color:{J.TEXT_PRI.name()};"
                              "background:transparent;border:none;")
            cmd_row.addWidget(cmd)
            cmd_row.addStretch(1)
            copy_btn = QPushButton("Copy command")
            copy_btn.setCursor(Qt.PointingHandCursor)
            copy_btn.setFont(inter(9, 600))
            copy_btn.setFixedHeight(26)
            copy_btn.setStyleSheet(
                f"QPushButton{{color:{J.BG.name()};background:{J.AMBER.name()};"
                "border:none;border-radius:6px;padding:0 12px;}"
                f"QPushButton:hover{{background:{J.TEXT_PRI.name()};}}")
            copy_btn.clicked.connect(self._copy_cmd)
            cmd_row.addWidget(copy_btn)
            card_lay.addLayout(cmd_row)
            note = QLabel("Training tum chalate ho — AERIS kabhi khud "
                          "nahi chalayega.")
            note.setFont(inter(8, 500))
            note.setStyleSheet(f"color:{J.TEXT_MUT.name()};"
                               "background:transparent;border:none;")
            card_lay.addWidget(note)
            self._retrain_card.setVisible(False)
            lay.addWidget(self._retrain_card)

            self._detail = QLabel("")
            self._detail.setFont(mono(8, 500))
            self._detail.setStyleSheet(
                f"color:{J.TEXT_MUT.name()};background:transparent;")
            self._detail.setWordWrap(True)
            lay.addWidget(self._detail)
            lay.addStretch(1)
            root.addWidget(_scrollable(host), 1)

            self._pending: dict | None = None
            self._apply_timer = QTimer(self)
            self._apply_timer.timeout.connect(self._apply_pending)
            self._apply_timer.start(700)
            self._collect_timer = QTimer(self)
            self._collect_timer.timeout.connect(self._collect_async)
            self._collect_timer.start(60000)
            QTimer.singleShot(2500, self._collect_async)

        def _copy_cmd(self):
            try:
                QApplication.clipboard().setText("python -m core.retrain")
            except Exception:
                pass

        def _collect_async(self):
            def work():
                try:
                    from core.brain_health import collect
                    from core.skill_registry import REGISTRY
                    # The hash check walks the merged corpus, which triggers
                    # skill discovery — the ENGINE owns that (worker thread,
                    # careful import order). Until it has happened, collect
                    # without the hash so this panel can never import heavy
                    # skill modules from a GUI-side thread.
                    ready = len(REGISTRY) > 50
                    self._pending = collect(
                        window_days=30, check_hash=ready).to_dict()
                except Exception as e:
                    log.debug("[intel-panel] collect failed: %s", e)
            threading.Thread(target=work, daemon=True,
                             name="IntelPanelCollect").start()

        def _apply_pending(self):
            d = self._pending
            if not d:
                return
            self._pending = None
            self._dial.set_score(d.get("health_score") or 0)
            router = {True: "NEURAL ✓", False: "k-NN FALLBACK ⚠",
                      None: "unknown"}[d.get("neural_active")]
            gold = d.get("golden_acc")
            val = d.get("best_val_acc")
            acc = d.get("acceptance_rate")
            lines = [
                f"router  {router}",
                f"model   gen {d.get('generation') or '—'}"
                f"  golden {f'{gold*100:.1f}%' if gold else '—'}"
                f"  val {f'{val*100:.1f}%' if val else '—'}",
                f"usage   {d.get('utterances_window', 0)} utt / "
                f"{d.get('window_days')}d"
                f"  accept {f'{acc*100:.0f}%' if acc is not None else '—'}",
                f"learned +{d.get('new_since_train', 0)} new · "
                f"{d.get('learned_review', 0)} in review",
            ]
            self._stats.setText("\n".join(lines))
            reasons = d.get("reasons") or []
            self._retrain_card.setVisible(bool(d.get("retrain_recommended")))
            if reasons:
                self._retrain_why.setText("RETRAIN DUE — "
                                          + "; ".join(reasons[:2]))
            conf = d.get("confusion_pairs") or []
            if conf:
                top = " · ".join(
                    f"{c['from']}→{c['to']}×{c['n']}"
                    for c in conf[:3])
                self._detail.setText(f"confusions  {top}")
            else:
                self._detail.setText(
                    "confusions  none logged — brain clean chal raha hai")

    return IntelligencePanel


# ─────────────────────────────────────────────────────────────────────── #
#  CONTINUITY — bodies, link, goals                                       #
# ─────────────────────────────────────────────────────────────────────── #

def _age_txt(ts: float) -> str:
    s = max(0, int(time.time() - ts))
    if s < 60:
        return "abhi"
    if s < 3600:
        return f"{s // 60}m"
    return f"{s // 3600}h"


def make_continuity_panel():
    _GlassPanel, _PanelHeader, _scrollable = _atoms()

    class ContinuityPanel(_GlassPanel):
        def __init__(self, parent=None):
            super().__init__(parent)
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)
            root.addWidget(_PanelHeader(
                "CONTINUITY", "ek mind · do body", J.GREEN))

            host = QWidget()
            lay = QVBoxLayout(host)
            lay.setContentsMargins(16, 12, 16, 14)
            lay.setSpacing(8)

            self._bodies = QLabel("reading presence…")
            self._bodies.setFont(mono(9, 600))
            self._bodies.setStyleSheet(
                f"color:{J.TEXT_PRI.name()};background:transparent;")
            lay.addWidget(self._bodies)

            self._link = QLabel("")
            self._link.setFont(mono(8, 500))
            self._link.setStyleSheet(
                f"color:{J.TEXT_MUT.name()};background:transparent;")
            self._link.setWordWrap(True)
            lay.addWidget(self._link)

            goals_head = QLabel("GOALS")
            goals_head.setFont(mono(8, 700))
            goals_head.setStyleSheet(
                f"color:{J.GREEN.name()};"
                "background:transparent;margin-top:6px;")
            lay.addWidget(goals_head)

            self._goals = QLabel("(koi standing goal nahi — phone ya "
                                 "yahan bolo “X pe nazar rakhna”)")
            self._goals.setFont(inter(9, 500))
            self._goals.setStyleSheet(
                f"color:{J.TEXT_SEC.name()};background:transparent;")
            self._goals.setWordWrap(True)
            lay.addWidget(self._goals)
            lay.addStretch(1)
            root.addWidget(_scrollable(host), 1)

            self._timer = QTimer(self)
            self._timer.timeout.connect(self._refresh)
            self._timer.start(5000)
            QTimer.singleShot(1200, self._refresh)

        def _refresh(self):
            try:
                from core.continuity import get_router, memory_slice
                r = get_router()
                active = r.registry.active_device()
                snap = r.registry.snapshot()
            except Exception:
                self._bodies.setText("continuity layer offline")
                return
            rows = []
            for dev in ("laptop", "phone"):
                info = snap.get(dev)
                mark = "●" if active == dev else "○"
                if info:
                    rows.append(f"{mark} {dev.upper():7s} {info['state']} "
                                f"· {_age_txt(info['ts'])}")
                else:
                    rows.append(f"{mark} {dev.upper():7s} —")
            self._bodies.setText("\n".join(rows))

            bits = []
            try:
                from core.cloud_bridge import get_bridge
                st = get_bridge().status()
                paired = st.get("paired", False)
                running = st.get("listening")
                bits.append("link: paired ✓" if paired
                            else "link: not paired — “phone pair "
                                 "karo” bolo")
                if paired:
                    bits.append("listening" if running else "bridge stopped")
            except Exception:
                bits.append("link: —")
            try:
                n = len(memory_slice().get("facts", []))
                bits.append(f"mem slice: {n} facts")
            except Exception:
                pass
            self._link.setText("  ·  ".join(bits))

            try:
                from core.goal_system import get_goal_store
                goals = [g for g in get_goal_store().all() if g.is_open]
            except Exception:
                goals = []
            if goals:
                lines = []
                for g in sorted(goals, key=lambda g: -g.updated)[:5]:
                    tag = {"blocked": "⏸", "acting": "▶",
                           "planning": "…"}.get(g.state, "▸")
                    line = f"{tag} {g.text[:44]}"
                    if g.state == "blocked" and g.ask:
                        line += f"\n    ↳ {g.ask[:52]}"
                    lines.append(line)
                self._goals.setText("\n".join(lines))
            else:
                self._goals.setText(
                    "(koi standing goal nahi — phone ya yahan bolo "
                    "“X pe nazar rakhna”)")

    return ContinuityPanel
