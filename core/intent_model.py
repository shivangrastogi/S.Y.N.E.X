"""Neural intent classifier — fine-tuned multilingual transformer inference.

Drop-in replacement for the k-NN cosine head in ``core/intent_classifier.py``.
Returns the same ``Prediction`` dataclass so callers don't care which one
they got. Loaded by ``core/brain.py`` and combined with the k-NN classifier
(neural primary, k-NN as fallback when no trained model is on disk).

The model lives at ``data/models/intent_neural/``, produced by
``python -m core.train_intent``. This module never trains — it only loads.

Hash-keyed safety: ``is_trained()`` returns True only when the saved
intents-hash matches the live intents.json. If you edit intents.json
without retraining, the brain transparently falls back to k-NN.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Optional

# Same OpenMP guard the training script uses — torch's MKL/OpenMP and
# the GUI's Qt build occasionally ship conflicting libiomp5md.dll on
# Windows. Set before torch is imported to be safe.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import numpy as np
import torch
import torch.nn.functional as F

from core.intent_classifier import Prediction
from core.normalizer import HinglishNormalizer

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DIR = os.path.join(_ROOT, "data", "models", "intent_neural")
_TOP_K = 3


class NeuralIntentClassifier:
    """Fine-tuned transformer classifier — same predict() shape as IntentClassifier.

    Boot order
    ----------
    1. ``__init__`` reads metadata only (cheap). Doesn't load weights.
    2. ``load()`` brings the model + tokenizer into RAM. Call once at boot.
    3. ``predict()`` is the hot path; ~80-150 ms CPU on xlm-roberta-base.

    The two-phase init matches ``IntentClassifier`` so JarvisBrain can show
    progress between phases in the GUI.
    """

    def __init__(self, model_dir: str = _DEFAULT_DIR,
                 intents_path: Optional[str] = None):
        self.model_dir = model_dir
        self.intents_path = intents_path or os.path.join(_ROOT, "data", "intents.json")
        self._model_subdir = os.path.join(model_dir, "model")
        self._tok_subdir = os.path.join(model_dir, "tokenizer")
        self._labels_path = os.path.join(model_dir, "labels.json")
        self._metadata_path = os.path.join(model_dir, "metadata.json")

        self.normalizer = HinglishNormalizer()
        self.model = None
        self.tokenizer = None
        self.id2label: dict[int, str] = {}
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._max_len = 48

        # Read just metadata up front so is_trained() works pre-load.
        self._saved_hash: Optional[str] = None
        if os.path.exists(self._labels_path):
            try:
                with open(self._labels_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._saved_hash = data.get("intents_hash")
                # JSON keys are always strings — coerce back to int.
                self.id2label = {int(k): v for k, v in data.get("id2label", {}).items()}
            except Exception as e:
                log.warning("[NeuralIntent] could not read labels.json: %s", e)
        if os.path.exists(self._metadata_path):
            try:
                with open(self._metadata_path, "r", encoding="utf-8") as f:
                    self._max_len = int(json.load(f).get("max_len", self._max_len))
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  Availability checks                                                #
    # ------------------------------------------------------------------ #

    def is_present(self) -> bool:
        """True iff a trained model exists on disk (hash may be stale)."""
        return (os.path.isdir(self._model_subdir)
                and os.path.isdir(self._tok_subdir)
                and os.path.exists(self._labels_path))

    def is_trained(self) -> bool:
        """True iff trained AND the saved intents_hash matches the live file.

        If a user edits intents.json without retraining, this flips to False
        and the brain falls back to k-NN — so we never serve predictions
        from a model that doesn't know the current intent set.
        """
        if not self.is_present():
            return False
        if not self._saved_hash:
            return False
        try:
            from core.intent_classifier import IntentClassifier
            tmp = IntentClassifier(self.intents_path,
                                   os.path.join(_ROOT, "data", "models"),
                                   lazy=True)
            return tmp._intents_hash() == self._saved_hash
        except Exception as e:
            log.warning("[NeuralIntent] hash check failed: %s", e)
            return False

    # ------------------------------------------------------------------ #
    #  Load                                                               #
    # ------------------------------------------------------------------ #

    def load(self) -> bool:
        """Bring weights + tokenizer into RAM. Returns False on any error."""
        if not self.is_present():
            return False
        try:
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )
            log.info("[NeuralIntent] loading model from %s", self._model_subdir)
            self.tokenizer = AutoTokenizer.from_pretrained(self._tok_subdir)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self._model_subdir
            ).to(self._device)
            self.model.eval()
            return True
        except Exception as e:
            log.error("[NeuralIntent] load failed: %s", e)
            self.model = None
            self.tokenizer = None
            return False

    # ------------------------------------------------------------------ #
    #  Predict                                                            #
    # ------------------------------------------------------------------ #

    def predict(self, text: str, threshold: float = 0.5) -> Prediction:
        """Same shape as IntentClassifier.predict — see Prediction dataclass.

        Confidence is the softmax probability of the winning class
        (well-calibrated under cross-entropy training). top3 is the
        renormalised top-3 of the softmax distribution.
        """
        if not text or not text.strip():
            return Prediction(intent=None, confidence=0.0,
                              raw_text=text or "", normalized_text="")
        if self.model is None or self.tokenizer is None:
            # Caller should check is_trained() first; return a benign empty
            # prediction so a misuse doesn't crash the pipeline.
            return Prediction(intent=None, confidence=0.0,
                              raw_text=text, normalized_text="")

        normalized = self.normalizer.clean(text)
        enc = self.tokenizer(
            normalized,
            padding="max_length",
            truncation=True,
            max_length=self._max_len,
            return_tensors="pt",
        )
        ids = enc["input_ids"].to(self._device)
        mask = enc["attention_mask"].to(self._device)
        with torch.no_grad():
            logits = self.model(input_ids=ids, attention_mask=mask).logits[0]
            probs = F.softmax(logits, dim=-1).cpu().numpy()

        k = min(_TOP_K, len(probs))
        top_idx = np.argsort(probs)[::-1][:k]
        top3 = [(self.id2label[int(i)], float(probs[i])) for i in top_idx]
        winner = top3[0][0]
        confidence = round(float(probs[top_idx[0]]), 4)

        if confidence < threshold:
            return Prediction(intent=None, confidence=confidence, top3=top3,
                              raw_text=text, normalized_text=normalized)
        return Prediction(intent=winner, confidence=confidence, top3=top3,
                          raw_text=text, normalized_text=normalized)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    clf = NeuralIntentClassifier()
    if not clf.is_present():
        print("No trained model at", _DEFAULT_DIR)
        print("Run:  python -m core.train_intent")
        sys.exit(0)
    if not clf.is_trained():
        print("Trained model present but intents.json hash has drifted.")
        print("Retrain:  python -m core.train_intent")
        sys.exit(0)
    if not clf.load():
        print("Failed to load model.")
        sys.exit(1)
    tests = [
        "chrome kholo",
        "notepad band karo",
        "weather batao",
        "screenshot le lo",
        "youtube pe arijit ka gaana chala do",
        "open edge",
        "youtube open kro in brave browser",
        "open youtube website",
    ]
    for q in tests:
        p = clf.predict(q)
        print(f"  {q!r:48s} -> {str(p.intent)!r:18s} "
              f"conf={p.confidence:.3f}  top3={p.top3}")
