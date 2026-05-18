"""Skill timeout + circuit breaker.

Wraps every plugin skill invocation in two protective layers:

  1. **Timeout** — the handler runs on a worker thread; if it doesn't
     return within ``timeout_s`` we abandon the wait and return a
     friendly error message. The thread keeps running (we cannot
     forcibly kill a Python thread that's stuck in C), but the user
     gets immediate feedback and the rest of AERIS stays responsive.

  2. **Circuit breaker** — three consecutive failures (timeout OR
     exception) trip the breaker; subsequent invocations short-circuit
     to a "this skill is disabled" message until either:
        - 60 seconds elapse (half-open: one trial call lets it back in)
        - the user explicitly calls ``reset(name)`` from a debug menu

Why thread + future, not asyncio
--------------------------------
Skills are written as plain ``def handler(slots) -> str``. Migrating
all 21 skills to async would be a multi-day rewrite. A
ThreadPoolExecutor with bounded concurrency gives us the timeout +
cancellation contract today with zero plugin churn.

The breaker state is in-memory only — restart resets every skill. This
is intentional: a permanently-disabled skill is a worse UX than a
flaky one that gets a fresh chance on next launch.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as _FuturesTimeout
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


# ── Tunables ───────────────────────────────────────────────────────── #

_DEFAULT_TIMEOUT_S = 5.0
_FAILURE_THRESHOLD = 3              # consecutive failures to trip the breaker
_OPEN_DURATION_S = 60.0             # how long the breaker stays OPEN
_POOL_MAX_WORKERS = 8               # cap concurrent skill invocations


class _State(Enum):
    CLOSED = auto()      # normal — calls flow through
    OPEN = auto()        # tripped — calls short-circuit to error
    HALF_OPEN = auto()   # trial — one call permitted; success → CLOSED


@dataclass
class _Breaker:
    name: str
    timeout_s: float = _DEFAULT_TIMEOUT_S
    state: _State = _State.CLOSED
    failures: int = 0
    opened_at: float = 0.0
    total_calls: int = 0
    total_failures: int = 0
    total_timeouts: int = 0


@dataclass
class CallResult:
    """Outcome of a guarded skill call. Always returns one of:
    success / error / timeout / shorted (breaker-open)."""
    ok: bool
    value: Any = None
    error: Optional[str] = None
    timed_out: bool = False
    short_circuited: bool = False
    elapsed_ms: int = 0


# ── Singleton state ────────────────────────────────────────────────── #

_lock = threading.RLock()
_breakers: dict[str, _Breaker] = {}
_pool: Optional[ThreadPoolExecutor] = None


def _get_pool() -> ThreadPoolExecutor:
    global _pool
    with _lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(
                max_workers=_POOL_MAX_WORKERS,
                thread_name_prefix="skill",
            )
    return _pool


def shutdown_pool() -> None:
    """Wind down the worker pool. Called from core.shutdown."""
    global _pool
    with _lock:
        p = _pool
        _pool = None
    if p is not None:
        p.shutdown(wait=False, cancel_futures=True)


# ── Per-skill knobs ────────────────────────────────────────────────── #

def configure(name: str,
              *,
              timeout_s: Optional[float] = None) -> None:
    """Override the default timeout for a single skill."""
    with _lock:
        b = _breakers.setdefault(name, _Breaker(name=name))
        if timeout_s is not None:
            b.timeout_s = max(0.5, float(timeout_s))


def reset(name: Optional[str] = None) -> None:
    """Reset one skill (or all skills) to CLOSED state, clear counters."""
    with _lock:
        if name is None:
            for b in _breakers.values():
                _reset_one(b)
        elif name in _breakers:
            _reset_one(_breakers[name])


def _reset_one(b: _Breaker) -> None:
    b.state = _State.CLOSED
    b.failures = 0
    b.opened_at = 0.0


def state(name: str) -> str:
    with _lock:
        b = _breakers.get(name)
        return b.state.name if b else "CLOSED"


def stats() -> list[dict[str, Any]]:
    """Snapshot every known breaker — feeds the logs panel / /metrics."""
    with _lock:
        return [
            {
                "name": b.name,
                "state": b.state.name,
                "consecutive_failures": b.failures,
                "total_calls": b.total_calls,
                "total_failures": b.total_failures,
                "total_timeouts": b.total_timeouts,
                "timeout_s": b.timeout_s,
            }
            for b in sorted(_breakers.values(), key=lambda x: x.name)
        ]


# ── Core wrapper ───────────────────────────────────────────────────── #

def call(name: str,
         fn: Callable[..., Any],
         *args,
         **kwargs) -> CallResult:
    """Invoke ``fn(*args, **kwargs)`` under the breaker named ``name``.

    Use this from the dispatch path that today calls the skill handler
    directly. Returns a structured ``CallResult`` regardless of outcome —
    no exceptions propagate.
    """
    started = time.monotonic()
    with _lock:
        b = _breakers.setdefault(name, _Breaker(name=name))

        # Half-open after cooldown
        if b.state == _State.OPEN and (time.monotonic() - b.opened_at) > _OPEN_DURATION_S:
            log.info("[breaker] %s OPEN→HALF_OPEN (cooldown elapsed)", name)
            b.state = _State.HALF_OPEN

        if b.state == _State.OPEN:
            return CallResult(
                ok=False,
                short_circuited=True,
                error=f"Skill '{name}' is temporarily disabled "
                      f"after repeated failures. Auto-retry in "
                      f"{int(_OPEN_DURATION_S - (time.monotonic() - b.opened_at))}s.",
                elapsed_ms=0,
            )

        b.total_calls += 1
        timeout = b.timeout_s

    # Submit to the bounded pool so a runaway skill can't spawn unlimited threads.
    pool = _get_pool()
    fut: Future = pool.submit(fn, *args, **kwargs)
    try:
        value = fut.result(timeout=timeout)
    except _FuturesTimeout:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        _record_failure(name, kind="timeout")
        # We can't kill the thread — the work continues in the background;
        # but we DON'T await its result. cancel() returns False post-start
        # but we mark the future done from the caller's perspective.
        fut.cancel()
        return CallResult(
            ok=False, timed_out=True,
            error=f"Skill '{name}' did not respond within {timeout:.1f}s.",
            elapsed_ms=elapsed_ms,
        )
    except BaseException as e:  # noqa: BLE001 — preserve every kind of failure
        elapsed_ms = int((time.monotonic() - started) * 1000)
        _record_failure(name, kind="error", err=e)
        return CallResult(
            ok=False, error=f"{e.__class__.__name__}: {e}",
            elapsed_ms=elapsed_ms,
        )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    _record_success(name)
    return CallResult(ok=True, value=value, elapsed_ms=elapsed_ms)


def _record_success(name: str) -> None:
    with _lock:
        b = _breakers.get(name)
        if b is None:
            return
        if b.state == _State.HALF_OPEN:
            log.info("[breaker] %s HALF_OPEN→CLOSED (trial call succeeded)", name)
        b.state = _State.CLOSED
        b.failures = 0


def _record_failure(name: str, *, kind: str, err: BaseException | None = None) -> None:
    with _lock:
        b = _breakers.get(name)
        if b is None:
            return
        b.failures += 1
        b.total_failures += 1
        if kind == "timeout":
            b.total_timeouts += 1
        # In HALF_OPEN any failure re-opens immediately, regardless of streak.
        if b.state == _State.HALF_OPEN or b.failures >= _FAILURE_THRESHOLD:
            if b.state != _State.OPEN:
                log.warning("[breaker] %s → OPEN (failure %d, kind=%s, last=%r)",
                            name, b.failures, kind, err)
            b.state = _State.OPEN
            b.opened_at = time.monotonic()


# ── Smoke test ─────────────────────────────────────────────────────── #

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    def flaky(should_fail: bool):
        if should_fail:
            raise RuntimeError("boom")
        return "ok"

    def slow():
        time.sleep(2.0)
        return "done"

    configure("flaky", timeout_s=1.0)
    configure("slow",  timeout_s=0.5)

    print("--- 3 failures should open the breaker ---")
    for _ in range(4):
        r = call("flaky", flaky, True)
        print(f"  {r}")

    print("--- subsequent call short-circuits ---")
    r = call("flaky", flaky, False)
    print(f"  {r}")

    print("--- slow call timeout ---")
    r = call("slow", slow)
    print(f"  {r}")

    print("--- stats ---")
    for s in stats():
        print(" ", s)
    shutdown_pool()
