"""A.E.R.I.S — JARVIS v6 PyQt5 GUI.

A native PyQt5 port of the `new-latest-ui` JARVIS v6 web design: the same
arc-reactor core, floating dock, mission-control chat, command palette,
proactive notifications, boot/onboarding flow and page router — wired to the
real :class:`core.main_engine.JarvisMainEngine` via the proven worker threads
from :mod:`ui.jarvis_v31.main_window`.

This is a *new* surface; the older `ui/jarvis_v31` and `ui/aeris_v4` GUIs are
left fully intact so the previous versions remain launchable for comparison.

Launch with::

    python run_aeris_v6.py
"""

__all__ = ["launch"]


def launch(splash=None):
    # Imported lazily so merely importing the package doesn't pull in PyQt5.
    from ui.aeris_v6.app import launch as _launch
    return _launch(splash=splash)
