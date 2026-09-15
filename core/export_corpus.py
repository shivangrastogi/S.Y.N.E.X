"""Export the fully-merged training corpus for off-machine (Colab/GPU) training.

Run on the LAPTOP (where all skills import correctly):

    python -m core.export_corpus

Writes ``data/training_corpus.json`` — the exact merged intent set
(intents.json + every discovered skill's patterns + user patterns) that
``load_all_intents()`` produces at runtime. Training from this file with
``train_intent.py --corpus`` reproduces the laptop's intents_hash, so the
resulting model passes the brain's hash check and actually loads.

Also prints the hash so you can eyeball that Colab produced the same one.
"""
from __future__ import annotations

import json
import os

from core.intent_loader import load_all_intents, intents_hash

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUT = os.path.join(_ROOT, "data", "training_corpus.json")


def main() -> None:
    intents = load_all_intents()
    h = intents_hash(intents)
    n_intents = len(intents)
    n_patterns = sum(len(v.get("patterns", [])) for v in intents.values())
    with open(_OUT, "w", encoding="utf-8") as f:
        json.dump(intents, f, ensure_ascii=False, indent=0)
    print(f"[export] wrote {_OUT}")
    print(f"[export] {n_intents} intents · {n_patterns} patterns")
    print(f"[export] intents_hash = {h}")
    print("[export] Upload this file to Colab and train with:")
    print("         python -m core.train_intent --corpus training_corpus.json "
          "--epochs 8")
    print("[export] After training, the model's saved hash MUST equal the "
          "above — then it loads on the laptop.")


if __name__ == "__main__":
    main()
