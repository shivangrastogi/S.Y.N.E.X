"""The 2026-09-15 speed pass: batched heavy-tier prediction and background
warm-up after a lite boot.

Batching must be a pure speed change, so every test here compares the batched
path against the one-at-a-time path it replaced and demands the same answers.
No real model is loaded: the encoder and neural head are small fakes.
"""
from __future__ import annotations

import threading

import numpy as np
import pytest

from core.intent_classifier import IntentClassifier, Prediction
from core import utterance_parser as up


# ── k-NN classifier: predict_many == [predict(t) ...] ───────────────────
class _FakeEncoder:
    """Deterministic 16-d unit vectors derived from the text."""

    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        rows = []
        for t in texts:
            rng = np.random.default_rng(abs(hash(t)) % (2**32))
            v = rng.normal(size=16)
            rows.append(v / np.linalg.norm(v))
        return np.array(rows)


@pytest.fixture
def knn(tmp_path):
    from sklearn.neighbors import NearestNeighbors
    clf = IntentClassifier(str(tmp_path / "intents.json"), str(tmp_path), lazy=True)
    clf.encoder = _FakeEncoder()
    patterns = [f"pattern {i}" for i in range(40)]
    clf.labels = [f"intent_{i % 7}" for i in range(40)]
    clf.nn = NearestNeighbors(metric="cosine").fit(clf.encoder.encode(patterns))
    return clf


def test_knn_predict_many_matches_predict(knn):
    texts = ["chrome kholo", "pattern 3", "", "wifi band kar do", "   ", "pattern 17"]
    batched = knn.predict_many(texts, threshold=0.0)
    single = [knn.predict(t, threshold=0.0) for t in texts]
    for b, s in zip(batched, single):
        assert (b.intent, b.top3, b.normalized_text) == (s.intent, s.top3, s.normalized_text)
        assert b.confidence == pytest.approx(s.confidence, abs=1e-6)


def test_knn_predict_many_applies_threshold_per_row(knn):
    rows = knn.predict_many(["pattern 3", "zzzz unrelated"], threshold=0.99)
    assert rows[0].intent is not None      # an exact pattern clears 0.99
    assert rows[1].intent is None


# ── neural head: batch padding must not change the answer ────────────────
def test_neural_predict_many_matches_predict():
    torch = pytest.importorskip("torch")
    from core.intent_model import NeuralIntentClassifier

    class _Tok:
        def __call__(self, texts, padding, truncation, max_length, return_tensors):
            texts = [texts] if isinstance(texts, str) else texts
            ids = [[(ord(c) % 50) + 1 for c in t][:max_length] for t in texts]
            width = max_length if padding == "max_length" else max(len(r) for r in ids)
            input_ids = torch.zeros((len(ids), width), dtype=torch.long)
            mask = torch.zeros((len(ids), width), dtype=torch.long)
            for i, r in enumerate(ids):
                input_ids[i, :len(r)] = torch.tensor(r)
                mask[i, :len(r)] = 1
            return {"input_ids": input_ids, "attention_mask": mask}

    class _Model(torch.nn.Module):
        """Masked mean of token embeddings -> 5 logits. Padding-invariant,
        like a real transformer with its attention mask."""

        def __init__(self):
            super().__init__()
            torch.manual_seed(0)
            self.emb = torch.nn.Embedding(51, 8)
            self.head = torch.nn.Linear(8, 5)

        def forward(self, input_ids, attention_mask):
            m = attention_mask.unsqueeze(-1).float()
            pooled = (self.emb(input_ids) * m).sum(1) / m.sum(1).clamp(min=1)

            class _Out:
                pass
            o = _Out()
            o.logits = self.head(pooled)
            return o

    n = NeuralIntentClassifier(model_dir="__missing__")
    n.tokenizer, n.model = _Tok(), _Model().eval()
    n.id2label = {i: f"intent_{i}" for i in range(5)}
    n._max_len = 24
    n._device_cached = torch.device("cpu")

    texts = ["chrome kholo", "", "wifi band kar do yaar", "ok"]
    batched = n.predict_many(texts, threshold=0.0)
    single = [n.predict(t, threshold=0.0) for t in texts]
    for b, s in zip(batched, single):
        assert b.intent == s.intent
        assert b.confidence == pytest.approx(s.confidence, abs=1e-5)


# ── JarvisBrain: cheap tiers stay cheap, the rest goes in one batch ─────
@pytest.fixture
def brain(monkeypatch):
    from core.brain import JarvisBrain
    b = JarvisBrain(lazy=True)
    b.prepare_fast_tiers()
    monkeypatch.setattr(b, "_ensure_loaded", lambda: None)
    b._neural_active = False
    batches: list[list[str]] = []

    def fake_many(texts, threshold=0.5):
        batches.append(list(texts))
        return [Prediction(intent="heavy", confidence=0.6, top3=[("heavy", 1.0)],
                           raw_text=t, normalized_text=t) for t in texts]

    def fake_one(text, threshold=0.5):
        return fake_many([text], threshold)[0]

    monkeypatch.setattr(b.classifier, "predict_many", fake_many)
    monkeypatch.setattr(b.classifier, "predict", fake_one)
    b.batches = batches
    return b


def test_brain_predict_many_batches_only_the_misses(brain):
    texts = ["lock screen", "zzq one", "12 plus 37 kitna hai", "zzq two"]
    preds = brain.predict_many(texts)
    assert [p.intent for p in preds] == ["lock_screen", "heavy", "calculate", "heavy"]
    assert brain.batches == [["zzq one", "zzq two"]]


def test_brain_predict_many_matches_predict(brain):
    texts = ["lock screen", "zzq three", "time kya hua"]
    assert [p.intent for p in brain.predict_many(texts)] == \
        [brain.predict(t).intent for t in texts]


def test_brain_predict_fast_never_touches_the_heavy_tier(brain):
    assert brain.predict_fast("zzq never seen") is None
    assert brain.batches == []


# ── subspan scanner: same answer as the old loop, fewer forwards ─────────
class _LoopOnlyBrain:
    """The pre-batching contract: predict() only."""

    def __init__(self, table):
        self.table = table
        self.calls: list[str] = []

    def predict(self, text, threshold=0.5):
        self.calls.append(text)
        conf, intent = self.table.get(text, (0.3, "noise"))
        return Prediction(intent=intent, confidence=conf, top3=[(intent, 1.0)],
                          raw_text=text, normalized_text=text)


class _BatchBrain(_LoopOnlyBrain):
    def __init__(self, table, certain):
        super().__init__(table)
        self.certain = certain          # spans a cheap tier answers
        self.many_calls: list[list[str]] = []

    def predict_fast(self, text, threshold=0.5):
        return self.predict(text) if text in self.certain else None

    def predict_many(self, texts, threshold=0.5):
        self.many_calls.append(list(texts))
        return [self.predict(t) for t in texts]


@pytest.mark.parametrize("text,table,certain", [
    # heavy-only: best of the trimmed variants wins
    ("ek kam karo notepad open karo",
     {"kam karo notepad open karo": (0.8, "open_app")}, set()),
    # a cheap-tier hit mid-list ends the scan
    ("bhai notepad kholo please",
     {"notepad kholo please": (1.0, "open_app")}, {"notepad kholo please"}),
    # nothing confident anywhere
    ("yaar kuch samajh nahi aa raha", {}, set()),
])
def test_batched_scan_picks_what_the_loop_picked(text, table, certain):
    old = up.find_best_interpretation(text, _LoopOnlyBrain(table))
    new_brain = _BatchBrain(table, certain)
    new = up.find_best_interpretation(text, new_brain)
    assert (old[0].intent, old[0].confidence, old[1]) == \
        (new[0].intent, new[0].confidence, new[1])
    assert len(new_brain.many_calls) == 1


def test_batched_scan_stops_at_the_first_certain_span():
    """Spans after a cheap-tier certainty must never reach the heavy tier —
    that stop is what keeps "notepad kholo" from loading the encoder."""
    text = "bhai notepad kholo please zara"
    spans = up._candidate_spans(text)
    certain = spans[1]
    b = _BatchBrain({certain: (1.0, "open_app")}, {certain})
    up.find_best_interpretation(text, b)
    assert b.many_calls == [spans[:2]]


# ── background warm-up ───────────────────────────────────────────────────
class _WarmBrain:
    def __init__(self, loaded=False):
        self.ml_loaded = loaded
        self.warmed = threading.Event()

    def warm_up(self):
        self.ml_loaded = True
        self.warmed.set()
        return True


class _EngineStub:
    from core.main_engine import JarvisMainEngine as _J
    start_background_warmup = _J.start_background_warmup

    def __init__(self, brain):
        self.brain = brain


def test_warmup_runs_in_the_background(monkeypatch):
    monkeypatch.setenv("AERIS_PREWARM", "1")
    eng = _EngineStub(_WarmBrain())
    assert eng.start_background_warmup(delay_s=0) is True
    assert eng.brain.warmed.wait(5)
    assert eng.start_background_warmup(delay_s=0) is False   # one thread only


@pytest.mark.parametrize("env,loaded", [("0", False), ("1", True)])
def test_warmup_skipped_when_off_or_already_warm(monkeypatch, env, loaded):
    monkeypatch.setenv("AERIS_PREWARM", env)
    eng = _EngineStub(_WarmBrain(loaded=loaded))
    assert eng.start_background_warmup(delay_s=0) is False
    assert not eng.brain.warmed.is_set()


@pytest.mark.parametrize("val,want", [
    (None, True), ("", True), ("1", True), ("on", True),
    ("0", False), ("false", False), ("OFF", False), ("no", False),
])
def test_prewarm_flag_parsing(monkeypatch, val, want):
    from core.lite_ml import prewarm_enabled
    if val is None:
        monkeypatch.delenv("AERIS_PREWARM", raising=False)
    else:
        monkeypatch.setenv("AERIS_PREWARM", val)
    assert prewarm_enabled() is want


def test_brain_warm_up_restarts_the_idle_clock(monkeypatch):
    from core.brain import JarvisBrain
    b = JarvisBrain(lazy=True)

    def fake_load(reason="cold predict"):
        assert reason == "background warm-up", "warm-up must label its log line"
        b._encoder_loaded = True
    monkeypatch.setattr(b, "_ensure_loaded", fake_load)
    b._last_predict_ts = 0.0
    assert b.warm_up() is True
    assert b._last_predict_ts > 0.0
    assert b.warm_up() is False          # already warm
