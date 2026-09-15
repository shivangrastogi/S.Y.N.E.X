"""Chat gate v2 — encoder-based chat-vs-command classifier.

Replaces the keyword-marker heuristic in ``dialogue_context.is_chatty``
as the primary router between SKILLS and CONVERSATION. The keyword list
only knows the markers it was told ("yaar", "bored", ...); this gate
generalizes — any *phrasing* that embeds near conversation and far from
the 355 skills' command patterns is chat.

How it works
------------
* Command side: every pattern from the live skill registry + intents.json.
* Chat side: ``data/chat_corpus.json`` (~100 curated Hinglish/English
  conversational utterances — editable, gate rebuilds on change).
* Both sides embedded with the SAME sentence encoder the brain already
  has in RAM (no second model), then a tiny LogisticRegression head.
* Artifacts cached at ``data/models/chat_gate.pkl`` keyed by a corpus
  hash — the ~20 s embed+fit cost is paid ONCE, then boots load in ms.

Runtime contract (``is_chatty_hybrid``):
* model ready  → encoder verdict (probability > _CHAT_THRESHOLD)
* model absent → falls back to the keyword heuristic, so the gate can
  never be weaker than v1.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import threading
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CORPUS_PATH = os.path.join(_ROOT, "data", "chat_corpus.json")
_CACHE_PATH = os.path.join(_ROOT, "data", "models", "chat_gate.pkl")

# P(chat) above this → conversation. Calibrated 2026-07-04 on probe sets:
# chat utterances scored 0.67–0.97, hardest paraphrase command ("awaaz
# thodi badha do") 0.61 — 0.65 splits the gap. Biased toward commands
# (a chat wrongly dispatched can CLOSE things; the keyword OR-term in
# is_chatty_hybrid still floors borderline chat).
_CHAT_THRESHOLD = 0.65

# Cap on command-side samples so the one-time build stays ~20 s.
_MAX_COMMAND_SAMPLES = 700

_lock = threading.Lock()
_clf = None                    # fitted LogisticRegression (or None)
_encode = None                 # callable: list[str] -> ndarray


def _load_corpus() -> tuple[list[str], list[str]]:
    """Returns (chat_examples, command_extras) from data/chat_corpus.json.
    ``commands_extra`` are paraphrase-style commands ("awaaz thodi badha
    do") that canonical registry patterns don't cover — without them the
    boundary drifts and polite Hinglish commands read as chat."""
    try:
        with open(_CORPUS_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return ([s for s in d.get("chat", []) if s.strip()],
                [s for s in d.get("commands_extra", []) if s.strip()])
    except Exception as e:
        log.warning("[chat_gate] corpus load failed: %s", e)
        return [], []


def _command_patterns() -> list[str]:
    pats: set[str] = set()
    try:
        from core.skill_registry import REGISTRY
        for sk in REGISTRY.values():
            for p in (sk.patterns or []):
                pats.add(p.strip().lower())
    except Exception:
        pass
    try:
        with open(os.path.join(_ROOT, "data", "intents.json"),
                  encoding="utf-8") as f:
            for cfg in json.load(f).values():
                for p in cfg.get("patterns", []):
                    pats.add(p.strip().lower())
    except Exception:
        pass
    out = sorted(pats)
    if len(out) > _MAX_COMMAND_SAMPLES:
        # Deterministic thinning — every Nth pattern, stable across boots.
        step = len(out) / _MAX_COMMAND_SAMPLES
        out = [out[int(i * step)] for i in range(_MAX_COMMAND_SAMPLES)]
    return out


def _corpus_hash(chats: list[str], commands: list[str]) -> str:
    h = hashlib.md5()
    for s in chats:
        h.update(s.encode("utf-8"))
    h.update(b"|")
    for s in commands:
        h.update(s.encode("utf-8"))
    return h.hexdigest()


def configure(encode_fn) -> None:
    """Give the gate an embedding function (the brain's encoder).
    ``encode_fn(list[str]) -> ndarray`` with normalized embeddings."""
    global _encode
    _encode = encode_fn


def ensure_ready() -> bool:
    """Load the cached head, or build it (embed + fit) if the corpus
    changed. Requires configure() first. Returns True when usable."""
    global _clf
    if _encode is None:
        return False
    with _lock:
        if _clf is not None:
            return True
        chats, cmd_extra = _load_corpus()
        commands = _command_patterns() + cmd_extra
        if len(chats) < 20 or len(commands) < 50:
            log.warning("[chat_gate] corpus too small (%d chat / %d cmd)",
                        len(chats), len(commands))
            return False
        want_hash = _corpus_hash(chats, commands)

        # Fast path — cached head matches the current corpus.
        try:
            with open(_CACHE_PATH, "rb") as f:
                blob = pickle.load(f)
            if blob.get("hash") == want_hash:
                _clf = blob["clf"]
                log.info("[chat_gate] loaded cached head (%d+%d samples)",
                         len(chats), len(commands))
                return True
        except Exception:
            pass

        # Build — one-time ~20 s (embeds ~800 sentences on CPU).
        log.info("[chat_gate] building head: %d chat + %d command samples",
                 len(chats), len(commands))
        try:
            import numpy as np
            from sklearn.linear_model import LogisticRegression
            X = _encode(chats + commands)
            y = np.array([1] * len(chats) + [0] * len(commands))
            clf = LogisticRegression(max_iter=1000, class_weight="balanced")
            clf.fit(X, y)
            acc = float(clf.score(X, y))
            log.info("[chat_gate] head fit — train acc %.3f", acc)
            os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
            with open(_CACHE_PATH, "wb") as f:
                pickle.dump({"hash": want_hash, "clf": clf}, f)
            _clf = clf
            return True
        except Exception as e:
            log.warning("[chat_gate] build failed: %s", e)
            return False


def chat_probability(text: str) -> Optional[float]:
    """P(chat) for one utterance, or None when the gate isn't ready."""
    if _clf is None or _encode is None or not text or not text.strip():
        return None
    try:
        X = _encode([text.strip().lower()])
        return float(_clf.predict_proba(X)[0][1])
    except Exception as e:
        log.debug("[chat_gate] score failed: %s", e)
        return None


# Domain words whose presence means "this is a data/action request, never
# small talk" — an assistant asked about weather/battery/time must ANSWER,
# even when the phrasing reads conversational ("mausam kaisa hai aaj?"
# scored p_chat 0.87 and flapped at the dispatch bar). Product rule, not
# statistics.
_NEVER_CHAT = (
    "mausam", "weather", "barish", "temperature", "forecast",
    "battery", "batteri", "time kya", "kitne baje", "date kya",
)


def is_chatty_hybrid(text: str) -> bool:
    """Primary router: encoder verdict when ready, keyword fallback else.

    The keyword heuristic (dialogue_context.is_chatty) is also kept as an
    OR-term for encoder-ready mode: it encodes hard product decisions
    (e.g. anything addressing the assistant as "tum/tumhara" is chat)
    that we never want a statistical head to silently unlearn.
    ``_NEVER_CHAT`` domain words hard-override in the other direction.
    """
    low = (text or "").lower()
    if any(k in low for k in _NEVER_CHAT):
        return False
    from core.dialogue_context import is_chatty as _kw
    p = chat_probability(text)
    if p is None:
        return _kw(text)
    return p >= _CHAT_THRESHOLD or _kw(text)
