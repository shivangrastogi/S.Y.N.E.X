"""One-command retrain pipeline — the whole learning loop as a single ritual.

    python -m core.retrain

runs, in order:

    1. preflight   — AERIS running? (auto stage-only if yes), deps present?
    2. harvest     — feedback DB → learned_patterns.json  (skip: --skip-harvest)
    3. export      — fresh merged corpus + hash (Colab bundle stays in sync)
    4. train       — core.train_intent in a subprocess (incremental by
                     default; gate + promote happen inside the trainer)
    5. report      — registry status + health summary + next steps

Modes:

    python -m core.retrain --dry-run     # show the plan, change nothing
    python -m core.retrain --colab       # steps 1-3 + rebuild the Colab
                                         # bundle; prints upload steps
                                         # (GPU training on Colab)
    python -m core.retrain --fresh       # forward: from-scratch training
    python -m core.retrain --epochs 8    # forward epochs to the trainer
    python -m core.retrain --no-promote  # forward: stage only

Why a subprocess for training: torch gets a clean process (no Qt/OpenMP
cohabitation), Ctrl+C kills cleanly, and an OOM can't take the pipeline
state with it.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import subprocess
import sys
import zipfile

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE_PATH = os.path.join(_ROOT, "aeris_train_bundle.zip")
LIVE_DIR = os.path.join(_ROOT, "data", "models", "intent_neural")


# ---------------------------------------------------------------------- #
#  Steps                                                                  #
# ---------------------------------------------------------------------- #

def preflight() -> dict:
    """Return {'aeris_running': bool, 'deps_ok': bool, 'mode': str}."""
    running = False
    try:
        from core.single_instance import SingleInstance
        inst = SingleInstance("aeris.gui")
        running = inst.already_running()
        inst.release()   # never hold the mutex — AERIS must stay launchable
    except Exception as e:
        log.warning("[retrain] instance check failed: %s", e)

    deps_ok = all(importlib.util.find_spec(m) is not None
                  for m in ("torch", "transformers", "numpy"))
    mode = "incremental" if os.path.isdir(os.path.join(LIVE_DIR, "model")) \
        else "fresh"
    return {"aeris_running": running, "deps_ok": deps_ok, "mode": mode}


def harvest() -> None:
    from core.learning_loop import LearningStore
    store = LearningStore()
    r = store.harvest()
    print(f"[harvest] scanned {r.scanned} rows -> +{r.added} new, "
          f"{r.bumped} bumped, {r.skipped_known + r.skipped_exact} skipped")
    s = store.status()
    print(f"[harvest] store: {s['trainable_samples']} trainable "
          f"({s['new_since_last_train']} new since last train)")


def export_corpus() -> str:
    """Re-export the merged corpus; returns the fresh hash."""
    from core.intent_loader import load_all_intents, intents_hash
    from core.atomic_io import write_atomic_json
    intents = load_all_intents()
    h = intents_hash(intents)
    out = os.path.join(_ROOT, "data", "training_corpus.json")
    write_atomic_json(out, intents, indent=0)
    n_pat = sum(len(v.get("patterns", [])) for v in intents.values())
    print(f"[export] {len(intents)} intents · {n_pat} patterns  hash={h}")
    return h


def build_colab_bundle() -> str:
    """core/*.py + merged corpus + golden set → aeris_train_bundle.zip."""
    core_dir = os.path.join(_ROOT, "core")
    with zipfile.ZipFile(BUNDLE_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(core_dir)):
            if name.endswith(".py"):
                z.write(os.path.join(core_dir, name), f"core/{name}")
        z.write(os.path.join(_ROOT, "data", "training_corpus.json"),
                "training_corpus.json")
        golden = os.path.join(_ROOT, "data", "intent_eval.json")
        if os.path.exists(golden):
            z.write(golden, "data/intent_eval.json")
    kb = os.path.getsize(BUNDLE_PATH) // 1024
    print(f"[bundle] rebuilt {BUNDLE_PATH} ({kb} KB)")
    return BUNDLE_PATH


def run_training(forward_args: list[str]) -> int:
    cmd = [sys.executable, "-m", "core.train_intent"] + forward_args
    print(f"[train] {' '.join(cmd)}\n", flush=True)
    # Inherit stdout/stderr so epoch logs stream live.
    return subprocess.run(cmd, cwd=_ROOT).returncode


def post_report() -> None:
    print("\n" + "─" * 52)
    try:
        from core.brain_health import collect, format_report
        print(format_report(collect(window_days=7)))
    except Exception as e:
        log.warning("[retrain] health report failed: %s", e)
    print("─" * 52)


# ---------------------------------------------------------------------- #
#  Pipeline                                                               #
# ---------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dry-run", action="store_true",
                   help="Show the plan; change nothing")
    p.add_argument("--colab", action="store_true",
                   help="Prepare the Colab bundle instead of training locally")
    p.add_argument("--skip-harvest", action="store_true",
                   help="Don't mine the feedback DB first")
    p.add_argument("--fresh", action="store_true",
                   help="Forward to trainer: from-scratch training")
    p.add_argument("--no-promote", action="store_true",
                   help="Forward to trainer: stage only")
    p.add_argument("--epochs", type=int, default=None,
                   help="Forward to trainer")
    args = p.parse_args(argv)

    pf = preflight()
    print(f"[preflight] mode={pf['mode']}  aeris_running={pf['aeris_running']}  "
          f"deps={'ok' if pf['deps_ok'] else 'MISSING torch/transformers'}")

    stage_only = args.no_promote
    if pf["aeris_running"] and not args.colab:
        # A live AERIS holds the model files (mmapped safetensors) — a
        # promote would fail mid-move. Train to staging instead.
        stage_only = True
        print("[preflight] AERIS chal raha hai -> training STAGE-ONLY hogi.\n"
              "            Baad mein AERIS band karke: "
              "python -m core.model_registry promote")

    if args.dry_run:
        _print_plan(pf, args, stage_only)
        return 0
    if not pf["deps_ok"] and not args.colab:
        print("[abort] torch/transformers missing — use --colab, or install deps.")
        return 1

    if not args.skip_harvest:
        harvest()
    fresh_hash = export_corpus()

    if args.colab:
        build_colab_bundle()
        print("\n[colab] Next steps (COLAB_TRAINING.md has the full guide):")
        print("  1. colab.research.google.com -> new notebook -> T4 GPU")
        print("  2. upload aeris_train_bundle.zip, unzip, cd into it")
        print("  3. !pip -q install transformers torch \"numpy<2.3\" sentence-transformers")
        print("  4. !python -m core.train_intent --corpus training_corpus.json --epochs 8")
        print(f"  5. final hash MUST be {fresh_hash}")
        print("  6. zip data/models/intent_neural, download, replace on laptop, "
              "restart AERIS")
        return 0

    forward: list[str] = []
    if args.fresh:
        forward.append("--fresh")
    if stage_only:
        forward.append("--no-promote")
    if args.epochs is not None:
        forward += ["--epochs", str(args.epochs)]
    rc = run_training(forward)
    if rc != 0:
        print(f"\n[train] FAILED (exit {rc}) — live model untouched.")
        return rc

    post_report()
    if stage_only:
        print("\nDone (staged). AERIS band karke: "
              "python -m core.model_registry promote  -> phir AERIS restart.")
    else:
        print("\nDone. AERIS restart karo — boot log mein "
              "\"Neural classifier ACTIVE\" dikhna chahiye.")
    return 0


def _print_plan(pf: dict, args, stage_only: bool) -> None:
    try:
        from core.learning_loop import LearningStore
        s = LearningStore().status()
        pending = (f"{s['trainable_samples']} trainable learned samples "
                   f"({s['new_since_last_train']} new since last train)")
    except Exception:
        pending = "learning store unreadable"
    steps = []
    if not args.skip_harvest:
        steps.append("harvest feedback DB -> learned_patterns.json")
    steps.append("re-export merged corpus (+hash)")
    if args.colab:
        steps.append("rebuild aeris_train_bundle.zip + print Colab steps")
    else:
        steps.append(f"train ({'fresh' if args.fresh else pf['mode']}"
                     f"{', stage-only' if stage_only else ', gate + promote'})")
        steps.append("health report + next steps")
    print(f"\n[plan] {pending}")
    for i, s_ in enumerate(steps, 1):
        print(f"  {i}. {s_}")
    print("\n(dry run — kuch nahi badla)")


if __name__ == "__main__":
    sys.exit(main())
