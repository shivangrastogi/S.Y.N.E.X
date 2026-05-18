"""JarvisBrain — combined neural + k-NN intent router.

Architecture
------------
Two classifiers live side-by-side:

1. ``NeuralIntentClassifier`` (fine-tuned XLM-R, ``core/intent_model.py``).
   Loaded only when a trained model exists at ``data/models/intent_neural/``
   AND its saved ``intents_hash`` matches the live ``intents.json``. Primary
   router when present — it understands paraphrase, code-mix, and word order
   variation that pure k-NN cosine misses.

2. ``IntentClassifier`` (sentence-encoder + k-NN, ``core/intent_classifier.py``).
   Always loaded — the safety net. Used:
     - when no neural model is trained yet (clean install, no breakage),
     - when the neural model's confidence is below the per-intent threshold,
     - as a top-3 enrichment source so the disambiguator sees nearest
       neighbours the neural classifier may not have considered.

Both expose ``predict(text) -> Prediction``; the orchestration here decides
which result to surface and how the top-3 is merged.

Retrain workflow
----------------
    python -m core.train_intent

After it finishes, restart AERIS. The brain detects the new model,
verifies its hash matches the live intents.json, and switches over.
If you edit intents.json *without* retraining, the hash mismatch flips
the brain back to pure k-NN until you retrain.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

from core.intent_classifier import IntentClassifier, Prediction
from core.intent_model import NeuralIntentClassifier

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Confidence below this → neural is "unsure", we cross-check k-NN.
# Soft floor; the feedback bandit's per-intent threshold (feedback.py)
# is the authoritative gate downstream.
_NEURAL_LOW_CONF = 0.55

# Idle-unload: if no predict() in this many seconds AND resource pressure
# is at least WARNING, drop the in-RAM encoder + neural model. Reloads
# transparently on the next predict() (with a noticeable ~3s latency the
# user will see exactly once, then the model stays hot until idle again).
_IDLE_UNLOAD_S = 5 * 60


class JarvisBrain:
    def __init__(self, *, lazy: bool = False):
        log.info("[Brain] Initialising...")
        self.classifier = IntentClassifier(
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
            models_dir=os.path.join(_ROOT, "data", "models"),
            lazy=True,
        )
        self.neural = NeuralIntentClassifier(
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
        )
        self._neural_active = False

        # Idle-unload bookkeeping. ``_last_predict_ts`` is the wall-clock
        # of the most recent predict() call; the ResourceMonitor pressure
        # callback consults it before unloading.
        self._last_predict_ts: float = time.monotonic()
        self._unload_lock = threading.RLock()
        self._encoder_loaded = False
        self._neural_loaded = False
        self._idle_unload_s = _IDLE_UNLOAD_S

        if not lazy:
            self.load_encoder()
            self.load_neural_model()
            self.build_or_load_index()
            log.info("[Brain] Ready.")

    # ------------------------------------------------------------------ #
    #  Three-phase boot (mirrors IntentClassifier so the GUI can paint   #
    #  progress between chunks)                                            #
    # ------------------------------------------------------------------ #

    def load_encoder(self) -> None:
        """Phase A1 — sentence encoder only.

        Split from neural-model load so the boot pipeline can yield progress
        between the two heavy loads (sentence-transformers ~5-10s + neural
        transformer ~5-10s would otherwise look like one ~17s freeze on the
        progress bar).
        """
        with self._unload_lock:
            self.classifier.load_encoder()
            self._encoder_loaded = True

    def load_neural_model(self) -> None:
        """Phase A2 — load the fine-tuned neural intent classifier if present.

        Safe to call even when no model is on disk or its hash has drifted —
        the brain just stays on the k-NN router in that case.
        """
        with self._unload_lock:
            if self.neural.is_trained():
                log.info("[Brain] Trained neural classifier present; loading...")
                if self.neural.load():
                    self._neural_active = True
                    self._neural_loaded = True
                    log.info("[Brain] Neural classifier ACTIVE (primary router).")
                else:
                    log.warning("[Brain] Neural load failed — falling back to k-NN only.")
            elif self.neural.is_present():
                log.info("[Brain] Neural model on disk but intents.json hash drifted — "
                         "using k-NN. Run `python -m core.train_intent` to refresh.")
            else:
                log.info("[Brain] No neural model yet — using k-NN. "
                         "Train one with `python -m core.train_intent`.")

    # ------------------------------------------------------------------ #
    #  Idle-unload (Phase 3b — lazy paging of large model weights)        #
    # ------------------------------------------------------------------ #

    def try_unload_idle(self) -> bool:
        """Drop encoder + neural model from RAM if idle long enough.

        Returns True if anything was unloaded. Safe to call from any
        thread (locked). The next ``predict()`` will transparently
        reload, costing ~3s of latency exactly once.
        """
        with self._unload_lock:
            idle_for = time.monotonic() - self._last_predict_ts
            if idle_for < self._idle_unload_s:
                return False
            if not (self._encoder_loaded or self._neural_loaded):
                return False
            log.info("[Brain] idle %.0fs → unloading models to reclaim RAM",
                     idle_for)
            # Drop the SentenceTransformer + sklearn index — keep the
            # labels so we can rebuild quickly. The objects become
            # garbage; Python's GC reclaims their tensors.
            try:
                self.classifier.encoder = None
                self.classifier.nn = None
                self.classifier.embeddings = None
                self._encoder_loaded = False
            except Exception:
                pass
            try:
                self.neural.model = None
                self.neural.tokenizer = None
                self._neural_loaded = False
                self._neural_active = False
            except Exception:
                pass
            # Hint the allocator to give pages back to the OS.
            import gc
            gc.collect()
            return True

    def _ensure_loaded(self) -> None:
        """Reload encoder + neural model if a previous idle-unload dropped them."""
        with self._unload_lock:
            if not self._encoder_loaded:
                log.info("[Brain] cold predict — reloading encoder")
                self.classifier.load_encoder()
                self.classifier.build_or_load_index()
                self._encoder_loaded = True
            if not self._neural_loaded and self.neural.is_trained():
                log.info("[Brain] cold predict — reloading neural model")
                if self.neural.load():
                    self._neural_loaded = True
                    self._neural_active = True

    def build_or_load_index(self) -> None:
        """Phase B — k-NN index cache load or rebuild."""
        self.classifier.build_or_load_index()

    # ------------------------------------------------------------------ #
    #  Predict                                                            #
    # ------------------------------------------------------------------ #

    def predict(self, text: str, threshold: float = 0.5) -> Prediction:
        """Combined neural-first / k-NN-fallback prediction.

        Rules:
          * No trained neural model → pure k-NN.
          * Neural confidence ≥ _NEURAL_LOW_CONF → trust neural. Merge
            its top3 with k-NN's top-1 (if a different intent) so the
            disambiguator gets the broader picture.
          * Neural confidence < _NEURAL_LOW_CONF → defer to k-NN, but
            merge neural's top-1 into the surfaced top3 as a second
            opinion for the disambiguator.
        """
        # Always update activity timestamp + warm any unloaded models.
        # ``_ensure_loaded`` is cheap when models are already in RAM.
        self._ensure_loaded()
        self._last_predict_ts = time.monotonic()

        if not self._neural_active:
            return self.classifier.predict(text, threshold=threshold)

        neural_pred = self.neural.predict(text, threshold=threshold)
        knn_pred = self.classifier.predict(text, threshold=threshold)

        if neural_pred.confidence >= _NEURAL_LOW_CONF and neural_pred.intent:
            return _with_merged_top3(neural_pred, knn_pred)
        # Neural unsure — k-NN drives.
        return _with_merged_top3(knn_pred, neural_pred)


def _with_merged_top3(primary: Prediction, secondary: Prediction) -> Prediction:
    """Return ``primary`` but with ``secondary``'s leading distinct intent
    grafted into top3 (capped at 3) so the disambiguator gets both views.

    Order is preserved — secondary entries only ever fill slots not already
    occupied by primary. Probabilities aren't renormalised; the disambiguator
    only uses the *order* and the absolute top-1 / top-2 gap.
    """
    if not secondary or not secondary.top3:
        return primary
    seen = {label for label, _ in primary.top3}
    merged = list(primary.top3)
    for label, score in secondary.top3:
        if label in seen:
            continue
        merged.append((label, score))
        seen.add(label)
        if len(merged) >= 3:
            break
    return Prediction(
        intent=primary.intent,
        confidence=primary.confidence,
        top3=merged[:3],
        raw_text=primary.raw_text,
        normalized_text=primary.normalized_text,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    brain = JarvisBrain()
    for q in ["chrome kholo", "weather batao", "screenshot lo zara",
              "youtube open kro in brave browser", "open youtube website"]:
        print(brain.predict(q))
