"""Lite-ML boot seam — "don't load the brain's weights until a word needs them".

Part of the load-free work (docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md,
P2 "tiered router + lazy ML"). Two things make AERIS heavy at rest:

1. **Import weight** — `sentence_transformers`/`torch` used to be module-level
   imports in `core.intent_classifier` / `core.intent_model`, so merely
   building a `JarvisBrain(lazy=True)` cost ~15 s and hundreds of MB. That is
   fixed unconditionally (those imports are now inside the functions that
   need them) and needs no flag.

2. **Boot weight** — `setup_iter()` eagerly loads the encoder, the neural
   head, the k-NN index, spaCy NER and the chat gate before the assistant
   will accept its first word. `AERIS_LITE_ML=1` skips all five and lets the
   tiered router (`JarvisBrain.predict`) pull them in on the first utterance
   that actually misses the exact-match / arithmetic / anchor tiers.

Lite boot is behaviour-preserving, not behaviour-reducing: the moment the
heavy tier is needed the brain loads it and fires its ml-loaded hooks, which
switch on the extras (spaCy, chat gate) that boot skipped. The cost is moved,
not removed — the first heavy utterance pays what boot used to.

Off by default: `AERIS_LITE_ML=1` opts in, exactly like `AERIS_SPLIT_BRAIN`.
"""
from __future__ import annotations

import os
from typing import Any, Optional


def lite_ml_enabled(flag: Optional[Any] = None) -> bool:
    """True when the engine should boot without loading any ML weights."""
    v = flag if flag is not None else os.environ.get("AERIS_LITE_ML", "")
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def prewarm_enabled(flag: Optional[Any] = None) -> bool:
    """True unless ``AERIS_PREWARM`` is explicitly off.

    Only consulted after a lite boot: the engine then loads the heavy tier
    on a background thread (``JarvisMainEngine.start_background_warmup``),
    so boot stays fast AND the first heavy command doesn't pay the load.
    ``AERIS_PREWARM=0`` restores lite boot's original, fully lazy behaviour
    for when resting memory matters more than first-command latency.
    """
    v = flag if flag is not None else os.environ.get("AERIS_PREWARM", "1")
    return str(v).strip().lower() not in ("0", "false", "no", "off")
