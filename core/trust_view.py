"""Trust view — makes "trust before autonomy" visible and auditable.

Everything AERIS does autonomously runs through the Autonomy Ladder
(``core.autonomy.TrustGate``) and lands in the append-only ``Ledger``. That
governance is invisible to the user, though. This read-only aggregator turns it
into a snapshot the Mind dashboard renders:

* **grants** — the effective autonomy level per action class, with the HARD_CAP
  on irreversible classes shown explicitly (so the user can see payment can
  *never* go autonomous, whatever the grant says).
* **state** — panic halt engaged? inside quiet hours? today's spend.
* **audit** — the recent "what did AERIS do, and why" trail (action, class,
  decision, reason, result, time), newest first.
* **stats** — today's allow / confirm / deny counts, so a glance shows whether
  the gate is mostly permitting or mostly gating.

Pure + injectable (gate + ledger pass in) → unit-tests with a real gate/ledger
on a tmp file, no dashboard or model.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from core.autonomy import (
    DEFAULT_GRANTS, HARD_CAP,
    L0_ASK, L1_SUGGEST, L2_DRAFT, L3_ACT, L4_GOAL, L5_DELEGATE,
)

# Human names for the six ladder rungs (docs/AERIS_AUTONOMOUS_YEAR_PLAN.md).
LEVEL_NAMES: Dict[int, str] = {
    L0_ASK: "Ask",
    L1_SUGGEST: "Suggest",
    L2_DRAFT: "Draft · confirm",
    L3_ACT: "Act · notify",
    L4_GOAL: "Act on goal",
    L5_DELEGATE: "Delegated",
}

# A friendly one-liner per class so the dashboard explains what each covers.
CLASS_BLURB: Dict[str, str] = {
    "read": "safe lookups",
    "device": "torch, volume, brightness, DND (reversible)",
    "app": "open an app",
    "media": "play / pause / next",
    "message": "send a message or email",
    "call": "place a call",
    "web": "browse / stage a booking",
    "system": "shutdown / restart / lock",
    "destructive": "delete / forget / kill",
    "payment": "spend money",
}


def level_name(level: int) -> str:
    return LEVEL_NAMES.get(int(level), f"L{level}")


def _gate():
    from core.autonomy import get_gate
    return get_gate()


def _ledger(gate):
    return gate.ledger


def grants_view(gate=None) -> list[Dict[str, Any]]:
    """The effective autonomy per class, most-trusted first, HARD_CAP surfaced."""
    gate = gate or _gate()
    rows: list[Dict[str, Any]] = []
    for cls in sorted(set(DEFAULT_GRANTS) | set(gate.grants)):
        raw = gate.grants.get(cls, L0_ASK)
        eff = gate.granted_level(cls)          # applies HARD_CAP
        cap = HARD_CAP.get(cls)
        rows.append({
            "cls": cls,
            "blurb": CLASS_BLURB.get(cls, ""),
            "granted": eff,
            "granted_name": level_name(eff),
            "raw_grant": raw,
            "hard_cap": cap,
            "capped": cap is not None and eff < raw,
        })
    rows.sort(key=lambda r: (-r["granted"], r["cls"]))
    return rows


def _audit_row(e: Dict[str, Any]) -> Dict[str, Any]:
    ts = e.get("ts")
    try:
        tstr = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""
    except Exception:
        tstr = ""
    return {
        "action": e.get("action", ""),
        "cls": e.get("cls", ""),
        "level": e.get("level"),
        "decision": e.get("decision", ""),
        "why": e.get("why", ""),
        "result": (e.get("result") or "")[:80],
        "cost": e.get("cost", 0.0),
        "ts": ts,
        "time": tstr,
    }


def audit_view(gate=None, *, n: int = 20) -> list[Dict[str, Any]]:
    """The most recent ledger entries, newest first."""
    gate = gate or _gate()
    rows = _ledger(gate).recent(n)
    return [_audit_row(e) for e in reversed(rows)]


def _decision_stats(ledger, *, decisions=("allow", "confirm", "deny")) -> Dict[str, int]:
    counts = {d: 0 for d in decisions}
    for e in ledger.all():
        d = e.get("decision")
        if d in counts:
            counts[d] += 1
    return counts


def apply_action(action: str, params: Dict[str, Any], *, gate=None,
                 panic_path: Optional[str] = None) -> Dict[str, Any]:
    """Apply a user control from the Trust dashboard. Pure over an injected
    gate (grant/quiet mutate it in place & persist); panic toggles the global
    flag. Returns a small result dict. Raises ValueError on a bad request so the
    server can answer 400. HARD_CAP is enforced in ``gate.set_grant``, so this
    can never lift a class past its safety ceiling.
    """
    gate = gate or _gate()
    action = (action or "").strip().lower()

    if action == "panic":
        from core.autonomy import set_panic, _DEFAULT_PANIC
        on = bool(params.get("on"))
        set_panic(on, path=panic_path or _DEFAULT_PANIC)
        return {"ok": True, "panic": on}

    if action == "grant":
        cls = params.get("cls")
        if "level" not in params:
            raise ValueError("grant needs a 'level'")
        eff = gate.set_grant(cls, int(params["level"]))
        return {"ok": True, "cls": cls, "granted": eff,
                "granted_name": level_name(eff)}

    if action == "quiet":
        s, e = int(params.get("start", gate.budgets.quiet_start_h)), \
            int(params.get("end", gate.budgets.quiet_end_h))
        gate.budgets.quiet_start_h = s % 24
        gate.budgets.quiet_end_h = e % 24
        return {"ok": True, "quiet_hours": {"start": gate.budgets.quiet_start_h,
                                            "end": gate.budgets.quiet_end_h}}

    raise ValueError(f"unknown trust action {action!r}")


def snapshot(gate=None, *, now: Optional[float] = None,
             audit_n: int = 20) -> Dict[str, Any]:
    """The full Trust snapshot for the dashboard (read-only, no side effects)."""
    gate = gate or _gate()
    ledger = _ledger(gate)
    b = gate.budgets
    return {
        "panic": gate.is_panic(),
        "quiet_hours": {
            "active": gate.in_quiet(now),
            "start": b.quiet_start_h,
            "end": b.quiet_end_h,
        },
        "spend_today": round(ledger.spend_today(), 2),
        "spend_cap_day": b.spend_cap_day,
        "grants": grants_view(gate),
        "stats": _decision_stats(ledger),
        "audit": audit_view(gate, n=audit_n),
    }
