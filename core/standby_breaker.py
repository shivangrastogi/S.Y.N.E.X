"""Circuit breaker for brain spin-up — stop hammering a brain that won't start.

Liveness reconciliation (``standby_runtime``) handles a brain that *started then
died*. This handles the other failure mode: a brain that **won't come up at all**
— a corrupt model file, a missing dependency, an ABI break. Without a breaker,
every wake retries the spawn immediately, and each failed spawn can be expensive
(it may load half the native stack before failing). The user just gets silence,
repeatedly, while the machine thrashes.

``SpinUpBreaker`` is the standard three-state breaker:

    CLOSED     — normal. Spin-up attempts are allowed. Consecutive failures are
                 counted; on the ``threshold``-th the breaker trips OPEN.
    OPEN       — tripped. Attempts are refused (fail fast, no expensive spawn)
                 until a cooldown elapses; then it becomes HALF_OPEN.
    HALF_OPEN  — one trial attempt is allowed. Success → CLOSED (recovered);
                 failure → OPEN again with a longer (exponential) cooldown.

The clock is injected, so every transition and the backoff schedule are
unit-tested deterministically with no real waiting.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Callable


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class SpinUpBreaker:
    """Trips after repeated spin-up failures; recovers via a half-open probe."""

    def __init__(
        self,
        *,
        threshold: int = 3,
        base_cooldown_s: float = 10.0,
        max_cooldown_s: float = 300.0,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = max(1, int(threshold))
        self._base = max(0.0, float(base_cooldown_s))
        self._max = max(self._base, float(max_cooldown_s))
        self._now = now

        self._failures = 0        # consecutive spin-up failures (CLOSED counting)
        self._state = BreakerState.CLOSED
        self._opened_at = 0.0
        self._open_count = 0      # times tripped in a row → exponential backoff
        self._cooldown = 0.0

    # ---- internal ---------------------------------------------------- #

    def _refresh(self) -> None:
        """OPEN → HALF_OPEN once the cooldown has elapsed."""
        if self._state is BreakerState.OPEN:
            if (self._now() - self._opened_at) >= self._cooldown:
                self._state = BreakerState.HALF_OPEN

    def _trip(self) -> None:
        self._state = BreakerState.OPEN
        self._opened_at = self._now()
        # Exponential backoff, capped: base, 2·base, 4·base, … ≤ max.
        self._cooldown = min(self._max, self._base * (2 ** self._open_count))
        self._open_count += 1

    # ---- observation ------------------------------------------------- #

    @property
    def state(self) -> BreakerState:
        self._refresh()
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._failures

    def cooldown_remaining(self) -> float:
        """Seconds until an OPEN breaker will allow a trial (0 otherwise)."""
        self._refresh()
        if self._state is not BreakerState.OPEN:
            return 0.0
        return max(0.0, self._cooldown - (self._now() - self._opened_at))

    # ---- decisions / events ------------------------------------------ #

    def allow(self) -> bool:
        """Whether a spin-up attempt is permitted right now."""
        self._refresh()
        return self._state in (BreakerState.CLOSED, BreakerState.HALF_OPEN)

    def record_success(self) -> None:
        """A spin-up succeeded — fully recover."""
        self._failures = 0
        self._open_count = 0
        self._cooldown = 0.0
        self._state = BreakerState.CLOSED

    def record_failure(self) -> None:
        """A spin-up failed — count it and maybe trip."""
        self._refresh()
        self._failures += 1
        # A failure during the half-open trial re-opens immediately (longer
        # cooldown); in CLOSED we trip once we hit the threshold.
        if self._state is BreakerState.HALF_OPEN or self._failures >= self._threshold:
            self._trip()

    def describe(self) -> str:
        s = self.state
        if s is BreakerState.OPEN:
            return f"brain unavailable — retry in {self.cooldown_remaining():.0f}s"
        if s is BreakerState.HALF_OPEN:
            return "brain recovery probe pending"
        return "ok"
