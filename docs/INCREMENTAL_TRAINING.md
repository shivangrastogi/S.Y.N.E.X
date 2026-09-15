# AERIS Incremental Intelligence — retrain loop that compounds

*Added 2026-07-19. AERIS ab har retrain pe pichle model ke upar seekhta
hai — usage se data khud jama hota hai, model generation-by-generation
smarter hota hai, aur ek bhi kharab retrain live model ko kharab nahi
kar sakta.*

## The loop (the whole thing)

```
   you use AERIS normally
        │  every utterance + outcome logged (core/feedback.py → feedback_log.sqlite)
        ▼
   python -m core.learning_loop harvest
        │  corrections + accepted phrases → data/learned_patterns.json
        │  (k-NN + exact-match pick them up IMMEDIATELY on next boot)
        ▼
   python -m core.train_intent
        │  warm-starts from the live model (incremental, ~4 epochs)
        │  → data/models/intent_neural_staging/
        │  → scored on data/intent_eval.json (95 held-out golden items)
        │  → promoted ONLY if it doesn't regress; old model archived
        ▼
   restart AERIS  →  "Neural classifier ACTIVE"  →  keep using it → repeat
```

`python -m core.learning_loop status` batata hai kab retrain worth it
hai (default: 15+ naye samples pe recommend karta hai).

> **Shortcut (v2)**: poora loop ek command mein — `python -m core.retrain`
> (ya `--colab` GPU ke liye, `--dry-run` plan dekhne ke liye). Voice se
> status: **"kya seekha tumne"** / **"brain health"**. Poora design:
> `docs/INTELLIGENCE_SYSTEM.md`.

## Commands

| Command | What it does |
|---|---|
| `python -m core.retrain` | ONE command: harvest → export → train → gate → promote |
| `python -m core.retrain --colab` | harvest + export + Colab bundle + steps |
| `python -m core.retrain --dry-run` | plan dikhao, kuch mat badlo |
| `python -m core.brain_health` | health score, confusions, trend, advisor |
| `python -m core.learning_loop status` | kitna naya seekha, retrain due hai ya nahi |
| `python -m core.learning_loop harvest` | feedback DB → learned_patterns.json |
| `python -m core.learning_loop list` | learned samples per intent (`[?]` = review) |
| `python -m core.learning_loop review-ai` | review queue Qwen suggestion ke saath nipta lo |
| `python -m core.learning_loop reject "<text>"` | galat sample — kabhi train na ho |
| `python -m core.learning_loop approve "<text>"` | review → trainable |
| `python -m core.learning_loop teach "<text>" <intent>` | manual gold sample |
| `python -m core.train_intent` | incremental retrain + gate + promote |
| `python -m core.train_intent --fresh` | base checkpoint se full retrain |
| `python -m core.train_intent --no-promote` | staging tak hi; promote baad mein |
| `python -m core.intent_eval` | live model ko golden set pe score karo |
| `python -m core.intent_eval compare` | live vs staging, gate verdict ke saath |
| `python -m core.intent_eval knn` | k-NN baseline (neural kitna aage hai) |
| `python -m core.model_registry status` | live / staging / archive summary |
| `python -m core.model_registry history` | promoted generations ki lineage |
| `python -m core.model_registry rollback` | pichla model wapas (one command) |
| `python -m core.model_registry promote` | staging → live (gate-fail override) |

## How incremental training works

- **Warm start**: `data/models/intent_neural` ke fine-tuned weights se
  shuru hota hai, base checkpoint se nahi. Body (transformer) poora
  transfer hota hai.
- **Head remap by name**: intent set badalne par label ids shift ho
  jaate hain (sorted order). Naya head intent-NAME se map hota hai —
  purane intents apni seekhi hui rows rakhte hain, naye intents ko
  fresh rows milti hain. (`_copy_head_rows` in `core/train_intent.py`,
  tested in `tests/test_incremental_training.py`.)
- **Gentle LR**: incremental default `lr 2e-5`, 4 epochs — purani
  knowledge protect hoti hai (vs fresh `5e-5`, 15 epochs).
- **Same-arch guard**: agar `--model` pichle se alag hai to warm start
  skip → fresh. `--warm-start <dir>` se koi bhi model dir (e.g. unzipped
  Colab model) parent ban sakta hai.

## Safety rails

- **Golden gate**: `data/intent_eval.json` ke 95 paraphrases kabhi
  training corpus mein nahi jaate — ye generalisation napte hain. Naya
  model comparable subset pe purane se (margin 2pt ke andar) girna
  nahi chahiye, warna staging mein hi ruk jaata hai.
- **Staging + archive**: live model kabhi overwrite nahi hota — archive
  hota hai (last 2 rakhta hai, ~500MB each). `rollback` ek command hai.
- **Hash discipline** (pehle jaisa): harvest ke baad corpus hash badal
  jaata hai → neural model hash-mismatch pe k-NN fallback. Isliye
  harvest hamesha retrain ke theek pehle karo, beech mein nahi.
- **Poison guard**: sirf explicit signals harvest hote hain (corrected
  = gold; accepted = positive, conf < 0.60 wale review queue mein).
  Exact-match (conf 1.0) rows skip — unme naya kuch nahi. Baaki
  un-feedback'd utterances purane `pending_patterns` + `review_cli`
  flow mein hi rehte hain.

## Files

| Path | Role |
|---|---|
| `core/learning_loop.py` | harvester + learned-samples store + CLI |
| `data/learned_patterns.json` | usage se seekhe samples (provenance ke saath) |
| `core/model_registry.py` | staging/promote/archive/rollback + lineage |
| `data/models/train_history.json` | har promoted generation ka record |
| `core/intent_eval.py` | golden evaluator + promote gate |
| `data/intent_eval.json` | 95 held-out golden paraphrases (kabhi train NA karna) |
| `core/train_intent.py` | trainer — ab incremental-by-default |
| `core/intent_loader.py` | learned patterns ko canonical corpus mein merge karta hai |

## Golden set ka rule

`data/intent_eval.json` ke phrases ko **kabhi bhi** `intents.json`,
skills, ya `learned_patterns.json` mein mat daalo — jis din wo training
mein aa gaye, eval number jhooth bolne lagega. Naye intents add karo to
2-3 fresh paraphrases golden set mein bhi daal do (patterns se alag
wording mein).
