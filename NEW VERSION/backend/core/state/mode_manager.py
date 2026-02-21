# BACKEND/core/state/mode_manager.py
from BACKEND.core.brain.state_manager import AudioState


class ModeManager:
    """Proxy to StateManager so modes stay consistent."""

    def __init__(self, state_manager=None):
        self.state_manager = state_manager
        self.current_mode = "idle"

    def set_mode(self, mode: str):
        self.current_mode = mode
        if self.state_manager:
            try:
                self.state_manager.set_state(AudioState(mode))
            except Exception:
                pass

    def get_mode(self) -> str:
        if self.state_manager:
            return self.state_manager.get_mode()
        return self.current_mode

    def is_idle(self) -> bool:
        if self.state_manager:
            return self.state_manager.is_idle()
        return self.current_mode == "idle"
