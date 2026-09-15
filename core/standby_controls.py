"""Control surface for the background standby daemon.

Because ``--standby`` runs windowless, the user needs a small handle to it:
pause/resume listening (e.g. during a meeting), see whether the brain is dormant
or active, and quit. ``StandbyControls`` is that handle — pure delegation to the
daemon, fully unit-tested. ``run_tray`` is a thin, optional system-tray adapter
(needs ``pystray`` + a desktop) that binds a menu to these controls; its menu is
built from ``menu_spec`` so the *contents* are testable even though the tray
rendering is not.
"""

from __future__ import annotations

from typing import Optional


class StandbyControls:
    """User-facing controls over a running ``StandbyDaemon``."""

    def __init__(self, daemon, stats=None, health=None) -> None:
        self._d = daemon
        self._stats = stats   # optional StandbyStats for the duty cycle
        self._health = health  # optional StandbyHealth for the full diagnostic

    # ---- actions ----------------------------------------------------- #

    def pause(self) -> None:
        self._d.pause_listening()

    def resume(self) -> None:
        self._d.resume_listening()

    def toggle_pause(self) -> bool:
        """Flip listening on/off. Returns the new *paused* state."""
        if self._d.is_paused:
            self._d.resume_listening()
        else:
            self._d.pause_listening()
        return self._d.is_paused

    def quit(self) -> None:
        self._d.stop()

    # ---- observation ------------------------------------------------- #

    @property
    def is_paused(self) -> bool:
        return self._d.is_paused

    def status(self) -> dict:
        state = self._d.brain_state
        brain = getattr(state, "value", str(state))
        out = {
            "listening": not self._d.is_paused,
            "paused": self._d.is_paused,
            "brain": brain,
            "running": self._d.running,
        }
        if self._stats is not None:
            out["duty"] = self._stats.snapshot()
        if self._health is not None:
            out["health"] = self._health.report()
        return out

    def status_line(self) -> str:
        # The health line is the richest single line (verdict + breaker + duty),
        # so prefer it when a health view is wired.
        if self._health is not None:
            paused = " · paused" if self._d.is_paused else ""
            return self._health.report_line() + paused
        s = self.status()
        listen = "paused" if s["paused"] else "listening"
        line = f"AERIS · {listen} · brain {s['brain']}"
        if "duty" in s:
            line += f" · {s['duty']['dormant_pct']:.0f}% dormant"
        return line

    # ---- tray menu (data the tray renders) --------------------------- #

    def menu_spec(self) -> list:
        """A simple, renderer-agnostic menu description."""
        return [
            {"id": "toggle", "label": "Resume listening" if self.is_paused
             else "Pause listening", "checked": not self.is_paused},
            {"id": "status", "label": self.status_line(), "enabled": False},
            {"id": "quit", "label": "Quit AERIS"},
        ]

    def invoke(self, item_id: str) -> None:
        """Dispatch a menu id to its action (used by the tray adapter)."""
        if item_id == "toggle":
            self.toggle_pause()
        elif item_id == "quit":
            self.quit()
        # "status" is inert


def run_tray(controls: StandbyControls, *, icon_name: str = "AERIS") -> None:  # pragma: no cover
    """Optional system-tray adapter. Requires ``pystray`` + Pillow + a desktop.

    Not unit-tested (it blocks on the tray event loop and needs a display); the
    menu it shows is built from ``controls.menu_spec`` which *is* tested.
    """
    try:
        import pystray
        from PIL import Image, ImageDraw
    except Exception as e:
        raise RuntimeError(
            "system tray needs 'pystray' and 'Pillow' installed"
        ) from e

    def _image():
        img = Image.new("RGB", (64, 64), (18, 18, 24))
        d = ImageDraw.Draw(img)
        d.ellipse((16, 16, 48, 48), fill=(109, 74, 255))
        return img

    def _build_menu():
        items = []
        for spec in controls.menu_spec():
            iid = spec["id"]
            if iid == "quit":
                items.append(pystray.MenuItem(
                    spec["label"], lambda icon, _: (controls.quit(), icon.stop())))
            elif iid == "toggle":
                items.append(pystray.MenuItem(
                    spec["label"], lambda icon, _: (controls.toggle_pause(),
                                                    icon.update_menu())))
            else:
                items.append(pystray.MenuItem(spec["label"], None, enabled=False))
        return pystray.Menu(*items)

    icon = pystray.Icon(icon_name, _image(), "AERIS standby",
                        menu=pystray.Menu(lambda: _build_menu()))
    icon.run()
