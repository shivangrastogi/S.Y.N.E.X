"""Multilingual intent classifier — sentence encoder + k-NN over labelled patterns.

Replaces the previous Keras dense head plus standalone trainer. There is no
training step: the sentence encoder is frozen, and "training" reduces to
embedding all patterns in `intents.json` and fitting a NearestNeighbors index.

The cached index is keyed by the MD5 hash of `intents.json`, so any edit to
that file triggers an automatic rebuild on next boot (still sub-10s for ~300
patterns).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors

from core.normalizer import HinglishNormalizer

log = logging.getLogger(__name__)

ENCODER_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 5


@dataclass
class Prediction:
    """Structured result returned by `IntentClassifier.predict`."""
    intent: Optional[str]
    confidence: float
    top3: list[tuple[str, float]] = field(default_factory=list)
    raw_text: str = ""
    normalized_text: str = ""

    def is_confident(self, threshold: float = 0.5) -> bool:
        return self.intent is not None and self.confidence >= threshold


class IntentClassifier:
    """Multilingual encoder + k-NN intent router.

    Public methods:
        predict(text, threshold=0.5) -> Prediction
        rebuild()                     -> force re-embed and re-cache
    """

    def __init__(self, intents_path: str, models_dir: str, *, lazy: bool = False):
        self.intents_path = intents_path
        self.models_dir = models_dir
        self.index_path = os.path.join(models_dir, "intent_index.pkl")
        self.metadata_path = os.path.join(models_dir, "intent_metadata.json")

        os.makedirs(self.models_dir, exist_ok=True)

        self.normalizer = HinglishNormalizer()
        self.encoder: Optional[SentenceTransformer] = None
        self.nn: Optional[NearestNeighbors] = None
        self.labels: list[str] = []
        self.embeddings: Optional[np.ndarray] = None

        # Eager mode (default): drive both sub-phases now so callers see
        # a fully-initialised classifier. Lazy mode is for the GUI worker
        # which paints progress between the two phases.
        if not lazy:
            self.load_encoder()
            self.build_or_load_index()

    # ------------------------------------------------------------------ #
    #  Boot — split into two callable sub-phases                          #
    # ------------------------------------------------------------------ #

    def load_encoder(self) -> None:
        """Phase A — load the sentence encoder.

        Dominant cost on cold boot (multi-second SentenceTransformer
        init). Idempotent: subsequent calls are no-ops.
        """
        self._ensure_encoder()

    def build_or_load_index(self) -> None:
        """Phase B — load the cached k-NN index, or rebuild it.

        Cheap when the intents.json hash matches the cached metadata;
        a few seconds when it has to re-embed every pattern. Requires
        that ``load_encoder`` has already been called.
        """
        cached_hash = self._cached_hash()
        current_hash = self._intents_hash()

        if cached_hash == current_hash and os.path.exists(self.index_path):
            log.info("[IntentClassifier] Loading cached index.")
            try:
                self._load_cache()
                return
            except Exception as e:
                log.warning(f"[IntentClassifier] Cache load failed ({e}); rebuilding.")

        log.info("[IntentClassifier] Rebuilding index from intents.json...")
        self._build_index()
        self._save_cache(current_hash)

    # ------------------------------------------------------------------ #
    #  Hashing & caching                                                  #
    # ------------------------------------------------------------------ #

    def _intents_hash(self) -> str:
        with open(self.intents_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def _cached_hash(self) -> Optional[str]:
        if not os.path.exists(self.metadata_path):
            return None
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                return json.load(f).get("intents_hash")
        except Exception:
            return None

    def _save_cache(self, intents_hash: str) -> None:
        with open(self.index_path, "wb") as f:
            pickle.dump(
                {
                    "embeddings": self.embeddings,
                    "labels": self.labels,
                    "encoder_name": ENCODER_NAME,
                },
                f,
            )
        meta = {
            "intents_hash": intents_hash,
            "encoder_name": ENCODER_NAME,
            "num_patterns": len(self.labels),
            "num_classes": len(set(self.labels)),
            "built_at": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        log.info(f"[IntentClassifier] Index cached → {self.index_path}")

    def _load_cache(self) -> None:
        with open(self.index_path, "rb") as f:
            blob = pickle.load(f)
        if blob.get("encoder_name") != ENCODER_NAME:
            log.warning("[IntentClassifier] Cached encoder differs; rebuilding.")
            self._build_index()
            self._save_cache(self._intents_hash())
            return
        self.embeddings = np.asarray(blob["embeddings"], dtype=np.float32)
        self.labels = list(blob["labels"])
        self._ensure_encoder()
        n_neighbors = min(TOP_K, len(self.labels))
        self.nn = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine")
        self.nn.fit(self.embeddings)

    # ------------------------------------------------------------------ #
    #  Index build                                                        #
    # ------------------------------------------------------------------ #

    def _ensure_encoder(self) -> None:
        if self.encoder is None:
            log.info(f"[IntentClassifier] Loading encoder: {ENCODER_NAME}")
            self.encoder = SentenceTransformer(ENCODER_NAME)

    def _load_intents(self) -> dict:
        with open(self.intents_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_index(self) -> None:
        self._ensure_encoder()
        intents = self._load_intents()

        patterns: list[str] = []
        labels: list[str] = []
        for intent_name, cfg in intents.items():
            for pattern in cfg.get("patterns", []):
                patterns.append(self.normalizer.clean(pattern))
                labels.append(intent_name)

        if not patterns:
            raise RuntimeError("intents.json contains no patterns.")

        log.info(
            f"[IntentClassifier] Embedding {len(patterns)} patterns "
            f"across {len(set(labels))} intents..."
        )
        embeddings = self.encoder.encode(
            patterns, show_progress_bar=False, normalize_embeddings=True
        )

        n_neighbors = min(TOP_K, len(patterns))
        nn = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine")
        nn.fit(embeddings)

        self.embeddings = np.asarray(embeddings, dtype=np.float32)
        self.labels = labels
        self.nn = nn

    # ------------------------------------------------------------------ #
    #  Prediction                                                         #
    # ------------------------------------------------------------------ #

    def predict(self, text: str, threshold: float = 0.5) -> Prediction:
        """Embed `text`, find top-K neighbours, return a Prediction.

        Winner = intent with highest weighted vote (each neighbour contributes
        `1 - cosine_distance` to its label). This is robust to a single noisy
        nearest neighbour because the neighbourhood as a whole decides.

        Confidence = top-1 cosine similarity (`1 - distance` of the closest
        neighbour). This is the raw semantic strength and is well-calibrated
        across intents — it does not depend on how many alternative intents
        share the neighbourhood.

        `top3` is the vote-share distribution among the top-3 winning intents,
        which the disambiguator (C8) reads to decide if it should ask the
        user instead of executing.
        """
        if not text or not text.strip():
            return Prediction(intent=None, confidence=0.0,
                              raw_text=text or "", normalized_text="")

        normalized = self.normalizer.clean(text)
        emb = self.encoder.encode([normalized], normalize_embeddings=True)
        n_neighbors = min(TOP_K, len(self.labels))
        distances, indices = self.nn.kneighbors(emb, n_neighbors=n_neighbors)

        # Exp-weighted vote: closer neighbours dominate sharply (temperature=10).
        # An exact match (similarity 1.0) gets weight ~e^10; a moderate match
        # (similarity 0.7) gets ~e^7. So a single perfect neighbour outweighs
        # several mediocre ones from a competing intent — this stops k-NN being
        # fooled when the encoder's lexical bias picks up sibling intents.
        similarities = np.maximum(0.0, 1.0 - distances[0])
        weights = np.exp(10.0 * similarities)

        scores: dict[str, float] = {}
        for w, idx in zip(weights, indices[0]):
            label = self.labels[int(idx)]
            scores[label] = scores.get(label, 0.0) + float(w)

        if not scores:
            return Prediction(intent=None, confidence=0.0,
                              raw_text=text, normalized_text=normalized)

        total = sum(scores.values()) or 1.0
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top3 = [(intent, round(score / total, 4)) for intent, score in ranked[:3]]
        winner_intent = ranked[0][0]

        # Confidence = top-1 cosine similarity (raw semantic strength).
        top1_similarity = float(similarities[0])
        confidence = round(top1_similarity, 4)

        if confidence < threshold:
            return Prediction(intent=None, confidence=confidence,
                              top3=top3, raw_text=text, normalized_text=normalized)

        return Prediction(intent=winner_intent, confidence=confidence,
                          top3=top3, raw_text=text, normalized_text=normalized)

    # ------------------------------------------------------------------ #
    #  Public maintenance                                                 #
    # ------------------------------------------------------------------ #

    def rebuild(self) -> None:
        """Force a re-embed and re-cache (use after hot-editing intents.json)."""
        self._build_index()
        self._save_cache(self._intents_hash())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    clf = IntentClassifier(
        intents_path=os.path.join(_here, "data", "intents.json"),
        models_dir=os.path.join(_here, "data", "models"),
    )
    tests = [
        "chrome kholo",
        "notepad band karo",
        "weather batao",
        "volume badhao",
        "screenshot lo",
        "mujhe yaad dilao 5 baje",
        "calculator open karo",
        "youtube pe arijit ka gaana chala do",
        "kuch random baat jo intent mein nahi hai",
    ]
    for q in tests:
        p = clf.predict(q)
        print(f"  {q!r:55s} -> intent={str(p.intent)!r:18s} conf={p.confidence:.3f}  top3={p.top3}")
