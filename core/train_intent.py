"""Fine-tune a multilingual transformer on intents.json for AERIS intent routing.

Drop-in replacement for the k-NN cosine head. The trained model lives at
``data/models/intent_neural/`` and is loaded by ``core/intent_model.py``.
JarvisBrain auto-detects it and routes through it; falls back to k-NN when
the model is missing or its ``intents_hash`` no longer matches.

Incremental-by-default (the continual-learning upgrade)
-------------------------------------------------------
When a previously trained model exists at ``data/models/intent_neural/``,
training WARM-STARTS from its weights instead of the base checkpoint:
the fine-tuned body is kept, the classification head is mapped by intent
NAME (new intents get fresh rows, existing ones keep their learned
weights), and only a few low-LR epochs run. Every retrain therefore
*adds* to what the model already knows — generation N+1 builds on
generation N. Use ``--fresh`` for a from-scratch run.

The run lands in ``data/models/intent_neural_staging/``, is scored on the
held-out golden set (``data/intent_eval.json``), and is promoted to live
only if it doesn't regress (``core/model_registry.py`` archives the old
model for one-command rollback).

Typical cycle (all run by you, whenever enough new usage has piled up):

    python -m core.learning_loop harvest    # real usage -> corpus
    python -m core.train_intent             # incremental warm-start + gate
    (restart AERIS)

Run from project root:

    python -m core.train_intent                         # incremental (auto)
    python -m core.train_intent --fresh                 # full retrain
    python -m core.train_intent --epochs 8 --batch 16
    python -m core.train_intent --no-promote            # stage only
    python -m core.train_intent --no-augment            # disable augmentation

Output (staged, then promoted to ``data/models/intent_neural/``):
    model/                     HuggingFace save_pretrained
    tokenizer/                 HuggingFace save_pretrained
    labels.json                {id: intent_name} + intents_hash
    metadata.json              accuracy, generation, mode, lineage, sizes

Notes
-----
* CPU training is supported; incremental runs (4 epochs, warm body) are
  several times cheaper than a fresh 15-epoch run. CUDA cuts either to
  minutes — see COLAB_TRAINING.md.
* Augmentation 4-5x's the training set (lower/upper case variants,
  punctuation drop, common Hinglish particles like "bhai" / "yaar").
* Class-weighted cross-entropy keeps rare intents from being ignored.
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
DEFAULT_EPOCHS_FRESH = 15
DEFAULT_EPOCHS_INCREMENTAL = 4             # warm body converges fast
DEFAULT_LR_FRESH = 5e-5
DEFAULT_LR_INCREMENTAL = 2e-5              # gentler — protect prior knowledge
DEFAULT_BATCH = 16
DEFAULT_MAX_LEN = 48                       # patterns are short — 48 covers ~99%
DEFAULT_VAL_RATIO = 0.15
DEFAULT_SEED = 42

LIVE_DIR = os.path.join(_ROOT, "data", "models", "intent_neural")
OUT_DIR = os.path.join(_ROOT, "data", "models", "intent_neural_staging")
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


# ─── Warm start (incremental fine-tuning) ──────────────────────────── #

def _copy_head_rows(old_sd: dict, new_sd: dict,
                    old_label2id: dict[str, int],
                    new_label2id: dict[str, int]) -> int:
    """Copy classification-head rows from an old state dict into a new one,
    mapped by intent NAME (label ids shift when the sorted intent set grows).

    Only touches parameters whose name marks them as head weights
    ("classifier"/"score") AND whose leading dimension equals the label
    count on both sides — body weights are never rewritten. Mutates
    ``new_sd`` tensors in place; returns how many parameters were mapped.
    """
    n_old, n_new = len(old_label2id), len(new_label2id)
    copied = 0
    with torch.no_grad():
        for key, new_t in new_sd.items():
            if "classifier" not in key and "score" not in key:
                continue
            old_t = old_sd.get(key)
            if old_t is None or not hasattr(new_t, "shape"):
                continue
            if (len(new_t.shape) < 1 or new_t.shape[0] != n_new
                    or old_t.shape[0] != n_old
                    or new_t.shape[1:] != old_t.shape[1:]):
                continue
            for intent, nid in new_label2id.items():
                oid = old_label2id.get(intent)
                if oid is not None:
                    new_t[nid] = old_t[oid]
            copied += 1
    return copied


def _load_warm_start(prev_dir: str, base_model_name: str,
                     label2id: dict[str, int], id2label: dict[int, str],
                     device):
    """Try to warm-start from a previously trained model directory.

    Returns ``(model, tokenizer, parent_meta)`` on success, else
    ``(None, None, None)`` — caller falls back to a fresh base checkpoint.
    """
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    model_sub = os.path.join(prev_dir, "model")
    tok_sub = os.path.join(prev_dir, "tokenizer")
    labels_p = os.path.join(prev_dir, "labels.json")
    if not (os.path.isdir(model_sub) and os.path.isdir(tok_sub)
            and os.path.exists(labels_p)):
        return None, None, None

    parent_meta: dict = {}
    meta_p = os.path.join(prev_dir, "metadata.json")
    if os.path.exists(meta_p):
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                parent_meta = json.load(f)
        except Exception:
            parent_meta = {}
    if parent_meta.get("model") and parent_meta["model"] != base_model_name:
        print(f"[warm] previous model is {parent_meta['model']!r}, requested "
              f"{base_model_name!r} — architectures differ, training FRESH.",
              flush=True)
        return None, None, None

    try:
        with open(labels_p, "r", encoding="utf-8") as f:
            old_label2id = {str(k): int(v)
                            for k, v in json.load(f).get("label2id", {}).items()}
        if not old_label2id:
            return None, None, None
        tokenizer = AutoTokenizer.from_pretrained(tok_sub)
        if old_label2id == label2id:
            model = AutoModelForSequenceClassification.from_pretrained(model_sub)
            print(f"[warm] label set unchanged ({len(label2id)} intents) — "
                  "resuming full model.", flush=True)
        else:
            model = AutoModelForSequenceClassification.from_pretrained(
                model_sub, num_labels=len(label2id),
                id2label=id2label, label2id=label2id,
                ignore_mismatched_sizes=True,
            )
            old_model = AutoModelForSequenceClassification.from_pretrained(model_sub)
            copied = _copy_head_rows(old_model.state_dict(), model.state_dict(),
                                     old_label2id, label2id)
            del old_model
            shared = len(set(old_label2id) & set(label2id))
            fresh = len(set(label2id) - set(old_label2id))
            print(f"[warm] head remapped by intent name: {shared} kept, "
                  f"{fresh} new, {copied} head param(s) copied.", flush=True)
        return model.to(device), tokenizer, parent_meta
    except Exception as e:
        print(f"[warm] warm-start failed ({e}) — training FRESH.", flush=True)
        return None, None, None


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
    # --corpus: train from a PRE-MERGED corpus file (exported on the
    # laptop via `python -m core.export_corpus`). This is how Colab/GPU
    # training works: the laptop's Windows-only skills can't import on
    # Linux, so discovering them there would yield a different merged set
    # and a hash the laptop brain rejects. Training from the exported
    # corpus reproduces the laptop's exact hash. Without --corpus we
    # discover normally (native retrain on the same machine).
    if getattr(args, "corpus", None):
        print(f"[data] loading PRE-MERGED corpus: {args.corpus}", flush=True)
        with open(args.corpus, "r", encoding="utf-8") as _cf:
            intents = json.load(_cf)
    else:
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

    # ── Model + tokenizer (incremental warm-start when possible) ───
    model = tokenizer = None
    parent_meta: dict = {}
    mode = "fresh"
    if not args.fresh:
        warm_dir = args.warm_start or LIVE_DIR
        model, tokenizer, parent_meta = _load_warm_start(
            warm_dir, args.model, label2id, id2label, device)
        if model is not None:
            mode = "incremental"
            print(f"[model] INCREMENTAL — warm-started from {warm_dir}",
                  flush=True)
    if model is None:
        print(f"[model] FRESH — loading base checkpoint {args.model}...",
              flush=True)
        tokenizer = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForSequenceClassification.from_pretrained(
            args.model,
            num_labels=len(label2id),
            id2label=id2label,
            label2id=label2id,
        ).to(device)

    # Resolve epochs/lr now that the mode is known (CLI overrides win).
    incremental = mode == "incremental"
    if args.epochs is None:
        args.epochs = DEFAULT_EPOCHS_INCREMENTAL if incremental else DEFAULT_EPOCHS_FRESH
    if args.lr is None:
        args.lr = DEFAULT_LR_INCREMENTAL if incremental else DEFAULT_LR_FRESH
    print(f"[train] mode={mode}  epochs={args.epochs}  lr={args.lr}", flush=True)

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

    # ── Save to STAGING ────────────────────────────────────────────
    from core.model_registry import live_generation
    generation = live_generation() + 1
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
    # Reproducibility snapshot: the EXACT merged corpus this generation was
    # trained on travels with the model (intents.json / skills / learned
    # patterns keep evolving underneath — the snapshot doesn't).
    with open(os.path.join(OUT_DIR, "corpus_snapshot.json"), "w",
              encoding="utf-8") as f:
        json.dump(intents, f, ensure_ascii=False, indent=0)
    learned_src = os.path.join(_ROOT, "data", "learned_patterns.json")
    if os.path.exists(learned_src):
        import shutil
        shutil.copy(learned_src, os.path.join(OUT_DIR, "learned_snapshot.json"))
    metadata = {
        "model": args.model,
        "mode": mode,
        "generation": generation,
        "parent_trained_at": parent_meta.get("trained_at"),
        "epochs": args.epochs,
        "best_epoch": best_epoch,
        "best_val_acc": round(best_val_acc, 4),
        "golden_acc": None,
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
    }
    _write_metadata(metadata)

    print(f"\n[done] best val_acc = {best_val_acc*100:.2f}% at epoch {best_epoch}",
          flush=True)
    print(f"[done] staged at {OUT_DIR}  (generation {generation}, {mode})",
          flush=True)

    # Free the training copy before the gate double-loads from disk.
    del model
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    _gate_and_promote(args, intents, metadata)


def _write_metadata(metadata: dict) -> None:
    with open(os.path.join(OUT_DIR, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def _gate_and_promote(args, intents: dict, metadata: dict) -> None:
    """Golden-set regression gate, then staging → live promotion.

    Skips gracefully when the golden set or its deps are unavailable
    (e.g. the Colab bundle) — an absent gate passes, matching the old
    behaviour of writing straight to the live dir.
    """
    gate_ok, gate_msg = True, "no golden set — gate passed trivially"
    if args.gate:
        try:
            from core.intent_eval import (evaluate_model_dir, gate as _gate,
                                          load_golden, write_report)
            items = load_golden(known_intents=set(intents.keys()))
            if items:
                print(f"\n[gate] scoring on {len(items)} held-out golden items...",
                      flush=True)
                new_res = evaluate_model_dir(OUT_DIR, items)
                old_res = (evaluate_model_dir(LIVE_DIR, items)
                           if os.path.isdir(LIVE_DIR) else None)
                if new_res is None:
                    raise RuntimeError("staged model failed to load for eval")
                metadata["golden_acc"] = round(new_res.accuracy, 4)
                _write_metadata(metadata)
                write_report(new_res, "staging")
                gate_ok, gate_msg = _gate(old_res, new_res)
                print(f"[gate] staged golden acc: {new_res.accuracy*100:.1f}%",
                      flush=True)
        except Exception as e:
            gate_msg = f"gate unavailable ({e}) — passing"
    print(f"[gate] {'PASS' if gate_ok else 'FAIL'} — {gate_msg}", flush=True)

    if not gate_ok:
        print("\n[keep] staging retained, live model UNCHANGED.", flush=True)
        print("  inspect : python -m core.intent_eval compare", flush=True)
        print("  force   : python -m core.model_registry promote", flush=True)
        return
    if not args.promote:
        print("\n[stage] --no-promote given — promote later with:", flush=True)
        print("  python -m core.model_registry promote", flush=True)
        return

    from core.model_registry import PromotionError, promote_staging
    try:
        promote_staging(note=gate_msg)
    except PromotionError as e:
        print(f"\n[promote] FAILED: {e}", flush=True)
        return
    try:
        from core.learning_loop import LearningStore
        LearningStore().mark_trained()
    except Exception:
        pass
    print(f"\n[promote] generation {metadata['generation']} is LIVE at {LIVE_DIR}",
          flush=True)
    print("Restart AERIS for the brain to pick it up. "
          "Rollback: python -m core.model_registry rollback", flush=True)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"HF model id (default: {DEFAULT_MODEL})")
    p.add_argument("--epochs", type=int, default=None,
                   help=f"default: {DEFAULT_EPOCHS_INCREMENTAL} incremental / "
                        f"{DEFAULT_EPOCHS_FRESH} fresh")
    p.add_argument("--corpus", default=None,
                   help="Path to a pre-merged corpus JSON (from "
                        "export_corpus) — trains without skill discovery so "
                        "GPU/Colab produces a laptop-matching hash.")
    p.add_argument("--lr", type=float, default=None,
                   help=f"default: {DEFAULT_LR_INCREMENTAL} incremental / "
                        f"{DEFAULT_LR_FRESH} fresh")
    p.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    p.add_argument("--max-len", type=int, default=DEFAULT_MAX_LEN)
    p.add_argument("--val-ratio", type=float, default=DEFAULT_VAL_RATIO)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--fresh", action="store_true",
                   help="Ignore any previous model — train from the base "
                        "checkpoint (old behaviour)")
    p.add_argument("--warm-start", default=None, metavar="DIR",
                   help="Warm-start from this model dir instead of the live "
                        "one (e.g. an unzipped Colab model)")
    p.add_argument("--no-promote", dest="promote", action="store_false",
                   help="Leave the trained model in staging; promote "
                        "manually via core.model_registry")
    p.add_argument("--no-gate", dest="gate", action="store_false",
                   help="Skip the golden-set regression gate")
    p.add_argument("--no-augment", dest="augment", action="store_false",
                   help="Disable training-data augmentation")
    p.set_defaults(augment=True, promote=True, gate=True)
    return p.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    train(_parse_args())
