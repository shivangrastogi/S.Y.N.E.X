# Training AERIS's intent brain on Google Colab (free GPU)

CPU training is ~1 hr/epoch (~8–15 hrs). Colab's free **T4 GPU** does it
in **~1–2 min/epoch** → the whole thing in well under an hour, and your
laptop stays free.

The model must match your laptop's intent corpus exactly (else the brain
rejects it), so we train from an **exported corpus** — not by re-scanning
skills on Linux (your Windows-only skills wouldn't import there and the
hash would differ).

Laptop corpus hash to match: **`504a659d43bb1e0c16466c5ad2f1d986`**
(586 intents · corpus). The trained model prints its hash at the
end — it must equal this.

---

## Step 0 — files you already have (in the project folder)
- `aeris_train_bundle.zip`  (~450 KB — core code + `training_corpus.json` + golden eval set)

If you edit `data/intents.json` or skills later, regenerate it first:
```
python -m core.export_corpus
```
then re-zip (the bundle is just `core/` + `data/training_corpus.json`).

---

## Step 1 — new Colab notebook, set GPU
1. Go to **colab.research.google.com** → New notebook.
2. Menu **Runtime → Change runtime type → Hardware accelerator → T4 GPU** → Save.

## Step 2 — upload the bundle (Cell 1)
```python
from google.colab import files
up = files.upload()          # pick aeris_train_bundle.zip
import zipfile, os
with zipfile.ZipFile('aeris_train_bundle.zip') as z:
    z.extractall('aeris')
os.chdir('aeris')
print('files:', os.listdir('.'))
```

## Step 3 — install deps (Cell 2)
```python
!pip -q install "transformers>=4.44" "torch" "numpy<2.3"
```

## Step 4 — train on GPU (Cell 3)
```python
# 8 epochs is plenty — accuracy plateaus (epoch 3→4 was +1.6%).
!python -m core.train_intent --corpus training_corpus.json --epochs 8
```
Watch the log: `[device] cuda  (cuda=True)` confirms the GPU. Each epoch
should take ~1–3 min. At the end it prints the saved hash — confirm it is
`504a659d43bb1e0c16466c5ad2f1d986`.

## Step 5 — download the trained model (Cell 4)
```python
import shutil
from google.colab import files
shutil.make_archive('intent_neural', 'zip', 'data/models/intent_neural')
files.download('intent_neural.zip')
```

## Step 6 — install it on the laptop
1. Unzip `intent_neural.zip`.
2. Replace the folder at:
   `New version- 3.0\data\models\intent_neural\`
   (it should contain `model/`, `tokenizer/`, `labels.json`, `metadata.json`)
3. Restart AERIS (`AERIS.bat`). On boot the log will say
   **"Neural classifier ACTIVE (primary router)"** instead of the
   hash-drift / k-NN message — that's the confirmation it loaded.

---

### Notes
- `--corpus` skips skill discovery, so Colab never needs your Windows
  libs — only `torch`, `transformers`, `numpy`.
- If the final hash does NOT match `504a659d…`, your laptop's
  `intents.json`/skills changed after the export — re-run
  `python -m core.export_corpus`, re-zip, retrain.
- Free-tier Colab disconnects after idle/12 h. 8 epochs finishes long
  before that; just keep the tab active.

---

## Incremental training (2026-07-19 upgrade)

`train_intent.py` is now **incremental by default**: if a previous model
exists it warm-starts from those weights (head rows mapped by intent
name; new intents get fresh rows) and needs only ~4 low-LR epochs.
Training always lands in `data/models/intent_neural_staging/`, is scored
on the golden set (`data/intent_eval.json`), and auto-promotes to
`intent_neural/` only if it doesn't regress (old model archived —
`python -m core.model_registry rollback` restores it).

On Colab:
- Fresh run (nothing else needed): the bundle has no previous model, so
  it trains from the base checkpoint exactly like before. The promote
  step still ends at `data/models/intent_neural` — Step 5 unchanged.
- Incremental run: also upload your current `intent_neural.zip`, unzip
  it to `data/models/intent_neural`, then just run the trainer — it
  warm-starts automatically. 3-4 epochs is enough.
- Golden gate on Colab: add `sentence-transformers` to the pip cell if
  you want the gate to actually score; otherwise it passes trivially
  (the laptop can re-check later with `python -m core.intent_eval`).

Full workflow: see `docs/INCREMENTAL_TRAINING.md`.
