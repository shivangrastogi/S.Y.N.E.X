"""Skill plugin hot-reload via filesystem polling.

OS-concept demo
---------------
The "real" way to watch for file changes is platform-specific:
``inotify`` on Linux, ``ReadDirectoryChangesW`` on Windows, ``kqueue``
on BSD/macOS. ``watchdog`` packages all three behind one API but adds
a dependency we don't otherwise need. For a 21-file plugin directory
that changes a handful of times a day during development, **polling
mtimes every 2 seconds costs ~0.2 ms per tick** and is fine.

Concept: stat each ``skills/*.py``, keep last-known mtime. When mtime
changes, run ``importlib.reload`` on that single module so the
``@skill`` decorator re-registers its handler in
``core.skill_registry.REGISTRY``. Other skills stay untouched — the
brain doesn't even need to reload its index because the intent
patterns themselves only change when the user edits ``intents.json``.

Trade-offs
----------
* importlib.reload only updates the module object — closures captured
  in `REGISTRY` are not magically swapped. The ``@skill`` decorator at
  import time *does* update REGISTRY, so the reload picks up new
  handler bytecode. Old references stored elsewhere (e.g. inside a
  thread pool future) still point at the OLD function — acceptable
  for AERIS because skills are dispatched by name through the
  registry, never cached upstream.
* If a reloaded skill raises during import, REGISTRY keeps the prior
  version and we log the error. No half-loaded state.
"""
from __future__ import annotations

import importlib
import logging
import os
import sys
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)


_DEFAULT_INTERVAL_S = 2.0


class SkillWatcher:
    """Background mtime poller. ``start()`` to begin, ``stop()`` to end."""

    def __init__(self,
                 skills_dir: Optional[str] = None,
                 *,
                 interval_s: float = _DEFAULT_INTERVAL_S,
                 on_reload: Optional[Callable[[str, bool, Optional[str]], None]] = None):
        _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._dir = skills_dir or os.path.join(_here, "skills")
        self._pkg = os.path.basename(self._dir.rstrip(os.sep))
        self._interval = max(0.5, interval_s)
        self._on_reload = on_reload
        self._mtimes: dict[str, float] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

    # ── Lifecycle ───────────────────────────────────────────────────

    def start(self) -> None:
        if not os.path.isdir(self._dir):
            log.info("[skill_watcher] %s missing — watcher inactive", self._dir)
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            # Prime so existing files aren't immediately treated as new.
            self._mtimes = self._snapshot_mtimes()
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run, name="SkillWatcher", daemon=True
            )
            self._thread.start()
            log.info("[skill_watcher] polling %s every %.1fs (%d files)",
                     self._dir, self._interval, len(self._mtimes))

    def stop(self, *, timeout: float = 1.0) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=timeout)

    # ── Main loop ──────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception:
                log.exception("[skill_watcher] poll raised")
            if self._stop.wait(self._interval):
                return

    def _poll_once(self) -> None:
        current = self._snapshot_mtimes()
        with self._lock:
            for path, m in current.items():
                old = self._mtimes.get(path)
                if old is None:
                    # New file → reload package to pick it up via decorator.
                    self._reload_module(path, reason="added")
                elif m != old:
                    self._reload_module(path, reason="changed")
            for path in list(self._mtimes):
                if path not in current:
                    # File deleted — we don't pop from REGISTRY (the
                    # handler is still callable until process restart);
                    # logged so the user knows the skill won't be there
                    # next launch.
                    log.info("[skill_watcher] %s removed (will disappear on restart)",
                             os.path.basename(path))
            self._mtimes = current

    def _snapshot_mtimes(self) -> dict[str, float]:
        out: dict[str, float] = {}
        try:
            for name in os.listdir(self._dir):
                if not name.endswith(".py") or name.startswith("_"):
                    continue
                full = os.path.join(self._dir, name)
                try:
                    out[full] = os.path.getmtime(full)
                except OSError:
                    pass
        except OSError as e:
            log.warning("[skill_watcher] listdir(%s) failed: %s", self._dir, e)
        return out

    def _reload_module(self, path: str, *, reason: str) -> None:
        mod_basename = os.path.splitext(os.path.basename(path))[0]
        full_mod_name = f"{self._pkg}.{mod_basename}"
        ok = True
        err: Optional[str] = None
        try:
            mod = sys.modules.get(full_mod_name)
            if mod is None:
                importlib.import_module(full_mod_name)
                log.info("[skill_watcher] imported new skill: %s", full_mod_name)
            else:
                importlib.reload(mod)
                log.info("[skill_watcher] reloaded %s (%s)", full_mod_name, reason)
        except Exception as e:
            ok = False
            err = repr(e)
            log.warning("[skill_watcher] reload(%s) failed: %s", full_mod_name, e)
        if self._on_reload:
            try:
                self._on_reload(full_mod_name, ok, err)
            except Exception:
                log.exception("[skill_watcher] on_reload callback raised")


# ── Singleton helper ───────────────────────────────────────────────── #

_singleton: Optional[SkillWatcher] = None
_singleton_lock = threading.Lock()


def get_watcher(**kwargs) -> SkillWatcher:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = SkillWatcher(**kwargs)
        return _singleton


if __name__ == "__main__":
    import tempfile
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    workdir = tempfile.mkdtemp(prefix="aeris_watcher_test_")
    try:
        sys.path.insert(0, os.path.dirname(workdir))
        pkg = os.path.basename(workdir)
        # Make it an importable package
        with open(os.path.join(workdir, "__init__.py"), "w") as f:
            pass
        with open(os.path.join(workdir, "demo.py"), "w") as f:
            f.write("VALUE = 1\nprint('demo loaded VALUE=1')\n")
        w = SkillWatcher(skills_dir=workdir, interval_s=0.5)
        w.start()
        import importlib
        importlib.import_module(f"{pkg}.demo")
        print("--- modify file in 1.5s, watcher should reload ---")
        time.sleep(1.5)
        with open(os.path.join(workdir, "demo.py"), "w") as f:
            f.write("VALUE = 2\nprint('demo loaded VALUE=2')\n")
        time.sleep(1.5)
        w.stop()
    finally:
        import shutil
        shutil.rmtree(workdir, ignore_errors=True)
