"""JarvisBrain — thin wrapper around IntentClassifier.

Currently delegates `predict()` directly. Kept as its own class for two reasons:

    1. Future expansion — pre/post hooks (instrumentation, A/B testing) live
       here without polluting the classifier.
    2. Stable import surface — `main_engine` imports `JarvisBrain`, not the
       classifier. If the classifier internals are swapped (e.g. FAISS HNSW
       at large scale) the rest of the codebase doesn't change.
"""

from __future__ import annotations

import logging
import os

from core.intent_classifier import IntentClassifier, Prediction

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class JarvisBrain:
    def __init__(self, *, lazy: bool = False):
        log.info("[Brain] Initialising...")
        # Build the classifier shell without doing the heavy load. In
        # eager mode (``lazy=False``, the default), drive both phases
        # immediately so callers see a fully-initialised brain.
        self.classifier = IntentClassifier(
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
            models_dir=os.path.join(_ROOT, "data", "models"),
            lazy=True,
        )
        if not lazy:
            self.load_encoder()
            self.build_or_load_index()
            log.info("[Brain] Ready.")

    def load_encoder(self) -> None:
        """Phase A — heavy: SentenceTransformer init."""
        self.classifier.load_encoder()

    def build_or_load_index(self) -> None:
        """Phase B — cache hit fast, rebuild slow."""
        self.classifier.build_or_load_index()

    def predict(self, text: str, threshold: float = 0.5) -> Prediction:
        return self.classifier.predict(text, threshold=threshold)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    brain = JarvisBrain()
    for q in ["chrome kholo", "weather batao", "screenshot lo zara"]:
        print(brain.predict(q))
