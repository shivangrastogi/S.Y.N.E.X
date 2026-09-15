"""Model registry — staging → promote → archive → rollback for the intent model.

Before this module the trainer wrote straight into the live model dir
(``data/models/intent_neural``): a bad run or a mid-save crash nuked the
only working model. Now every training run lands in a STAGING dir, passes
the golden-eval gate, and only then gets promoted — with the previous
live model archived so one command rolls back.

Layout (all under ``data/models/``)::

    intent_neural/            LIVE — what the brain loads (unchanged path)
    intent_neural_staging/    where train_intent writes; deleted on promote
    intent_neural_archive/
        gen003_20260719-101500/   previous live models, newest = rollback target
    train_history.json        append-only lineage of every promoted model

CLI:
    python -m core.model_registry history     # lineage of promoted models
    python -m core.model_registry rollback    # restore the previous model
    python -m core.model_registry status      # live/staging/archive summary
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
from typing import Optional

from core.atomic_io import write_atomic_json

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(_ROOT, "data", "models")
LIVE_DIR = os.path.join(MODELS_DIR, "intent_neural")
STAGING_DIR = os.path.join(MODELS_DIR, "intent_neural_staging")
ARCHIVE_DIR = os.path.join(MODELS_DIR, "intent_neural_archive")
HISTORY_PATH = os.path.join(MODELS_DIR, "train_history.json")

KEEP_ARCHIVES = 2   # transformer dirs are ~500 MB each — keep disk sane


class PromotionError(RuntimeError):
    """Raised when staging → live could not complete. Staging is left
    intact so nothing is lost; the live model is restored if it had
    already been moved aside."""


def _read_metadata(model_dir: str) -> dict:
    path = os.path.join(model_dir, "metadata.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def live_generation() -> int:
    """Generation counter of the live model (0 = no model yet)."""
    return int(_read_metadata(LIVE_DIR).get("generation", 1)) if \
        os.path.isdir(LIVE_DIR) else 0


def promote_staging(staging_dir: str = STAGING_DIR,
                    live_dir: str = LIVE_DIR,
                    archive_dir: str = ARCHIVE_DIR,
                    note: str = "") -> str:
    """Archive the live model (if any) and move staging into its place.

    Returns the live dir path. Raises ``PromotionError`` if any move
    fails — most commonly because AERIS is running and holds the model
    files open (Windows locks mmapped safetensors). In that case close
    AERIS and re-run ``python -m core.model_registry promote``.
    """
    if not os.path.isdir(staging_dir):
        raise PromotionError(f"no staging model at {staging_dir}")

    meta = _read_metadata(staging_dir)
    gen = int(meta.get("generation", live_generation() + 1))
    stamp = time.strftime("%Y%m%d-%H%M%S")

    moved_live: Optional[str] = None
    if os.path.isdir(live_dir):
        os.makedirs(archive_dir, exist_ok=True)
        moved_live = os.path.join(
            archive_dir, f"gen{live_generation():03d}_{stamp}")
        try:
            shutil.move(live_dir, moved_live)
        except Exception as e:
            raise PromotionError(
                f"could not archive live model ({e}). Is AERIS still "
                "running? Close it and retry: python -m core.model_registry promote"
            ) from e
    try:
        shutil.move(staging_dir, live_dir)
    except Exception as e:
        # Restore the live model we just archived so the brain still works.
        if moved_live and not os.path.isdir(live_dir):
            try:
                shutil.move(moved_live, live_dir)
            except Exception:
                log.error("[registry] restore of archived live model FAILED; "
                          "recover manually from %s", moved_live)
        raise PromotionError(f"could not move staging into place: {e}") from e

    _prune_archives(archive_dir)
    record_history({
        "event": "promote",
        "generation": gen,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "best_val_acc": meta.get("best_val_acc"),
        "golden_acc": meta.get("golden_acc"),
        "mode": meta.get("mode", "fresh"),
        "num_intents": meta.get("num_intents"),
        "num_train_samples": meta.get("num_train_samples"),
        "note": note,
    })
    log.info("[registry] promoted generation %d -> %s", gen, live_dir)
    return live_dir


def rollback(live_dir: str = LIVE_DIR,
             archive_dir: str = ARCHIVE_DIR) -> Optional[str]:
    """Restore the newest archived model as live. The rejected live model
    is parked in the archive as ``rejected_<ts>`` (pruned like the rest).

    Returns the restored dir path, or None when there is no archive.
    """
    newest = _newest_archive(archive_dir)
    if newest is None:
        log.info("[registry] nothing to roll back to — archive is empty")
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if os.path.isdir(live_dir):
        shutil.move(live_dir, os.path.join(archive_dir, f"rejected_{stamp}"))
    shutil.move(newest, live_dir)
    _prune_archives(archive_dir)
    record_history({
        "event": "rollback",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "restored_from": os.path.basename(newest),
    })
    log.info("[registry] rolled back to %s", os.path.basename(newest))
    return live_dir


def _newest_archive(archive_dir: str = ARCHIVE_DIR) -> Optional[str]:
    if not os.path.isdir(archive_dir):
        return None
    dirs = [os.path.join(archive_dir, d) for d in os.listdir(archive_dir)
            if os.path.isdir(os.path.join(archive_dir, d))
            and not d.startswith("rejected_")]
    if not dirs:
        return None
    return max(dirs, key=os.path.getmtime)


def _prune_archives(archive_dir: str = ARCHIVE_DIR,
                    keep: int = KEEP_ARCHIVES) -> None:
    if not os.path.isdir(archive_dir):
        return
    dirs = sorted(
        (os.path.join(archive_dir, d) for d in os.listdir(archive_dir)
         if os.path.isdir(os.path.join(archive_dir, d))),
        key=os.path.getmtime, reverse=True,
    )
    for stale in dirs[keep:]:
        try:
            shutil.rmtree(stale)
            log.info("[registry] pruned old archive %s", os.path.basename(stale))
        except Exception as e:
            log.warning("[registry] could not prune %s: %s", stale, e)


# ---------------------------------------------------------------------- #
#  Lineage                                                                #
# ---------------------------------------------------------------------- #

def record_history(entry: dict) -> None:
    entries = history()
    entries.append(entry)
    write_atomic_json(HISTORY_PATH, entries)


def history() -> list[dict]:
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------- #
#  CLI                                                                    #
# ---------------------------------------------------------------------- #

def _cli_status() -> None:
    for label, path in (("live", LIVE_DIR), ("staging", STAGING_DIR)):
        if os.path.isdir(path):
            m = _read_metadata(path)
            print(f"  {label:8s}: gen {m.get('generation', '?')}  "
                  f"val_acc={m.get('best_val_acc', '?')}  "
                  f"golden={m.get('golden_acc', '?')}  "
                  f"mode={m.get('mode', '?')}  trained={m.get('trained_at', '?')}")
        else:
            print(f"  {label:8s}: (none)")
    n = 0
    if os.path.isdir(ARCHIVE_DIR):
        n = sum(1 for d in os.listdir(ARCHIVE_DIR)
                if os.path.isdir(os.path.join(ARCHIVE_DIR, d)))
    print(f"  archive : {n} model(s)")


def _cli_history() -> None:
    entries = history()
    if not entries:
        print("No training history yet.")
        return
    for e in entries:
        if e.get("event") == "promote":
            print(f"  gen {e.get('generation', '?'):>3}  {e.get('at', '')}  "
                  f"{e.get('mode', ''):11s}  val={e.get('best_val_acc')}  "
                  f"golden={e.get('golden_acc')}  "
                  f"intents={e.get('num_intents')}  {e.get('note', '')}")
        else:
            print(f"  ROLLBACK  {e.get('at', '')}  <- {e.get('restored_from', '')}")


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        _cli_status()
    elif cmd == "history":
        _cli_history()
    elif cmd == "promote":
        try:
            promote_staging(note="manual promote")
            print("Promoted staging -> live. Restart AERIS to load it.")
        except PromotionError as e:
            print(f"Promote failed: {e}")
            return 1
    elif cmd == "rollback":
        restored = rollback()
        print("Rolled back — restart AERIS." if restored else "Archive empty.")
    else:
        print(__doc__.split("CLI:")[-1])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
