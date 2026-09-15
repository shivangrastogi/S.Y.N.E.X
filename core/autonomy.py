"""Autonomy Ladder + Ledger — the trust spine (Q1·M3).

See docs/AERIS_AUTONOMOUS_YEAR_PLAN.md. Before AERIS is allowed to act on its
own initiative (Q2+), it needs a governance layer that answers, for every
proposed action: *may I do this myself, must I ask first, or is it forbidden?* —
and records what happened so it's explainable and undoable.

Two pieces:

* **Autonomy Ladder** — each *action class* has a granted max level (L0–L5). A
  proposed action carries the autonomy level it wants; the ``TrustGate``
  authorizes it against the class grant, live budgets, quiet hours, and a global
  panic switch. Irreversible classes are capped low by design.
* **Ledger** — an append-only `data/ledger.jsonl` of every governed action with
  a plain-language ``why``. Budgets are computed from it; "AERIS, tu ne ye kyun
  kiya?" reads it.

Everything is injectable (clock, ledger path, panic flag) so it unit-tests with
no disk beyond a tmp file.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_LEDGER = os.path.join(_ROOT, "data", "ledger.jsonl")
_DEFAULT_PANIC = os.path.join(_ROOT, "data", "panic.flag")
_DEFAULT_GRANTS_PATH = os.path.join(_ROOT, "data", "trust_grants.json")

# ── the ladder ──────────────────────────────────────────────────────── #

L0_ASK, L1_SUGGEST, L2_DRAFT, L3_ACT, L4_GOAL, L5_DELEGATE = 0, 1, 2, 3, 4, 5

LEVEL_NAME = {
    0: "Ask", 1: "Suggest", 2: "Draft", 3: "Act+notify",
    4: "Act-on-goal", 5: "Delegated",
}

# Default max autonomy AERIS may use PER CLASS without asking. Irreversible /
# money / identity classes are capped low by design (plan: irreversible ≤ L2).
DEFAULT_GRANTS: dict[str, int] = {
    "read": L3_ACT,          # safe lookups
    "device": L3_ACT,        # reversible: torch, volume, brightness, DND
    "app": L3_ACT,           # open an app
    "media": L3_ACT,         # play/pause/next
    "message": L2_DRAFT,     # send msg/email → one-tap confirm
    "call": L2_DRAFT,
    "web": L2_DRAFT,         # browse/stage a booking
    "system": L1_SUGGEST,    # shutdown/restart/lock → offer
    "destructive": L1_SUGGEST,  # delete/forget/kill → offer (never above L2)
    "payment": L0_ASK,       # never autonomous
}

# Irreversible classes can never be granted above this, whatever the user sets.
HARD_CAP: dict[str, int] = {
    "destructive": L2_DRAFT,
    "payment": L2_DRAFT,
    "system": L2_DRAFT,
}


def classify(action: str) -> str:
    """Map a skill/action name to its autonomy class."""
    a = (action or "").lower()
    try:
        from core.confirm_gate import DESTRUCTIVE_SKILLS
        if a in DESTRUCTIVE_SKILLS:
            return "destructive"
    except Exception:
        pass
    if re.search(r"pay|upi|send_money|transfer", a):
        return "payment"
    if re.search(r"shutdown|restart|reboot|sleep_pc|lock_screen|logout", a):
        return "system"
    if re.search(r"forget|delete|clear|wipe|kill|reset|unteach|remove", a):
        return "destructive"
    if re.search(r"whatsapp|sms|message|mail|email|send|notify_contact", a):
        return "message"
    if re.search(r"call|dial|phone_", a):
        return "call"
    if re.search(r"browse|http|open_url|search_web|book|form", a):
        return "web"
    if re.search(r"open|launch|start_app|app_", a):
        return "app"
    if re.search(r"play|pause|next|previous|media", a):
        return "media"
    if re.search(r"torch|volume|bright|wifi|bluetooth|dnd|flash|screenshot", a):
        return "device"
    return "read"


# ── decision + config ───────────────────────────────────────────────── #

@dataclass
class Decision:
    outcome: str          # "allow" | "confirm" | "deny"
    why: str
    cls: str
    level: int
    granted: int


@dataclass
class Budgets:
    spend_cap_day: float = 5000.0        # ₹/day across all payments
    rate_cap_day: dict = field(default_factory=lambda: {
        "message": 40, "call": 20, "payment": 10, "web": 60,
    })
    quiet_start_h: int = 23              # no L3+ initiative in quiet hours
    quiet_end_h: int = 7


# ── the ledger ──────────────────────────────────────────────────────── #

class Ledger:
    """Append-only action log; budgets are derived from it."""

    def __init__(self, path: str = _DEFAULT_LEDGER,
                 *, now_fn: Callable[[], float] = time.time):
        self._path = path
        self._now = now_fn
        self._last_raw: Optional[str] = None   # last on-disk line (hash chain)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # In-memory cache: the Trust Gate reads the ledger on EVERY tool call
        # for budget checks, so re-parsing the file each time would be O(file)
        # per authorize (O(n²) over a run). Load once, then keep in sync on
        # append. Single-process by design, so the cache never goes stale.
        self._cache: Optional[list[dict]] = None

    def _rows(self) -> list[dict]:
        if self._cache is None:
            rows: list[dict] = []
            try:
                if os.path.exists(self._path):
                    with open(self._path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                rows.append(json.loads(line))
                                self._last_raw = line   # chain tail (S1)
            except Exception as e:
                log.warning("[ledger] read failed: %s", e)
            self._cache = rows
        return self._cache

    def record(self, *, action: str, args: dict, cls: str, level: int,
               decision: str, why: str, result: str = "",
               undo_token: Optional[str] = None, cost: float = 0.0) -> dict:
        entry = {
            "ts": self._now(), "action": action, "args": args, "cls": cls,
            "level": level, "decision": decision, "why": why,
            "result": result, "undo_token": undo_token, "cost": cost,
        }
        # Warm the cache from the CURRENT (pre-write) file first. If the very
        # first ledger op is a record(), a lazy load after the write would read
        # this entry back and the append below would duplicate it.
        rows = self._rows()
        # S1 tamper-evidence: each entry carries the sha256 of the previous
        # raw line, forming an append-only hash chain (`verify()` walks it).
        entry["prev_sha"] = (hashlib.sha256(self._last_raw.encode("utf-8"))
                             .hexdigest() if self._last_raw else "genesis")
        line = json.dumps(entry, ensure_ascii=False)
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            log.warning("[ledger] write failed: %s", e)
        self._last_raw = line
        rows.append(entry)  # keep the cache in sync (exactly once)
        return entry

    def verify(self) -> tuple[bool, Optional[int]]:
        """Walk the on-disk chain. Returns (ok, first_bad_line_no). Lines
        written before S1 (no ``prev_sha``) are grandfathered — the chain
        re-anchors at each of them."""
        prev: Optional[str] = None
        try:
            if not os.path.exists(self._path):
                return True, None
            with open(self._path, "r", encoding="utf-8") as f:
                for i, raw in enumerate(f, start=1):
                    raw = raw.rstrip("\n")
                    if not raw.strip():
                        continue
                    try:
                        d = json.loads(raw)
                    except Exception:
                        return False, i
                    want = d.get("prev_sha")
                    if want is not None:
                        have = (hashlib.sha256(prev.encode("utf-8")).hexdigest()
                                if prev is not None else "genesis")
                        if want != have:
                            return False, i
                    prev = raw
        except Exception as e:
            log.warning("[ledger] verify failed: %s", e)
            return False, None
        return True, None

    def all(self) -> list[dict]:
        return list(self._rows())

    def recent(self, n: int = 20) -> list[dict]:
        return self._rows()[-n:]

    def _today(self) -> list[dict]:
        today = datetime.fromtimestamp(self._now()).date()
        return [e for e in self._rows()
                if e.get("decision") == "allow"
                and datetime.fromtimestamp(e.get("ts", 0)).date() == today]

    def spend_today(self) -> float:
        return sum(float(e.get("cost", 0) or 0) for e in self._today())

    def count_today(self, cls: str) -> int:
        return sum(1 for e in self._today() if e.get("cls") == cls)

    def explain(self, action: Optional[str] = None) -> Optional[str]:
        for e in reversed(self._rows()):
            if action is None or e.get("action") == action:
                return e.get("why")
        return None


# ── the gate ────────────────────────────────────────────────────────── #

class TrustGate:
    """Authorizes a proposed autonomous action against grants, budgets, quiet
    hours, and the panic switch. Pure decision — the caller records the result
    to the ledger after acting."""

    def __init__(self, *, ledger: Optional[Ledger] = None,
                 grants: Optional[dict] = None,
                 budgets: Optional[Budgets] = None,
                 now_fn: Callable[[], float] = time.time,
                 is_panic: Optional[Callable[[], bool]] = None,
                 grants_path: Optional[str] = None):
        self.ledger = ledger or Ledger(now_fn=now_fn)
        self.budgets = budgets or Budgets()
        self._now = now_fn
        self._is_panic = is_panic or _panic_flag_reader()
        # User-adjusted autonomy per class persists to ``grants_path`` (opt-in;
        # tests construct without one and stay pure in-memory). Persisted values
        # layer over any explicit ``grants`` layer over DEFAULT_GRANTS.
        self._grants_path = grants_path
        base = {**DEFAULT_GRANTS, **(grants or {})}
        if grants_path:
            base.update(self._load_grants(grants_path))
        self.grants = base

    @staticmethod
    def _load_grants(path: str) -> dict:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                return {k: int(v) for k, v in (d.get("grants") or {}).items()
                        if k in DEFAULT_GRANTS}
        except Exception as e:
            log.warning("[trust] grants load failed: %s", e)
        return {}

    def _save_grants(self) -> None:
        if not self._grants_path:
            return
        try:
            overrides = {k: v for k, v in self.grants.items()
                         if v != DEFAULT_GRANTS.get(k)}
            from core.atomic_io import write_atomic_json
            write_atomic_json(self._grants_path, {"grants": overrides})
        except Exception as e:
            log.warning("[trust] grants save failed: %s", e)

    def set_grant(self, cls: str, level: int) -> int:
        """Set the autonomy grant for a class, clamped to [L0, HARD_CAP or L5]
        so the safety ceiling can never be raised past. Persists (if this gate
        has a path) and returns the new effective level."""
        if cls not in DEFAULT_GRANTS:
            raise ValueError(f"unknown class {cls!r}")
        ceiling = HARD_CAP.get(cls, L5_DELEGATE)
        self.grants[cls] = max(L0_ASK, min(int(level), ceiling))
        self._save_grants()
        return self.granted_level(cls)

    def granted_level(self, cls: str) -> int:
        g = self.grants.get(cls, L0_ASK)
        if cls in HARD_CAP:
            g = min(g, HARD_CAP[cls])
        return g

    def authorize(self, action: str, requested_level: int,
                  *, cost: float = 0.0, now: Optional[float] = None) -> Decision:
        cls = classify(action)
        # Panic → everything drops to L0 (only explicit user commands run).
        if self._is_panic():
            return Decision("deny", "PANIC: autonomy halted (L0).", cls,
                            requested_level, L0_ASK)
        granted = self.granted_level(cls)

        # Budgets first — a within-grant action can still need a confirm.
        if cost > 0 and self.ledger.spend_today() + cost > \
                self.budgets.spend_cap_day:
            return Decision("confirm",
                            f"spend cap ₹{self.budgets.spend_cap_day:.0f}/day "
                            f"crossed — confirm karo.", cls, requested_level,
                            granted)
        cap = self.budgets.rate_cap_day.get(cls)
        if cap is not None and self.ledger.count_today(cls) >= cap:
            return Decision("confirm",
                            f"{cls} ka daily limit ({cap}) hit — confirm karo.",
                            cls, requested_level, granted)
        # Quiet hours: no proactive L3+ acting; offer instead.
        if requested_level >= L3_ACT and self._in_quiet(now):
            return Decision("confirm", "Quiet hours — abhi khud nahi karunga, "
                            "confirm karo to karun.", cls, requested_level,
                            granted)

        if requested_level <= granted:
            return Decision("allow", f"{cls} @ {LEVEL_NAME.get(requested_level)} "
                            f"granted.", cls, requested_level, granted)
        # Wants more autonomy than granted.
        if granted >= L2_DRAFT:
            return Decision("confirm",
                            f"{cls} sirf {LEVEL_NAME.get(granted)} tak allowed — "
                            f"confirm karo.", cls, requested_level, granted)
        return Decision("deny",
                        f"{cls} autonomous allowed nahi ({LEVEL_NAME.get(granted)}).",
                        cls, requested_level, granted)

    def _in_quiet(self, now: Optional[float]) -> bool:
        h = datetime.fromtimestamp(now if now is not None else self._now()).hour
        s, e = self.budgets.quiet_start_h, self.budgets.quiet_end_h
        return (s <= h or h < e) if s > e else (s <= h < e)

    # -- public read accessors (for the Trust dashboard) ---------------

    def is_panic(self) -> bool:
        """True while the global halt is engaged (gate denies everything)."""
        return bool(self._is_panic())

    def in_quiet(self, now: Optional[float] = None) -> bool:
        """True inside the no-autonomous-initiative quiet-hours window."""
        return self._in_quiet(now)


# ── panic switch ────────────────────────────────────────────────────── #

def _panic_flag_reader(path: str = _DEFAULT_PANIC) -> Callable[[], bool]:
    return lambda: os.path.exists(path)


def set_panic(on: bool, path: str = _DEFAULT_PANIC) -> None:
    """Global halt: while set, the gate denies every autonomous action."""
    try:
        if on:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(str(time.time()))
        elif os.path.exists(path):
            os.remove(path)
    except Exception as e:
        log.warning("[panic] toggle failed: %s", e)


# ── module singleton ────────────────────────────────────────────────── #

_GATE: Optional[TrustGate] = None


def get_gate() -> TrustGate:
    global _GATE
    if _GATE is None:
        _GATE = TrustGate(grants_path=_DEFAULT_GRANTS_PATH)
    return _GATE
