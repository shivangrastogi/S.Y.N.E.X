# %% [markdown]
# # AERIS brain · 02 — supervised fine-tuning (QLoRA, Unsloth)
#
# Trains the base model chosen in the Phase-0 bake-off on `final/train.jsonl` from notebook 01 —
# **brain v2**: one model, three heads (TURN chat/commands, NLU understanding, MEMORY extraction).
#
# * **Exactly the phone's prompt:** each sample is the prompt the app will build (system prompt with the offered tools, then the chat so far) plus the contract JSON. Loss is on the answer only (plan §7).
# * **Checkpoints go to Drive** every 100 steps; re-running resumes.
# * **Optional Optuna sweep:** learning rate, LoRA rank/alpha/dropout and epochs on a data slice. The study lives in Drive (SQLite), so it survives disconnects too.
# * **Eval:** at the end, every eval set is scored and an error file is written for reading the misses.
#
# GPU: a free T4 trains 1–2B models. An A100 (Colab Pro) makes the sweep practical.

# %%
from google.colab import drive
drive.mount("/content/drive")
import os, json, glob, random, subprocess
DRIVE_FOLDER = "/content/drive/MyDrive/mobile aeris"   # your Google Drive folder
DRIVE = "/content/aeris_drive"                          # space-free link to it (the ! shell commands need that)
if not os.path.exists(DRIVE):
    assert os.path.isdir(DRIVE_FOLDER), f"Folder not found: {DRIVE_FOLDER} - check the name in Google Drive"
    os.symlink(DRIVE_FOLDER, DRIVE)
CODE = "/content/aeris_brain"
if not os.path.exists(CODE):
    subprocess.run(["unzip", "-q", f"{DRIVE}/aeris_brain_code.zip", "-d", "/content"], check=True)
os.chdir(CODE)
!pip -q install unsloth optuna
DATA = f"{DRIVE}/data/final"

# %% [markdown]
# ## Config
# `BASE`: the bake-off winner. Check the exact repo name on huggingface.co/unsloth. Gemma 4 / Qwen3 names change as Unsloth publishes them.
# `TEMPLATE_KW`: chat-template switches that must match the phone (Qwen3 → no thinking block).

# %%
BASE = "unsloth/Qwen3-1.7B"                # or the Gemma 4 E2B repo the bake-off picked
TEMPLATE_KW = {"enable_thinking": False} if "qwen3" in BASE.lower() else {}
RUN = f"{DRIVE}/runs/{BASE.split('/')[-1]}-sft-v2"
MAX_LEN = 2048
# v2 on a free T4: notebook 01 already mixes exactly 40k examples (~35 % conversation), so train on
# all of it, 1 epoch (~4-6 h; resumes from Drive checkpoints after a disconnect).
TRAIN_LIMIT = None
EVAL_LIMIT = 600          # per eval set at the end (seed_real is always complete: 96)
HP = dict(lr=2e-4, r=32, alpha_mult=2, dropout=0.0, epochs=1, batch=4, grad_accum=16, warmup=0.04)
os.makedirs(RUN, exist_ok=True)

# %%
from unsloth import FastLanguageModel
import torch
from datasets import Dataset
from brain.contract import load_tools
from brain.render import samples

TOOLS = load_tools()

def load_base():
    model, tok = FastLanguageModel.from_pretrained(BASE, max_seq_length=MAX_LEN, load_in_4bit=True, dtype=None)
    return model, tok

def read(path, limit=None):
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    return rows[:limit] if limit else rows

def to_dataset(records, tok):
    from brain.contract import tools_for
    out = []
    for r in records:
        for s in samples(r, tools_for(r, TOOLS), tok, **TEMPLATE_KW):
            out.append({"prompt": s["prompt"], "completion": s["completion"]})
    return Dataset.from_list(out)

model, tok = load_base()
probe = to_dataset(read(f"{DATA}/train.jsonl", 2000), tok)
lens = sorted(len(tok(p + c).input_ids) for p, c in zip(probe["prompt"], probe["completion"]))
print("tokens/sample: median", lens[len(lens)//2], "p99", lens[int(len(lens)*.99)], "max", lens[-1])
print(probe[0]["prompt"][-600:], "\n>>>", probe[0]["completion"])

# %% [markdown]
# ## Train

# %%
from trl import SFTTrainer, SFTConfig

def make_trainer(model, tok, train_ds, eval_ds, hp, out_dir, max_steps=-1):
    model = FastLanguageModel.get_peft_model(
        model, r=hp["r"], lora_alpha=hp["r"] * hp["alpha_mult"], lora_dropout=hp["dropout"],
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none", use_gradient_checkpointing="unsloth", random_state=3407)
    cfg = SFTConfig(
        output_dir=out_dir, max_length=MAX_LEN, completion_only_loss=True, packing=False,
        per_device_train_batch_size=hp["batch"], gradient_accumulation_steps=hp["grad_accum"],
        learning_rate=hp["lr"], lr_scheduler_type="cosine", warmup_ratio=hp["warmup"],
        num_train_epochs=hp["epochs"], max_steps=max_steps, weight_decay=0.01,
        optim="adamw_8bit", bf16=torch.cuda.is_bf16_supported(), fp16=not torch.cuda.is_bf16_supported(),
        logging_steps=20, save_steps=100, save_total_limit=3,
        eval_strategy="steps" if eval_ds is not None else "no", eval_steps=200,
        per_device_eval_batch_size=hp["batch"], report_to="tensorboard", seed=3407)
    try:
        return SFTTrainer(model=model, processing_class=tok, train_dataset=train_ds, eval_dataset=eval_ds, args=cfg)
    except TypeError:   # older TRL
        return SFTTrainer(model=model, tokenizer=tok, train_dataset=train_ds, eval_dataset=eval_ds, args=cfg)

all_train = read(f"{DATA}/train.jsonl")
random.Random(1).shuffle(all_train)              # random slice keeps the mix proportions
train_ds = to_dataset(all_train[:TRAIN_LIMIT] if TRAIN_LIMIT else all_train, tok)
del all_train; import gc; gc.collect()   # the full 265k list is ~GBs of Python objects
dev_ds = to_dataset(read(f"{DATA}/dev.jsonl", 300), tok)
print(len(train_ds), "train samples,", len(dev_ds), "dev samples")
trainer = make_trainer(model, tok, train_ds, dev_ds, HP, RUN)
resume = bool(glob.glob(f"{RUN}/checkpoint-*"))
trainer.train(resume_from_checkpoint=resume)
model = trainer.model   # the LoRA-wrapped model — use this from here on
model.save_pretrained(f"{RUN}/adapter"); tok.save_pretrained(f"{RUN}/adapter")
json.dump({"base": BASE, "hp": HP, "template_kw": TEMPLATE_KW,
           "data_sha": json.load(open(f"{DATA}/train.jsonl.mix.json"))["_sha256"]},
          open(f"{RUN}/run.json", "w"), indent=2)

# %% [markdown]
# ## Evaluate on every eval set
# Greedy decoding, gold history for earlier turns. The **seed_real** score is the release gate (plan §1).

# %%
from brain.evaluate import predict, score_preds, save
from brain.score_v2 import is_task_set, score_task, task_prompts
FastLanguageModel.for_inference(model)
tok.padding_side = "left"
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

@torch.no_grad()
def generate(prompts, max_new=256):
    enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
    out = model.generate(**enc, max_new_tokens=max_new, do_sample=False, temperature=None, top_p=None,
                         pad_token_id=tok.pad_token_id)
    return tok.batch_decode(out[:, enc.input_ids.shape[1]:], skip_special_tokens=False)

reports = {}
for path in sorted(glob.glob(f"{DATA}/eval/*.jsonl")):
    name = os.path.basename(path).replace(".jsonl", "")
    recs = read(path, EVAL_LIMIT)
    if is_task_set(recs):   # NLU / MEMORY heads
        ps = task_prompts(recs, tok, TOOLS, **TEMPLATE_KW)
        preds = [o for i in range(0, len(ps), 32) for o in generate(ps[i:i + 32], max_new=160)]
        rep = score_task(recs, preds)
    else:
        preds = predict(recs, generate, tok, TOOLS, batch=32, **TEMPLATE_KW)
        rep = score_preds(recs, preds, TOOLS, title=name)
    save(f"{RUN}/errors.{name}.jsonl", rep.pop("errors"))
    reports[name] = rep
    print(rep["markdown"])
json.dump(reports, open(f"{RUN}/eval.json", "w"), indent=2)

# %% [markdown]
# ## Optional · hyper-parameter sweep (Optuna)
# Each trial trains on a 20k slice for 300 steps and scores **exact match on 400 dev turns**.
# T4: ~25 min/trial. A100: ~6 min. The study is stored in Drive, so it resumes after a disconnect.
# Copy the best params into `HP` above and run the full training again.

# %%
RUN_SWEEP = False
if RUN_SWEEP:
    import optuna
    slice_recs = read(f"{DATA}/train.jsonl", 20000)
    dev_recs = read(f"{DATA}/dev.jsonl", 400)

    def objective(trial):
        hp = dict(HP, lr=trial.suggest_float("lr", 5e-5, 3e-4, log=True),
                  r=trial.suggest_categorical("r", [16, 32, 64, 128]),
                  alpha_mult=trial.suggest_categorical("alpha_mult", [1, 2]),
                  dropout=trial.suggest_categorical("dropout", [0.0, 0.05]))
        m, t = load_base()
        tr = make_trainer(m, t, to_dataset(slice_recs, t), None, hp, f"/content/sweep/{trial.number}", max_steps=300)
        tr.train()
        global model, tok
        model, tok = tr.model, t
        FastLanguageModel.for_inference(model)
        tok.padding_side = "left"
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        rep = score_preds(dev_recs, predict(dev_recs, generate, tok, TOOLS, batch=32, **TEMPLATE_KW), TOOLS)
        del m, tr
        torch.cuda.empty_cache()
        return rep["exact_pct"] or 0.0

    study = optuna.create_study(direction="maximize", study_name="aeris-sft",
                                storage=f"sqlite:///{DRIVE}/optuna.db", load_if_exists=True)
    study.optimize(objective, n_trials=8)
    print("best:", study.best_params, study.best_value)
