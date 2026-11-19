# %% [markdown]
# # AERIS brain · 03 — preference tuning (DPO) and optional GRPO
#
# Starts from the SFT adapter (notebook 02) and sharpens the decisions it *almost* gets right (plan §7, S2/S3):
#
# * **DPO** on near-miss pairs from `brain.prefs`: guessing instead of asking, asking when everything was said, a sibling tool, a corrupted name/number, or answering live info from memory.
# * **GRPO** (optional) with a verifiable reward. The scorer grades each sampled answer against the gold label: right tool + exact args = full reward. No reward model is needed, and the scorer can't be fooled by fluent wrong JSON.
#
# Gate: keep the new adapter only if `seed_real` exact-match does not drop.

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
!pip -q install unsloth
DATA = f"{DRIVE}/data/final"
SFT_RUN = f"{DRIVE}/runs/Qwen3-1.7B-sft-v1"      # the run folder from notebook 02
cfg = json.load(open(f"{SFT_RUN}/run.json"))
TEMPLATE_KW = cfg["template_kw"]
OUT = SFT_RUN.replace("-sft-", "-dpo-")
os.makedirs(OUT, exist_ok=True)

# %%
from unsloth import FastLanguageModel, PatchDPOTrainer
PatchDPOTrainer()
import torch
from datasets import Dataset
from trl import DPOTrainer, DPOConfig
from brain.contract import load_tools, tools_for
from brain.prefs import pairs
from brain.render import chat, end_marker

TOOLS = load_tools()
model, tok = FastLanguageModel.from_pretrained(f"{SFT_RUN}/adapter", max_seq_length=2048, load_in_4bit=True)
END = end_marker(tok, **TEMPLATE_KW)

def read(path, limit=None):
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    return rows[:limit] if limit else rows

def prompt_for(record, turn):
    msgs = chat(record, tools_for(record, TOOLS))
    seen = -1
    for i, m in enumerate(msgs):
        if m["role"] == "assistant":
            seen += 1
            if seen == turn:
                return tok.apply_chat_template(msgs[:i], tokenize=False, add_generation_prompt=True, **TEMPLATE_KW)

recs = read(f"{DATA}/train.jsonl", 60000)
ps = pairs([r for r in recs if not r.get("tool_specs")], TOOLS, seed=7)
random.Random(7).shuffle(ps)
ps = ps[:20000]
print({k: sum(p["kind"] == k for p in ps) for k in sorted({p["kind"] for p in ps})})
dpo_ds = Dataset.from_list([{"prompt": prompt_for(p["record"], p["turn"]),
                             "chosen": p["chosen"] + END, "rejected": p["rejected"] + END} for p in ps])

# %%
args = DPOConfig(output_dir=OUT, beta=0.1, learning_rate=5e-6, lr_scheduler_type="cosine", warmup_ratio=0.05,
                 num_train_epochs=1, per_device_train_batch_size=4, gradient_accumulation_steps=8,
                 max_length=2048, max_prompt_length=1800, optim="adamw_8bit",
                 bf16=torch.cuda.is_bf16_supported(), fp16=not torch.cuda.is_bf16_supported(),
                 logging_steps=20, save_steps=200, save_total_limit=2, report_to="tensorboard", seed=3407)
try:
    trainer = DPOTrainer(model=model, ref_model=None, args=args, train_dataset=dpo_ds, processing_class=tok)
except TypeError:
    trainer = DPOTrainer(model=model, ref_model=None, args=args, train_dataset=dpo_ds, tokenizer=tok)
trainer.train(resume_from_checkpoint=bool(glob.glob(f"{OUT}/checkpoint-*")))
model = trainer.model
model.save_pretrained(f"{OUT}/adapter"); tok.save_pretrained(f"{OUT}/adapter")
json.dump(dict(cfg, stage="dpo", parent=SFT_RUN), open(f"{OUT}/run.json", "w"), indent=2)

# %% [markdown]
# ## Gate: compare against SFT on the eval sets
# Same eval code as notebook 02. Keep DPO only if `seed_real` exact-match is ≥ the SFT run's.

# %%
from brain.evaluate import predict, score_preds, save
FastLanguageModel.for_inference(model)
tok.padding_side = "left"
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

@torch.no_grad()
def generate(prompts, max_new=256):
    enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
    out = model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=tok.pad_token_id)
    return tok.batch_decode(out[:, enc.input_ids.shape[1]:], skip_special_tokens=False)

sft = json.load(open(f"{SFT_RUN}/eval.json"))
reports = {}
for path in sorted(glob.glob(f"{DATA}/eval/*.jsonl")):
    name = os.path.basename(path).replace(".jsonl", "")
    recs_e = read(path, 1500)
    rep = score_preds(recs_e, predict(recs_e, generate, tok, TOOLS, batch=32, **TEMPLATE_KW), TOOLS, title=name)
    save(f"{OUT}/errors.{name}.jsonl", rep.pop("errors"))
    reports[name] = rep
    print(f"{name}: exact {sft.get(name, {}).get('exact_pct')} → {rep['exact_pct']} | "
          f"decision {sft.get(name, {}).get('decision_pct')} → {rep['decision_pct']}")
json.dump(reports, open(f"{OUT}/eval.json", "w"), indent=2)

# %% [markdown]
# ## Optional · GRPO with a verifiable reward
# Best on an A100: it samples several answers per prompt. The reward comes from the scorer, so it is cheap and exact.

# %%
RUN_GRPO = False
if RUN_GRPO:
    from trl import GRPOTrainer, GRPOConfig
    from brain.score import score_pair
    from brain.render import offered_specs

    def reward(prompts, completions, gold, allowed, **kw):
        out = []
        for c, g, al in zip(completions, gold, allowed):
            text = c if isinstance(c, str) else c[-1]["content"]
            s = score_pair(json.loads(g), text.split(END)[0], TOOLS, set(json.loads(al)))
            r = 0.2 * s["valid"] + 0.3 * s["type"]
            if s["action"] is not None:
                r += 0.5 * bool(s["action"]) + 1.0 * bool(s["exact"])
            elif s["type"]:
                r += 1.0
            out.append(r)
        return out

    rows = []
    for r in read(f"{DATA}/train.jsonl", 30000):
        if r.get("tool_specs") or len(r["messages"]) != 2:
            continue
        rows.append({"prompt": prompt_for(r, 0), "gold": json.dumps(r["messages"][1]["content"]),
                     "allowed": json.dumps(r.get("tools") or list(TOOLS))})
    gargs = GRPOConfig(output_dir=OUT.replace("-dpo-", "-grpo-"), learning_rate=1e-6, num_generations=6,
                       max_completion_length=200, per_device_train_batch_size=6, gradient_accumulation_steps=4,
                       max_steps=600, logging_steps=10, save_steps=100, report_to="tensorboard",
                       bf16=torch.cuda.is_bf16_supported(), fp16=not torch.cuda.is_bf16_supported())
    FastLanguageModel.for_training(model)
    g = GRPOTrainer(model=model, reward_funcs=[reward], args=gargs, train_dataset=Dataset.from_list(rows),
                    processing_class=tok)
    g.train()
    g.model.save_pretrained(gargs.output_dir + "/adapter"); tok.save_pretrained(gargs.output_dir + "/adapter")
