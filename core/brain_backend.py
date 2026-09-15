"""Brain backend selector — one seam, two implementations
(docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md, P1 cutover).

``get_brain_backend()`` returns the brain the GUI should talk to:

  * ``AERIS_SPLIT_BRAIN`` truthy → a ``RemoteBrain`` (torch runs in a CHILD
    process; the GUI process stays ML-free → the 0xC0000374 crash class can't
    happen in the GUI). Call ``.start()`` before use.
  * otherwise → the in-process ``JarvisMainEngine`` wrapped in a thin adapter
    that adds ``start()/is_ready()/poll_events()`` and **transparently
    delegates every other attribute** (``_speak``, ``dialogue``, ``feedback``,
    ``agent`` …) to the engine, so nothing about today's GUI changes.

Both expose the uniform surface the GUI's turn path needs:
``process_text(text)->str``, ``last_dispatch``, ``start()``, ``is_ready()``,
``poll_events()``. So the cutover is a one-line swap behind an env flag.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Optional


def use_split_brain(flag: Optional[Any] = None) -> bool:
    v = flag if flag is not None else os.environ.get("AERIS_SPLIT_BRAIN", "")
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _default_remote():
    from core.remote_brain import RemoteBrain
    return RemoteBrain()


def _default_engine():
    from core.main_engine import JarvisMainEngine
    return JarvisMainEngine(stt="SKIP", tts="SKIP", verbose=False)


class InProcessBackend:
    """Wrap a JarvisMainEngine so it matches the RemoteBrain surface, while
    delegating everything else to the engine (fully transparent in-process)."""

    def __init__(self, engine):
        # stored under a private name so __getattr__ never recurses on it
        object.__setattr__(self, "_engine", engine)

    def start(self, ready_timeout: float = 0.0) -> bool:
        return True                      # already constructed

    def is_ready(self) -> bool:
        return True

    def poll_events(self) -> list:
        return []                        # in-process proactivity uses its own path

    def process_text(self, text: str) -> str:
        return self._engine.process_text(text)

    @property
    def last_dispatch(self):
        return getattr(self._engine, "last_dispatch", None)

    def __getattr__(self, name: str):
        # Delegate any other attribute (_speak, dialogue, feedback, agent, …).
        return getattr(object.__getattribute__(self, "_engine"), name)


def get_brain_backend(flag: Optional[Any] = None,
                      engine_builder: Optional[Callable] = None,
                      remote_builder: Optional[Callable] = None):
    """Return the selected brain backend. Injectable builders for testing."""
    if use_split_brain(flag):
        return (remote_builder or _default_remote)()
    return InProcessBackend((engine_builder or _default_engine)())
