"""Process-wide cache registry + memory-pressure responder.

Wraps stdlib's ``functools.lru_cache`` so every cache built through
``bounded_cache`` is:

  1. Discoverable — the registry can enumerate every cache (handy for
     a ``/metrics`` endpoint or a debug command);
  2. Sheddable — when the ResourceMonitor emits ``LEVEL_WARNING`` we
     halve every registered cache's max-size; on ``LEVEL_CRITICAL`` we
     ``cache_clear`` them entirely.

The contract:
    @bounded_cache(maxsize=4096, name="normalizer.clean")
    def clean(text): ...

The decorator returns a function with stdlib's ``cache_info()`` /
``cache_clear()`` API plus a ``cache_resize(new_maxsize)`` shim so the
shedding hook can shrink it.

Why not just ``functools.lru_cache``?
- We need a single place to subscribe to ResourceMonitor.
- We need to RESIZE (stdlib only supports clear, not shrink), which
  requires re-wrapping the underlying function with a new lru_cache.
- Names make /metrics readable instead of showing anonymous function
  ids.

Subscribers register the central pressure-handler exactly once at boot:

    from core.resource_monitor import get_monitor
    from core.cache_registry import register_pressure_handler
    register_pressure_handler(get_monitor())
"""
from __future__ import annotations

import functools
import logging
import threading
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


# ── Registry ───────────────────────────────────────────────────────── #

_lock = threading.RLock()
_caches: dict[str, "_BoundedCache"] = {}


class _BoundedCache:
    """Wraps an lru_cache that we can resize at runtime."""

    def __init__(self, fn: Callable, maxsize: int, name: str):
        self._fn = fn
        self._name = name
        self._maxsize = max(1, int(maxsize))
        self._cached = functools.lru_cache(maxsize=self._maxsize)(fn)

    @property
    def name(self) -> str:
        return self._name

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def __call__(self, *args, **kwargs):
        return self._cached(*args, **kwargs)

    def cache_info(self):
        return self._cached.cache_info()

    def cache_clear(self) -> None:
        self._cached.cache_clear()

    def cache_resize(self, new_maxsize: int) -> None:
        """Shrink (or grow) the cache. Implemented by rebuilding the
        ``lru_cache`` wrapper — stdlib has no resize syscall.
        """
        new_max = max(1, int(new_maxsize))
        if new_max == self._maxsize:
            return
        old_info = self.cache_info()
        self._maxsize = new_max
        self._cached = functools.lru_cache(maxsize=new_max)(self._fn)
        log.debug("[cache] %s resized %d → %d (was %d entries)",
                  self._name, old_info.maxsize, new_max, old_info.currsize)


def bounded_cache(*, maxsize: int = 1024, name: Optional[str] = None):
    """Decorator factory. Use exactly like ``functools.lru_cache`` but
    with a ``name=`` for the registry.
    """
    def _wrap(fn: Callable) -> _BoundedCache:
        cache_name = name or f"{fn.__module__}.{fn.__qualname__}"
        bc = _BoundedCache(fn, maxsize=maxsize, name=cache_name)
        with _lock:
            if cache_name in _caches:
                log.warning("[cache] duplicate name %s — replacing", cache_name)
            _caches[cache_name] = bc
        return bc
    return _wrap


def all_caches() -> list[_BoundedCache]:
    with _lock:
        return list(_caches.values())


def cache_stats() -> list[dict[str, Any]]:
    """Snapshot every registered cache. Useful for /metrics, debug menus."""
    out: list[dict[str, Any]] = []
    for c in all_caches():
        info = c.cache_info()
        out.append({
            "name": c.name,
            "hits": info.hits,
            "misses": info.misses,
            "currsize": info.currsize,
            "maxsize": info.maxsize,
            "hit_rate": (info.hits / (info.hits + info.misses)
                         if (info.hits + info.misses) else 0.0),
        })
    return out


# ── ResourceMonitor integration ────────────────────────────────────── #

def _on_pressure(level: int) -> None:
    """Pressure callback — runs on ResourceMonitor's thread. Must be
    thread-safe (cache_resize / cache_clear both are)."""
    from core.resource_monitor import LEVEL_CRITICAL, LEVEL_WARNING
    if level == LEVEL_WARNING:
        for c in all_caches():
            c.cache_resize(max(64, c.maxsize // 2))
        log.info("[cache] WARNING pressure — halved %d caches", len(all_caches()))
    elif level == LEVEL_CRITICAL:
        for c in all_caches():
            c.cache_clear()
        log.info("[cache] CRITICAL pressure — cleared %d caches", len(all_caches()))
    # LEVEL_OK transition: leave caches as they are; if the user wants
    # them to grow back the next round of misses will refill them.


_registered_with: set[int] = set()
_registration_lock = threading.Lock()


def register_pressure_handler(monitor) -> None:
    """Idempotent — wires this module to a ResourceMonitor instance."""
    key = id(monitor)
    with _registration_lock:
        if key in _registered_with:
            return
        monitor.subscribe(_on_pressure)
        _registered_with.add(key)
        log.info("[cache] pressure handler registered with ResourceMonitor")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")

    @bounded_cache(maxsize=8, name="demo.square")
    def square(n: int) -> int:
        return n * n

    for i in range(20):
        square(i % 4)
    print("stats after population:")
    for s in cache_stats():
        print(" ", s)

    print("resizing to 2:")
    square.cache_resize(2)
    for s in cache_stats():
        print(" ", s)

    print("clearing all:")
    for c in all_caches():
        c.cache_clear()
    for s in cache_stats():
        print(" ", s)
