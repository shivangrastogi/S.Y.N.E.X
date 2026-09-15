"""Trust Ladder — the safety spine for AERIS's autonomy (Sentient-Partner Phase 3).

Before AERIS does ANYTHING on its own (anticipation = Phase 4, cognition = Phase 6),
the candidate action passes through `classify()`, which returns one of:

  AUTO    — safe to do silently (local, reversible, non-outward)
  OFFER   — suggest it; do it on a simple "haan"
  CONFIRM — require explicit confirmation (destructive / outward / stateful-risky)
  FORBID  — never auto; only on an explicit user command (irreversible / high-impact)

A decision = **action risk** (its base tier) **clamped by the global autonomy level**
(0 = fully manual … 3 = trusted). Reuses `confirm_gate.DESTRUCTIVE_SKILLS` so the
autonomous gate and the user-command confirm gate never disagree.

Autonomy level: env `AERIS_AUTONOMY_LEVEL` (default 2). Lower = more conservative.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

AUTO = "auto"
OFFER = "offer"
CONFIRM = "confirm"
FORBID = "forbid"

# Rank for clamping (higher = more restrictive).
_RANK = {AUTO: 0, OFFER: 1, CONFIRM: 2, FORBID: 3}
_UNRANK = {v: k for k, v in _RANK.items()}

# Irreversible / high-impact — never auto, even on high autonomy.
_FORBID_KW = (
    "shutdown", "restart_pc", "reboot", "format", "factory", "uninstall",
    "wipe", "pay", "payment", "transfer", "purchase", "buy_", "checkout",
    "empty_recycle", "delete_all", "mass_", "self_destruct",
)
# Leaves the machine / reaches other people — confirm.
_OUTWARD_KW = (
    "send", "post", "email", "compose", "whatsapp", "message", "sms",
    "tweet", "share", "publish", "call_", "dial", "broadcast",
)
# Changes state but is easily reversible — offer.
_STATEFUL_KW = (
    "create", "add_", "set_", "note", "reminder", "timer", "alarm", "save",
    "schedule", "enable", "disable", "expense", "task", "meeting", "store",
    "rename", "move_", "copy_",
)


@dataclass(frozen=True)
class TrustDecision:
    level: str          # AUTO | OFFER | CONFIRM | FORBID
    reason: str

    @property
    def may_auto(self) -> bool:
        return self.level == AUTO

    @property
    def blocked(self) -> bool:
        return self.level == FORBID


def autonomy_level() -> int:
    try:
        return max(0, min(3, int(os.environ.get("AERIS_AUTONOMY_LEVEL", "2"))))
    except (TypeError, ValueError):
        return 2


def _base_tier(intent: str, is_destructive: Optional[bool]) -> tuple[str, str]:
    name = (intent or "").lower()
    if not name:
        return CONFIRM, "unknown action"

    # Destructive per the shared confirm-gate list, or irreversible keywords.
    if is_destructive is None:
        try:
            from core.confirm_gate import needs_confirmation
            is_destructive = needs_confirmation(intent)
        except Exception:
            is_destructive = False

    if any(k in name for k in _FORBID_KW):
        return FORBID, "irreversible / high-impact"
    if is_destructive:
        return CONFIRM, "destructive (confirm-gate)"
    if any(k in name for k in _OUTWARD_KW):
        return CONFIRM, "outward action (reaches others)"
    if any(k in name for k in _STATEFUL_KW):
        return OFFER, "changes state (reversible)"
    return AUTO, "local, reversible, silent"


def _clamp(base: str, level: int) -> str:
    """Lower autonomy makes AERIS more conservative — it can only *raise*
    the restriction, never lower a CONFIRM/FORBID.

      level 0 (manual)  : nothing auto/offer → min CONFIRM
      level 1 (careful) : may OFFER, never silent AUTO
      level 2 (default) : AUTO allowed for safe actions
      level 3 (trusted) : as classified
    """
    floor = {0: CONFIRM, 1: OFFER, 2: AUTO, 3: AUTO}.get(level, AUTO)
    return _UNRANK[max(_RANK[base], _RANK[floor])]


def classify(intent: str, args: Optional[dict] = None, *,
             level: Optional[int] = None,
             is_destructive: Optional[bool] = None) -> TrustDecision:
    """Classify a candidate *autonomous* action. `intent` is the skill/intent name."""
    base, reason = _base_tier(intent, is_destructive)
    lvl = autonomy_level() if level is None else max(0, min(3, level))
    final = _clamp(base, lvl)
    if final != base:
        reason = f"{reason} (autonomy L{lvl} → {final})"
    return TrustDecision(level=final, reason=reason)


def may_auto(intent: str, **kw) -> bool:
    """Convenience: can AERIS just DO this unprompted?"""
    return classify(intent, **kw).level == AUTO
