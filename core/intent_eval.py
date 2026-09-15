"""Golden-set evaluator for the intent brain — the promote gate.

``data/intent_eval.json`` holds curated paraphrases that are deliberately
NOT in the training corpus (held-out, never augmented, never trained on).
They answer the only question that matters after a retrain: *did the new
model actually get smarter on phrasings it has never seen?*

Used two ways:

1. **Promote gate** — ``core/train_intent.py`` evaluates the freshly
   trained staging model AND the current live model on this set; staging
   is only promoted when it doesn't regress (see ``gate()``).
2. **Standalone** — check any model dir, or compare live vs staging::

       python -m core.intent_eval                    # evaluate live model
       python -m core.intent_eval compare            # live vs staging
       python -m core.intent_eval knn                # k-NN baseline

Item format::

    {"text": "chrome chalu karde", "intent": "open_app"}
    {"text": "kitna bajra hai",     "intent": "current_time",
     "also_ok": ["get_time"]}      # legacy twin intents both count

Every run writes a report card to ``data/report_card/``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_PATH = os.path.join(_ROOT, "data", "intent_eval.json")
CARD_DIR = os.path.join(_ROOT, "data", "report_card")
LIVE_DIR = os.path.join(_ROOT, "data", "models", "intent_neural")
STAGING_DIR = os.path.join(_ROOT, "data", "models", "intent_neural_staging")

# Staging may score up to this much BELOW live and still be promoted —
# golden sets are small, one flipped item shouldn't block a good model.
GATE_MARGIN = 0.02


@dataclass
class ItemResult:
    text: str
    gold: str
    also_ok: list[str]
    predicted: Optional[str]
    confidence: float

    @property
    def correct(self) -> bool:
        return self.predicted is not None and (
            self.predicted == self.gold or self.predicted in self.also_ok)


@dataclass
class EvalResult:
    model: str                       # dir path or "knn"
    items: list[ItemResult] = field(default_factory=list)
    known_labels: set = field(default_factory=set)

    @property
    def n(self) -> int:
        return len(self.items)

    @property
    def accuracy(self) -> float:
        if not self.items:
            return 0.0
        return sum(1 for i in self.items if i.correct) / len(self.items)

    def accuracy_over(self, labels: set) -> float:
        """Accuracy restricted to items whose gold intent is in ``labels`` —
        the fair basis for old-vs-new comparison when the new model has
        intents the old one never knew."""
        subset = [i for i in self.items if i.gold in labels]
        if not subset:
            return 0.0
        return sum(1 for i in subset if i.correct) / len(subset)

    def misses(self) -> list[ItemResult]:
        return [i for i in self.items if not i.correct]

    def summary(self) -> dict:
        per_intent: dict[str, list[int]] = {}
        for i in self.items:
            hit, total = per_intent.setdefault(i.gold, [0, 0])
            per_intent[i.gold] = [hit + (1 if i.correct else 0), total + 1]
        return {
            "model": self.model,
            "n": self.n,
            "accuracy": round(self.accuracy, 4),
            "per_intent": {k: {"correct": v[0], "total": v[1]}
                           for k, v in sorted(per_intent.items())},
            "misses": [{"text": i.text, "gold": i.gold,
                        "predicted": i.predicted,
                        "confidence": round(i.confidence, 3)}
                       for i in self.misses()],
        }


# ---------------------------------------------------------------------- #
#  Golden set                                                             #
# ---------------------------------------------------------------------- #

def load_golden(path: str = GOLDEN_PATH,
                known_intents: Optional[set] = None) -> list[dict]:
    """Load golden items; silently drops malformed rows, warns on items
    whose gold intent isn't in ``known_intents`` (when provided)."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log.warning("[eval] could not read %s: %s", path, e)
        return []
    items = []
    for raw in (data or {}).get("items", []):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text", "")).strip()
        intent = str(raw.get("intent", "")).strip()
        if not text or not intent:
            continue
        also = [str(x) for x in raw.get("also_ok", []) if isinstance(x, str)]
        if known_intents is not None and intent not in known_intents:
            log.warning("[eval] golden item %r targets unknown intent %r — skipped",
                        text, intent)
            continue
        items.append({"text": text, "intent": intent, "also_ok": also})
    return items


# ---------------------------------------------------------------------- #
#  Evaluators                                                             #
# ---------------------------------------------------------------------- #

def evaluate_model_dir(model_dir: str, items: list[dict]) -> Optional[EvalResult]:
    """Load the transformer at ``model_dir`` and score it on ``items``.

    The model is loaded fresh and released when done (returns the result
    only). Returns None when no loadable model exists there. Hash checks
    are deliberately skipped — eval must work on staging models whose
    hash intentionally differs from the live corpus.
    """
    from core.intent_model import NeuralIntentClassifier
    clf = NeuralIntentClassifier(model_dir=model_dir)
    if not clf.is_present():
        return None
    if not clf.load():
        return None
    result = EvalResult(model=model_dir,
                        known_labels=set(clf.id2label.values()))
    for it in items:
        pred = clf.predict(it["text"], threshold=0.0)
        result.items.append(ItemResult(
            text=it["text"], gold=it["intent"], also_ok=it["also_ok"],
            predicted=pred.intent, confidence=pred.confidence))
    # Release weights promptly — trainer evaluates two models back to back.
    clf.model = None
    clf.tokenizer = None
    return result


def evaluate_knn(items: list[dict]) -> EvalResult:
    """k-NN baseline — useful to sanity-check that the neural model is
    actually earning its RAM."""
    from core.intent_classifier import IntentClassifier
    clf = IntentClassifier(
        intents_path=os.path.join(_ROOT, "data", "intents.json"),
        models_dir=os.path.join(_ROOT, "data", "models"),
        lazy=True,
    )
    clf.load_encoder()
    clf.build_or_load_index()
    result = EvalResult(model="knn")
    for it in items:
        pred = clf.predict(it["text"], threshold=0.0)
        result.items.append(ItemResult(
            text=it["text"], gold=it["intent"], also_ok=it["also_ok"],
            predicted=pred.intent, confidence=pred.confidence))
    return result


# ---------------------------------------------------------------------- #
#  Gate                                                                   #
# ---------------------------------------------------------------------- #

def gate(old: Optional[EvalResult], new: EvalResult,
         margin: float = GATE_MARGIN) -> tuple[bool, str]:
    """Decide whether ``new`` (staging) may replace ``old`` (live).

    Comparison runs only over items whose gold intent the OLD model knew —
    brand-new intents can't be held against it. No old model → trivially
    pass (first train / clean install / Colab bundle).
    """
    if old is None or not old.items:
        return True, "no live model to compare against — promoting"
    base = old.known_labels or {i.gold for i in old.items}
    old_acc = old.accuracy_over(base)
    new_acc = new.accuracy_over(base)
    delta = new_acc - old_acc
    detail = (f"golden (comparable subset): live {old_acc*100:.1f}% -> "
              f"staging {new_acc*100:.1f}% ({delta*100:+.1f} pts)")
    if new_acc + margin >= old_acc:
        return True, detail
    return False, detail + f" — regression beyond {margin*100:.0f}pt margin"


# ---------------------------------------------------------------------- #
#  Report card                                                            #
# ---------------------------------------------------------------------- #

def write_report(result: EvalResult, tag: str = "") -> str:
    os.makedirs(CARD_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"intent_eval_{tag + '_' if tag else ''}{stamp}.json"
    path = os.path.join(CARD_DIR, name)
    from core.atomic_io import write_atomic_json
    write_atomic_json(path, result.summary())
    return path


def _print_result(r: EvalResult) -> None:
    print(f"  model : {r.model}")
    print(f"  items : {r.n}   accuracy: {r.accuracy*100:.1f}%")
    misses = r.misses()
    if misses:
        print(f"  misses ({len(misses)}):")
        for m in misses[:20]:
            print(f"    {m.text!r:44s} gold={m.gold}  got={m.predicted} "
                  f"({m.confidence:.2f})")
        if len(misses) > 20:
            print(f"    ... and {len(misses) - 20} more")


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cmd = argv[1] if len(argv) > 1 else "live"
    items = load_golden()
    if not items:
        print(f"No golden set at {GOLDEN_PATH} — nothing to evaluate.")
        return 1
    print(f"{len(items)} golden items loaded.\n")

    if cmd == "knn":
        r = evaluate_knn(items)
        _print_result(r)
        print(f"\nreport: {write_report(r, 'knn')}")
        return 0

    if cmd == "compare":
        old = evaluate_model_dir(LIVE_DIR, items)
        new = evaluate_model_dir(STAGING_DIR, items)
        if old:
            print("LIVE:")
            _print_result(old)
        else:
            print("LIVE: (no model)")
        if new:
            print("\nSTAGING:")
            _print_result(new)
            ok, why = gate(old, new)
            print(f"\ngate: {'PASS' if ok else 'FAIL'} — {why}")
        else:
            print("\nSTAGING: (no model)")
        return 0

    # default: evaluate a model dir (arg or live)
    target = cmd if os.path.isdir(cmd) else LIVE_DIR
    r = evaluate_model_dir(target, items)
    if r is None:
        print(f"No loadable model at {target}")
        return 1
    _print_result(r)
    print(f"\nreport: {write_report(r)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
