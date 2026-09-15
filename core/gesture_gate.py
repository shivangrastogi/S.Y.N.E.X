"""Presence-gated gesture arming — gestures only live when you're actually there.

The gesture engine is a real-time CV pipeline: leaving it consuming frames when
the user has walked away or gone idle is wasted CPU and, worse, a source of
false fires (a passer-by, a stretch, a coffee mug). This gate ties the gesture
engine to the **fused eternal-presence state** so it arms only while you're
ACTIVE or in FOCUS, and quietly disarms on IDLE / AWAY.

Two correctness guarantees keep it from fighting the user:

* **It only undoes its own pause.** If the user manually turned gestures off,
  the gate won't surprise-resume them — it only resumes a session *it* paused.
* **Privacy wins.** With the privacy switch on, the gate disarms and stays
  disarmed regardless of presence.

The engine and presence sources are injected, so the whole thing unit-tests
with tiny fakes — no camera, no MediaPipe, no torch.

    from core.gesture_gate import install_gesture_gating
    install_gesture_gating()        # wires the real singletons
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)

# Presence states in which gestures should be live.
_ARMED_STATES = ("active", "focus")


class GestureGate:
    """Bridges presence state → gesture-engine arm/disarm. Inject ``engine``
    and a ``privacy`` predicate for tests; defaults resolve the real ones."""

    def __init__(self, engine=None, privacy=None):
        self._engine = engine
        self._privacy = privacy
        self._paused_by_gate = False     # did *we* stop it (vs the user)?
        self._installed = False

    # ── resolution (lazy, optional) ──────────────────────────────────

    def _ge(self):
        if self._engine is not None:
            return self._engine
        try:
            from core.gesture_engine import get_gesture_engine
            return get_gesture_engine()
        except Exception:
            return None

    def _privacy_on(self) -> bool:
        if self._privacy is not None:
            try:
                return bool(self._privacy())
            except Exception:
                return False
        try:
            from core.privacy_mode import is_on
            return bool(is_on())
        except Exception:
            return False

    # ── the gate logic ───────────────────────────────────────────────

    def on_state(self, new_state: str, prev: str = "") -> None:
        """React to a presence transition. Public so tests can call directly."""
        ge = self._ge()
        if ge is None:
            return

        if self._privacy_on():
            self._disarm(ge)
            return

        if new_state in _ARMED_STATES:
            self._arm(ge)
        else:
            self._disarm(ge)

    def _arm(self, ge) -> None:
        # Only resume what we paused; never force-start a user-disabled engine.
        if not self._paused_by_gate:
            return
        try:
            if not ge.is_enabled():
                ge.start()
                log.info("[gesture-gate] armed (user present).")
        finally:
            self._paused_by_gate = False

    def _disarm(self, ge) -> None:
        try:
            if ge.is_enabled():
                ge.stop()
                self._paused_by_gate = True
                log.info("[gesture-gate] disarmed (user away/idle).")
        except Exception:
            log.debug("[gesture-gate] disarm failed", exc_info=True)

    # ── install ──────────────────────────────────────────────────────

    def install(self, presence=None) -> bool:
        if self._installed:
            return True
        try:
            if presence is None:
                from core.eternal_presence import get_eternal_presence
                presence = get_eternal_presence()
            presence.add_state_listener(self.on_state)
            self._installed = True
            log.info("[gesture-gate] installed.")
            return True
        except Exception:
            log.debug("[gesture-gate] install failed", exc_info=True)
            return False


_DEFAULT: Optional[GestureGate] = None


def get_gesture_gate() -> GestureGate:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = GestureGate()
    return _DEFAULT


def install_gesture_gating(presence=None) -> bool:
    """Convenience: wire the process-wide gate to the live presence engine."""
    return get_gesture_gate().install(presence=presence)
