"""Fine-tune a multilingual transformer on intents.json for AERIS intent routing.

Drop-in replacement for the k-NN cosine head. The trained model lives at
``data/models/intent_neural/`` and is loaded by ``core/intent_model.py``.
JarvisBrain auto-detects it and routes through it; falls back to k-NN when
the model is missing or its ``intents_hash`` no longer matches.

Run from project root:

    python -m core.train_intent                         # defaults
    python -m core.train_intent --epochs 8 --batch 16
    python -m core.train_intent --model microsoft/Multilingual-MiniLM-L12-H384
    python -m core.train_intent --no-augment            # disable augmentation

Output (under ``data/models/intent_neural/``):
    model/                     HuggingFace save_pretrained
    tokenizer/                 HuggingFace save_pretrained
    labels.json                {id: intent_name} + intents_hash
    metadata.json              train/val accuracy, epoch, model name, sizes

Notes
-----
* CPU training is supported. XLM-R-base on ~1500 augmented samples runs
  in ~3-6 minutes per epoch on an i9-13900K. CUDA cuts that to seconds.
* Augmentation 4-5x's the training set (lower/upper case variants,
  punctuation drop, common Hinglish particles like "bhai" / "yaar").
* Class-weighted cross-entropy keeps rare intents from being ignored.
* The model is small enough to retrain whenever you edit ``intents.json``;
  the brain will pick the new weights up on the next start automatically.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass

# Silence the OpenMP duplicate-runtime crash on Windows (torch ↔ Qt clash).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Force UTF-8 on stdout/stderr so Windows cp1252 consoles don't crash on
# any non-ASCII characters that slip into our log lines.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

# Make `python -m core.train_intent` work whether or not the repo root is
# already on sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.intent_loader import load_all_intents, intents_hash
from core.normalizer import HinglishNormalizer

log = logging.getLogger("train_intent")


# ─── Defaults ──────────────────────────────────────────────────────── #

DEFAULT_MODEL = "distilbert-base-multilingual-cased"  # 134M; ~2x faster than XLM-R on CPU
DEFAULT_EPOCHS = 15
DEFAULT_LR = 5e-5
DEFAULT_BATCH = 16
DEFAULT_MAX_LEN = 48                       # patterns are short — 48 covers ~99%
DEFAULT_VAL_RATIO = 0.15
DEFAULT_SEED = 42

OUT_DIR = os.path.join(_ROOT, "data", "models", "intent_neural")
INTENTS_PATH = os.path.join(_ROOT, "data", "intents.json")


# ─── Data loading + augmentation ───────────────────────────────────── #

PARTICLES_SUFFIX = ["bhai", "yaar", "sir", "please", "zara", "na", "to", "abhi", "jaldi"]
PARTICLES_PREFIX = ["zara", "please", "ek kaam karo", "haan", "arre", "ok"]


# Loader + hash live in core.intent_loader so the runtime classifier and the
# offline trainer agree byte-for-byte on what counts as "the intent set".


def _augment(text: str, rng: random.Random) -> list[str]:
    """Return [original, ...variants] for a single pattern.

    Aggressive Hinglish-flavoured augmentation. Targets 4-5 variants per
    pattern minimum so a 700-pattern dataset becomes ~3000+ samples.
    Variants are appended as a list (not a set) so identical-looking
    text from different augmentation paths still creates separate training
    examples — the optimiser benefits from seeing duplicates of "important"
    patterns.

    Variant slots:
      0. base — original normalised text
      1. lowercase variant (no-op if already lowercase, kept anyway)
      2. trailing-particle variant ("X bhai" / "X please" / ...)
      3. leading-particle variant ("zara X" / "arre X" / ...)
      4. punctuation-stripped variant
      5. with-extra-space variant (simulates ASR insertions, ~30% chance)
    """
    base = text.strip()
    variants = [base, base.lower()]

    # Always a trailing particle — most Hinglish utterances have one
    variants.append(f"{base} {rng.choice(PARTICLES_SUFFIX)}")

    # Always a leading particle
    variants.append(f"{rng.choice(PARTICLES_PREFIX)} {base}")

    # Punctuation drop (matters when ASR adds trailing dots/commas)
    stripped = base.rstrip(".!?, ")
    if stripped != base:
        variants.append(stripped)
    else:
        # No-op cases: emit the lowercase+particle combination instead
        variants.append(f"{base.lower()} {rng.choice(PARTICLES_SUFFIX)}")

    # 30% extra-space variant — STT sometimes splits words oddly
    if rng.random() < 0.3 and " " in base:
        words = base.split()
        if len(words) >= 2:
            i = rng.randrange(len(words) - 1)
            spaced = " ".join(words[:i + 1]) + "  " + " ".join(words[i + 1:])
            variants.append(spaced)

    return variants


@dataclass
class Sample:
    text: str
    label: int


def _build_samples(intents: dict, normalizer: HinglishNormalizer
                   ) -> tuple[list[Sample], dict[str, int]]:
    """Flatten intents → [(pattern, label_id)] with a stable label map."""
    label2id: dict[str, int] = {}
    samples: list[Sample] = []
    for intent_name in sorted(intents.keys()):
        for pattern in intents[intent_name].get("patterns", []):
            if intent_name not in label2id:
                label2id[intent_name] = len(label2id)
            samples.append(Sample(
                text=normalizer.clean(pattern),
                label=label2id[intent_name],
            ))
    return samples, label2id


def _stratified_split(samples: list[Sample], val_ratio: float, rng: random.Random
                      ) -> tuple[list[Sample], list[Sample]]:
    """Per-label split so every intent appears in both train AND val.

    Intents with ≤1 example go entirely into train (val needs ≥1 example
    per label for meaningful per-class accuracy).
    """
    by_label: dict[int, list[Sample]] = {}
    for s in samples:
        by_label.setdefault(s.label, []).append(s)
    train, val = [], []
    for label, group in by_label.items():
        rng.shuffle(group)
        if len(group) <= 2:
            train.extend(group)
            continue
        n_val = max(1, int(round(len(group) * val_ratio)))
        val.extend(group[:n_val])
        train.extend(group[n_val:])
    return train, val


# ─── Torch Dataset ─────────────────────────────────────────────────── #

class IntentDataset(Dataset):
    def __init__(self, samples: list[Sample], tokenizer, max_len: int):
        self.samples = samples
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        enc = self.tokenizer(
            s.text,
            padding="max_length",
            truncation=True,
            max_length=self.max_len,
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "label": torch.tensor(s.label, dtype=torch.long),
        }


# ─── Train loop ────────────────────────────────────────────────────── #

def _class_weights(samples: list[Sample], num_classes: int) -> torch.Tensor:
    """Inverse-frequency weights so rare intents aren't dwarfed in CE loss."""
    counts = Counter(s.label for s in samples)
    total = sum(counts.values())
    weights = torch.ones(num_classes, dtype=torch.float)
    for label, c in counts.items():
        weights[label] = total / (num_classes * c)
    return weights


def _evaluate(model, loader, device) -> tuple[float, float]:
    model.eval()
    correct = 0
    total = 0
    loss_sum = 0.0
    ce = torch.nn.CrossEntropyLoss()
    with torch.no_grad():
        for batch in loader:
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)
            logits = model(input_ids=ids, attention_mask=mask).logits
            loss_sum += ce(logits, labels).item() * labels.size(0)
            preds = logits.argmax(dim=-1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
    return correct / max(1, total), loss_sum / max(1, total)


def train(args) -> None:
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[device] {device}  (cuda={torch.cuda.is_available()})", flush=True)

    # ── Load intents + build samples ───────────────────────────────
    print("[data] loading intents + plugin patterns...", flush=True)
    intents = load_all_intents(INTENTS_PATH)
    hash_ = intents_hash(intents)
    normalizer = HinglishNormalizer()
    samples, label2id = _build_samples(intents, normalizer)
    if not samples:
        raise RuntimeError("No patterns found in intents.json or plugin registry.")

    id2label = {v: k for k, v in label2id.items()}
    print(f"[data] {len(samples)} patterns over {len(label2id)} intents.", flush=True)

    rng = random.Random(args.seed)
    train_raw, val = _stratified_split(samples, args.val_ratio, rng)

    # Augment ONLY the training half — val stays clean for honest accuracy.
    if args.augment:
        train_aug: list[Sample] = []
        for s in train_raw:
            for variant in _augment(s.text, rng):
                train_aug.append(Sample(text=variant, label=s.label))
        train = train_aug
        print(f"[data] train: {len(train_raw)} -> {len(train)} (augmented)  "
              f"val: {len(val)}", flush=True)
    else:
        train = train_raw
        print(f"[data] train: {len(train)}  val: {len(val)}  (no augmentation)",
              flush=True)

    # ── Model + tokenizer ──────────────────────────────────────────
    print(f"[model] loading {args.model}...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model,
        num_labels=len(label2id),
        id2label=id2label,
        label2id=label2id,
    ).to(device)

    train_loader = DataLoader(
        IntentDataset(train, tokenizer, args.max_len),
        batch_size=args.batch, shuffle=True, num_workers=0,
    )
    val_loader = DataLoader(
        IntentDataset(val, tokenizer, args.max_len),
        batch_size=args.batch, shuffle=False, num_workers=0,
    )

    # ── Optimiser + schedule + loss ────────────────────────────────
    optim = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optim, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )
    cw = _class_weights(train, len(label2id)).to(device)
    ce = torch.nn.CrossEntropyLoss(weight=cw)

    # ── Train loop with best-on-val checkpointing ──────────────────
    best_val_acc = 0.0
    best_epoch = -1
    best_state = None
    print(f"[train] {args.epochs} epochs x {len(train_loader)} steps each\n",
          flush=True)
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0 = time.time()
        running = 0.0
        for step, batch in enumerate(train_loader, 1):
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)
            logits = model(input_ids=ids, attention_mask=mask).logits
            loss = ce(logits, labels)
            optim.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step()
            scheduler.step()
            running += loss.item()
        train_loss = running / max(1, len(train_loader))
        val_acc, val_loss = _evaluate(model, val_loader, device)
        dt = time.time() - t0
        marker = "  ** best" if val_acc > best_val_acc else ""
        print(f"  epoch {epoch:2d}/{args.epochs}  "
              f"train_loss={train_loss:.4f}  "
              f"val_loss={val_loss:.4f}  val_acc={val_acc*100:5.2f}%  "
              f"({dt:.1f}s){marker}", flush=True)
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    # ── Save ───────────────────────────────────────────────────────
    os.makedirs(OUT_DIR, exist_ok=True)
    model_dir = os.path.join(OUT_DIR, "model")
    tok_dir = os.path.join(OUT_DIR, "tokenizer")
    model.save_pretrained(model_dir)
    tokenizer.save_pretrained(tok_dir)
    with open(os.path.join(OUT_DIR, "labels.json"), "w", encoding="utf-8") as f:
        json.dump({
            "id2label": id2label,
            "label2id": label2id,
            "intents_hash": hash_,
        }, f, indent=2, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump({
            "model": args.model,
            "epochs": args.epochs,
            "best_epoch": best_epoch,
            "best_val_acc": round(best_val_acc, 4),
            "num_intents": len(label2id),
            "num_train_samples": len(train),
            "num_val_samples": len(val),
            "augmented": args.augment,
            "max_len": args.max_len,
            "lr": args.lr,
            "batch": args.batch,
            "seed": args.seed,
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "device": str(device),
        }, f, indent=2)

    print(f"\n[done] best val_acc = {best_val_acc*100:.2f}% at epoch {best_epoch}",
          flush=True)
    print(f"[done] saved to {OUT_DIR}", flush=True)
    print("\nRestart AERIS (or call brain.reload()) for the brain to use this model.",
          flush=True)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"HF model id (default: {DEFAULT_MODEL})")
    p.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    p.add_argument("--lr", type=float, default=DEFAULT_LR)
    p.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    p.add_argument("--max-len", type=int, default=DEFAULT_MAX_LEN)
    p.add_argument("--val-ratio", type=float, default=DEFAULT_VAL_RATIO)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--no-augment", dest="augment", action="store_false",
                   help="Disable training-data augmentation")
    p.set_defaults(augment=True)
    return p.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    train(_parse_args())
