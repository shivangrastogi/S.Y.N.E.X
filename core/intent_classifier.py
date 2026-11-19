"""Multilingual intent classifier — sentence encoder + k-NN over labelled patterns.

Replaces the previous Keras dense head plus standalone trainer. There is no
training step: the sentence encoder is frozen, and "training" reduces to
embedding all patterns in `intents.json` and fitting a NearestNeighbors index.

The cached index is keyed by the MD5 hash of `intents.json`, so any edit to
that file triggers an automatic rebuild on next boot (still sub-10s for ~300
patterns).
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np

# NOTE — `sentence_transformers` (and the torch runtime behind it) plus
# `sklearn.neighbors` are imported LAZILY, inside the functions that first
# need them (see `_ensure_encoder` / `_nearest_neighbors`). Importing them
# here cost ~15 s and several hundred MB of RSS at *module import* time —
# i.e. every caller paid the whole torch tax just to `from core.brain import
# JarvisBrain`, even with `lazy=True` and even for utterances that resolve on
# the exact-match tier and never touch an embedding.
# Keep it that way: no module-level torch/sentence-transformers/sklearn here.
from core.intent_loader import load_all_intents, intents_hash
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
        # Exact-pattern fast path: {normalized pattern → intent name}.
        # Built/refreshed any time the index is built or loaded so a
        # verbatim "open notepad" never gets re-routed by an embedding
        # model that fixates on the wrong cue word ("note").
        self._exact_lookup: dict[str, str] = {}
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
                self._build_exact_lookup()
                return
            except Exception as e:
                log.warning(f"[IntentClassifier] Cache load failed ({e}); rebuilding.")

        log.info("[IntentClassifier] Rebuilding index from intents.json...")
        self._build_index()
        self._build_exact_lookup()
        self._save_cache(current_hash)

    def load_exact_only(self) -> None:
        """Tier-0 boot — build ONLY the verbatim pattern table.

        Pure JSON + dict work: no encoder, no torch, no pickled index. This is
        what lite boot calls so the exact-match fast path is live while the
        k-NN index (and the sentence encoder behind it) stay unloaded until an
        utterance actually misses every cheap tier. Idempotent.
        """
        self._build_exact_lookup()

    def _build_exact_lookup(self) -> None:
        """Index every pattern by its normalised form so verbatim user input
        can bypass the heavy classifiers. Cheap — just JSON + dict-build.
        """
        intents = self._load_intents()
        lookup: dict[str, str] = {}
        for intent_name, cfg in intents.items():
            for pattern in cfg.get("patterns", []):
                key = self.normalizer.clean(pattern)
                if key:
                    lookup.setdefault(key, intent_name)
        self._exact_lookup = lookup

    def exact_match(self, text: str) -> Optional[str]:
        """Return the intent for a verbatim pattern match, or None."""
        if not self._exact_lookup or not text:
            return None
        key = self.normalizer.clean(text)
        return self._exact_lookup.get(key)

    # ------------------------------------------------------------------ #
    #  Hashing & caching                                                  #
    # ------------------------------------------------------------------ #

    def _intents_hash(self) -> str:
        """Hash of the merged intent set (file + plugin registry).

        Delegates to ``core.intent_loader`` so train_intent and runtime agree
        byte-for-byte; otherwise the neural model's saved hash never matches.
        """
        return intents_hash(self._load_intents())

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
        self.nn = self._nearest_neighbors(n_neighbors=n_neighbors, metric="cosine")
        self.nn.fit(self.embeddings)

    # ------------------------------------------------------------------ #
    #  Index build                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _nearest_neighbors(**kwargs):
        """Lazy sklearn handle — see the import note at the top of the file."""
        from sklearn.neighbors import NearestNeighbors
        return NearestNeighbors(**kwargs)

    def _ensure_encoder(self) -> None:
        if self.encoder is None:
            # Lazy import: this line is where the torch tax is actually paid.
            from sentence_transformers import SentenceTransformer

            # torch may have just come into existence — pin it to one compute
            # thread before any tensor op runs (see core/torch_setup.py).
            from core.torch_setup import pin_torch_threads
            pin_torch_threads()

            log.info(f"[IntentClassifier] Loading encoder: {ENCODER_NAME}")
            try:
                # Local cache first. A default load asks hf.co whether the
                # model changed: measured 6.6 s online vs 2.2 s offline here.
                # run_gui.py sidesteps that with HF_HUB_OFFLINE, but main.py
                # and run_split.py didn't. Only a cache miss (the first run
                # on a machine) goes on to the network below.
                self.encoder = SentenceTransformer(ENCODER_NAME,
                                                   local_files_only=True)
                return
            except Exception as e:
                log.info("[IntentClassifier] encoder not in local cache (%s); "
                         "downloading", e)
            try:
                self.encoder = SentenceTransformer(ENCODER_NAME)
            except Exception as e:
                # Common offline cause: huggingface_hub can't reach hf.co
                # (getaddrinfo failed / connection refused). The model is
                # almost always already in the local cache, so retry with
                # local_files_only=True before giving up — this keeps the
                # GUI splash from hanging when the machine is offline.
                msg = repr(e).lower()
                offline_signals = (
                    "getaddrinfo", "name or service not known",
                    "connection", "timeout", "11001", "max retries",
                )
                if any(s in msg for s in offline_signals):
                    log.warning(
                        "[IntentClassifier] Network unreachable while loading "
                        "encoder — retrying from local HuggingFace cache."
                    )
                    self.encoder = SentenceTransformer(
                        ENCODER_NAME, local_files_only=True
                    )
                else:
                    raise

    def _load_intents(self) -> dict:
        return load_all_intents(self.intents_path)

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
        from core.encoder_lock import ENCODER_LOCK
        with ENCODER_LOCK:
            embeddings = self.encoder.encode(
                patterns, show_progress_bar=False, normalize_embeddings=True
            )

        n_neighbors = min(TOP_K, len(patterns))
        nn = self._nearest_neighbors(n_neighbors=n_neighbors, metric="cosine")
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
        # Shared encoder — serialize against the semantic-memory embed
        # thread + chat gate (concurrent torch forwards corrupt the heap).
        from core.encoder_lock import ENCODER_LOCK
        with ENCODER_LOCK:
            emb = self.encoder.encode([normalized], normalize_embeddings=True)
        n_neighbors = min(TOP_K, len(self.labels))
        distances, indices = self.nn.kneighbors(emb, n_neighbors=n_neighbors)
        return self._vote(text, normalized, distances[0], indices[0], threshold)

    def predict_many(self, texts: list[str],
                     threshold: float = 0.5) -> list[Prediction]:
        """``[predict(t) for t in texts]`` with one encoder forward for the lot.

        The subspan scanner asks about up to six variants of one utterance.
        Encoding them as one batch took 78 ms against 270 ms one at a time on
        this laptop's CPU (torch pinned to one thread). Each row is voted
        exactly as ``predict`` votes it.
        """
        out: list[Optional[Prediction]] = [None] * len(texts)
        live: list[int] = []
        norms: list[str] = []
        for i, text in enumerate(texts):
            if not text or not text.strip():
                out[i] = Prediction(intent=None, confidence=0.0,
                                    raw_text=text or "", normalized_text="")
            else:
                live.append(i)
                norms.append(self.normalizer.clean(text))
        if live:
            from core.encoder_lock import ENCODER_LOCK
            with ENCODER_LOCK:
                emb = self.encoder.encode(norms, normalize_embeddings=True,
                                          show_progress_bar=False)
            n_neighbors = min(TOP_K, len(self.labels))
            distances, indices = self.nn.kneighbors(emb, n_neighbors=n_neighbors)
            for row, i in enumerate(live):
                out[i] = self._vote(texts[i], norms[row], distances[row],
                                    indices[row], threshold)
        return out

    def _vote(self, text: str, normalized: str, distances, indices,
              threshold: float) -> Prediction:
        """Turn one row of k-NN neighbours into a Prediction (see ``predict``)."""
        # Exp-weighted vote: closer neighbours dominate sharply (temperature=10).
        # An exact match (similarity 1.0) gets weight ~e^10; a moderate match
        # (similarity 0.7) gets ~e^7. So a single perfect neighbour outweighs
        # several mediocre ones from a competing intent — this stops k-NN being
        # fooled when the encoder's lexical bias picks up sibling intents.
        similarities = np.maximum(0.0, 1.0 - distances)
        weights = np.exp(10.0 * similarities)

        scores: dict[str, float] = {}
        for w, idx in zip(weights, indices):
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
