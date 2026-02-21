# BACKEND/core/brain/intent_router.py
from BACKEND.core.brain.action_router import ActionRouter

class IntentRouter:
    def __init__(self, speech):
        self.speech = speech
        self.router = ActionRouter(speech)

    def route(self, intent: str, text: str = "") -> str:
        """Deprecated: use ActionRouter.handle instead."""
        return self.router.handle(intent, text or intent)
