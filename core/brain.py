"""JarvisBrain — top-level orchestrator for the assistant pipeline.

Checkpoint 1 wires only the intent classifier. Subsequent checkpoints will add:
    C3  sentiment    — `core.sentiment.SentimentAnalyzer`
    C4  memory       — `core.memory.UserMemory`  (user_facts injected before classify)
    C5  conversation — `core.conversation.ConversationHistory`
    C6  llm_chat     — `core.llm_chat.LLMChat`        (chit-chat fallback)
    C7  feedback     — `core.feedback.FeedbackStore`  (per-intent thresholds)
    C8  disambig     — `core.disambiguator.Disambiguator`
    C2  entities     — handled at main_engine layer, not here
"""

from __future__ import annotations

import logging
import os

from core.intent_classifier import IntentClassifier, Prediction

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class JarvisBrain:
    """Front door for the brain pipeline.

    Until C9 lands, the legacy `predict_intent(text) -> list[dict]` shape is
    preserved as a compatibility shim so `main_engine.py` keeps working.
    The new `predict(text) -> Prediction` is the API for C9+.
    """

    def __init__(self):
        log.info("[Brain] Initialising...")
        self.classifier = IntentClassifier(
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
            models_dir=os.path.join(_ROOT, "data", "models"),
        )
        log.info("[Brain] Ready.")

    # New API (C9+) -----------------------------------------------------
    def predict(self, text: str, threshold: float = 0.5) -> Prediction:
        return self.classifier.predict(text, threshold=threshold)

    # Legacy compat shim — remove after C9 main_engine rewire ----------
    def predict_intent(self, text: str) -> list[dict]:
        p = self.classifier.predict(text)
        if p.intent is None:
            return []
        return [{"intent": p.intent, "probability": f"{p.confidence:.3f}"}]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    brain = JarvisBrain()
    for q in ["chrome kholo", "weather batao", "screenshot lo zara"]:
        print(brain.predict(q))
