"""Earned trust — proposing autonomy raises from the ledger (§6.32).

`core/autonomy.py` has the Autonomy Ladder (per-class grants L0–L5, hard caps on
irreversible classes) and an append-only, hash-chained Ledger of every governed
action. `core/eval_harness.py` has the L3→L4 gate. What was missing is the
thing that connects them: **nothing ever looks at the track record and says
"this class has earned a step up"**. `set_grant` is reached only from
`core/trust_view.py` — i.e. the user raises grants by hand, from memory.

This module reads the ledger and proposes. It is the "trust before autonomy"
loop's missing half, and P4's "the initiative engine graduates from offer to
trusted act".

### It proposes; it never promotes

Nothing here calls `set_grant`. A system that quietly grants itself more power
is exactly the thing an autonomy ladder exists to prevent, and a silent raise
would be undetectable until it acted on its own. Recommendations surface as a
*notify* initiative — the same shape `brain_health` uses for "retrain due" —
and the user applies them.

### What the evidence actually supports

Worth being precise, because it is tempting to claim more. The ledger records
`decision` (allow / confirm / deny) and a `result`, but **not whether the user
said yes to a `confirm`**. So an "approval rate" cannot be computed from it
without inventing data.

What *is* honestly there: how often a class ran at its granted level, whether
anything was denied, and whether results carried failures. So a recommendation
here means:

    "this class has executed cleanly N times over D days, with no denials and
     no failures — consider allowing it one step further"

**Since §6.33 refusals are recorded too** (`decision="declined"`), so this is no
longer only a reliability claim. A class the user keeps saying no to is now
visibly different from one they were never asked about — which it was not
before, and which was a real hole: the first cut of this module would have
cheerfully proposed raising a class the user had refused ten times.

A refusal counts against a class exactly as heavily as a hard denial. The user
actively declining is the clearest possible evidence that something should not
get more rope.

What still cannot be counted is a confirmation the user simply never answers.
Those park and expire, and are treated as neither approval nor refusal rather
than being guessed at.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

WINDOW_DAYS = 14.0
MIN_SAMPLES = 8          # below this, a clean record is luck rather than evidence
MAX_FAILURE_RATE = 0.0   # any failure resets the case; this is about reliability

# Words that mean a recorded result went wrong. The ledger stores whatever the
# tool returned, so this is a heuristic — deliberately broad, because a false
# "it failed" only costs a recommendation we did not make.
_FAILURE_MARKERS = ("error", "failed", "failure", "exception", "traceback",
                    "denied", "not found", "unable", "could not", "timeout")


def looks_failed(result: Any) -> bool:
    text = str(result or "").lower()
    return any(m in text for m in _FAILURE_MARKERS)


@dataclass
class Promotion:
    cls: str
    current: int
    proposed: int
    samples: int
    window_days: float
    reason: str

    def sentence(self) -> str:
        return (f"'{self.cls}' {self.samples} baar bina kisi dikkat ke chala "
                f"{self.window_days:.0f} din me — level L{self.current} se "
                f"L{self.proposed} karu, sir?")


@dataclass
class ClassRecord:
    cls: str
    total: int = 0
    allowed: int = 0
    denied: int = 0
    failed: int = 0
    asked: int = 0        # the gate required a confirmation
    declined: int = 0     # ...and the user said no (§6.33)

    @property
    def clean(self) -> bool:
        """No evidence against. A refusal counts as heavily as a hard denial:
        the user actively saying no is the single clearest signal that a class
        should NOT get more rope."""
        return self.denied == 0 and self.failed == 0 and self.declined == 0

    @property
    def consent_rate(self):
        """Approvals / times asked, or ``None`` when never asked.

        Only meaningful because declines are now recorded (§6.33). Before
        that, a class the user kept refusing was indistinguishable from one
        they were never asked about.
        """
        if self.asked <= 0:
            return None
        return max(0.0, (self.asked - self.declined) / self.asked)


def tally(rows, *, now: Optional[float] = None,
          window_days: float = WINDOW_DAYS) -> dict:
    """Per-class record over the window. Pure — takes rows, returns counts."""
    now = time.time() if now is None else now
    cutoff = now - window_days * 86400.0
    out: dict[str, ClassRecord] = {}
    for r in rows or []:
        try:
            if float(r.get("ts") or 0.0) < cutoff:
                continue
            cls = str(r.get("cls") or "")
            if not cls:
                continue
            rec = out.setdefault(cls, ClassRecord(cls=cls))
            rec.total += 1
            decision = str(r.get("decision") or "")
            if decision == "allow":
                rec.allowed += 1
            elif decision == "deny":
                rec.denied += 1
            elif decision == "confirm":
                rec.asked += 1
            elif decision == "declined":
                rec.asked += 1
                rec.declined += 1
            if looks_failed(r.get("result")):
                rec.failed += 1
        except Exception as e:      # one malformed row must not lose the rest
            log.debug("[trust] skipping ledger row: %s", e)
    return out


def assess(rows, gate: Any, *, now: Optional[float] = None,
           window_days: float = WINDOW_DAYS,
           min_samples: int = MIN_SAMPLES) -> list:
    """Which classes have earned a step up? Highest-evidence first.

    ``gate`` supplies the current grant and the ceiling, so a class already at
    its hard cap is never proposed — the cap exists precisely because no amount
    of good behaviour should unlock an irreversible action.
    """
    from core.autonomy import HARD_CAP, L5_DELEGATE

    out = []
    for cls, rec in tally(rows, now=now, window_days=window_days).items():
        try:
            current = int(gate.granted_level(cls))
        except Exception:
            continue
        ceiling = int(HARD_CAP.get(cls, L5_DELEGATE))
        if current >= ceiling:
            continue                       # capped on purpose
        if rec.allowed < min_samples:
            continue                       # not enough evidence yet
        if not rec.clean:
            continue                       # a denial or failure resets the case
        consent = rec.consent_rate
        reason = (f"{rec.allowed} clean runs in {window_days:.0f}d, "
                  f"0 denials, 0 failures")
        if consent is not None:
            reason += f", {rec.asked} confirmations all approved"
        out.append(Promotion(
            cls=cls, current=current, proposed=min(current + 1, ceiling),
            samples=rec.allowed, window_days=window_days, reason=reason))
    out.sort(key=lambda p: -p.samples)
    return out


# ── initiative source ────────────────────────────────────────────────── #
# Same shape as `brain_health.initiative_candidates`: at most one nudge per
# cooldown, surfaced as a NOTIFY, never as an autonomous act. Raising autonomy
# is the one decision that must never be taken autonomously.

_NUDGE_COOLDOWN_S = 3 * 86400.0
_last_nudge: float = 0.0


def initiative_candidates(now_fn: Callable[[], float] = time.time) -> list:
    global _last_nudge
    try:
        now = now_fn()
        if now - _last_nudge < _NUDGE_COOLDOWN_S:
            return []
        from core.autonomy import get_gate
        gate = get_gate()
        best = assess(gate.ledger.all(), gate, now=now)
        if not best:
            return []
        p = best[0]
        _last_nudge = now
        from core.initiative_engine import Initiative
        return [Initiative(
            text=(p.sentence() + " (Trust panel se badal sakte ho.)"),
            kind="trust_promotion", action="notify_user",
            importance=0.45, timeliness=0.4, confidence=0.8, openness=0.4,
            source_id=f"trust:{p.cls}:{p.proposed}", requested_level=2,
        )]
    except Exception as e:
        log.debug("[trust] initiative source failed: %s", e)
        return []


def reset_nudge_clock() -> None:
    """Test hook — the cooldown is module state by design (one nudge per
    process-lifetime window), so tests need a way to clear it."""
    global _last_nudge
    _last_nudge = 0.0
