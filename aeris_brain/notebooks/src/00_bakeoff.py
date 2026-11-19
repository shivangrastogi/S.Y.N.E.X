# %% [markdown]
# # AERIS brain · 00 — bake-off (zero-shot accuracy)
#
# Before any training: how good is each candidate **out of the box** with our exact prompt, on your real-style test sentences?
#
# Phase 0 on the phone (plan §4.1) already picked **Qwen3 1.7B Q4_K_M** as the base: Gemma 4 on the Mali GPU corrupted numbers.
# This notebook answers the remaining question: **is Qwen3 0.6B nearly as accurate?** It would be about 3× faster on the phone.
# It also checks the whole Colab setup (Drive → code zip → tests) works before the long dataset build.
#
# **Runtime:** Runtime → Change runtime type → **T4 GPU**. About 25 min.
#
# Uses only the `torch` / `transformers` that Colab ships with. Installing another inference engine mid-session swaps those libraries under the running notebook and breaks it (that happened in the first attempt).

# %%
from google.colab import drive
drive.mount("/content/drive")
import os, json, glob, subprocess
DRIVE_FOLDER = "/content/drive/MyDrive/mobile aeris"   # your Google Drive folder
DRIVE = "/content/aeris_drive"                          # space-free link to it (the ! shell commands need that)
if not os.path.exists(DRIVE):
    assert os.path.isdir(DRIVE_FOLDER), f"Folder not found: {DRIVE_FOLDER} - check the name in Google Drive"
    os.symlink(DRIVE_FOLDER, DRIVE)
CODE = "/content/aeris_brain"
assert os.path.exists(f"{DRIVE}/aeris_brain_code.zip"), "Upload aeris_brain_code.zip to MyDrive/mobile aeris/ first"
if not os.path.exists(CODE):
    subprocess.run(["unzip", "-q", f"{DRIVE}/aeris_brain_code.zip", "-d", "/content"], check=True)
os.chdir(CODE)
!pip -q install pytest
!python -m pytest -q
!python -m eval.build_seed
!python -m brain.generate --n 10 --eval-n 400 --out /content/bake

# %%
# Phase-0 winner first. Gemma is left out: ruled out on this phone (Mali GPU number bug).
CANDIDATES = {
    "qwen3-1.7b": ("Qwen/Qwen3-1.7B", {"enable_thinking": False}),
    "qwen3-0.6b": ("Qwen/Qwen3-0.6B", {"enable_thinking": False}),
}
EVAL_SETS = {"seed_real": "eval/seed_real.jsonl", "templated_test": "/content/bake/test.jsonl"}

# %% [markdown]
# ## Run the candidates
# Greedy decoding, no grammar. Invalid JSON counts against the model, which is fine for a zero-shot baseline. The phone app will enforce the grammar.

# %%
import gc, time, torch, transformers
from transformers import AutoTokenizer, AutoModelForCausalLM
from brain.contract import load_tools
from brain.evaluate import prompts_for, score_preds
print("torch", torch.__version__, "| transformers", transformers.__version__, "| GPU", torch.cuda.get_device_name(0))

TOOLS = load_tools()
read = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

def generate_all(model, tok, prompts, batch=16, max_new=200):
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    texts = []
    for k in range(0, len(prompts), batch):
        enc = tok(prompts[k:k + batch], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=tok.pad_token_id)
        texts += tok.batch_decode(out[:, enc.input_ids.shape[1]:], skip_special_tokens=True)
        print(f"  {min(k + batch, len(prompts))}/{len(prompts)}", end="\r")
    return texts

results = {}
for key, (repo, kw) in CANDIDATES.items():
    tok = AutoTokenizer.from_pretrained(repo)
    model = AutoModelForCausalLM.from_pretrained(repo, dtype=torch.float16, device_map="cuda")
    for name, path in EVAL_SETS.items():
        recs = read(path)
        jobs = prompts_for(recs, tok, TOOLS, **kw)
        t0 = time.time()
        texts = generate_all(model, tok, [p for _, _, p in jobs])
        preds = [{"id": i, "turn": t, "output": o} for (i, t, _), o in zip(jobs, texts)]
        rep = score_preds(recs, preds, TOOLS, title=f"{key} · {name}")
        with open(f"{DRIVE}/bakeoff_errors.{key}.{name}.jsonl", "w", encoding="utf-8") as f:
            for e in rep.pop("errors"):
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        results[(key, name)] = rep
        print(f"\n{key} · {name}: {len(jobs)} turns in {time.time() - t0:.0f}s")
        print(rep["markdown"])
    del model
    gc.collect(); torch.cuda.empty_cache()

# %% [markdown]
# ## Summary
# **decision** = right kind of answer (act / ask / reply / plan / escalate). **exact** = right tool AND every detail right.
# Zero-shot numbers are low; training fixes most of that. What matters here is the **gap** between 1.7B and 0.6B.

# %%
print(f"{'model':12s} {'set':15s} {'valid':>6s} {'decision':>9s} {'action':>7s} {'exact':>6s} {'argF1':>6s}")
for (k, n), r in results.items():
    print(f"{k:12s} {n:15s} {r['valid_pct']!s:>6} {r['decision_pct']!s:>9} "
          f"{r['action_pct']!s:>7} {r['exact_pct']!s:>6} {r['arg_f1']!s:>6}")
json.dump({f"{k}|{n}": r for (k, n), r in results.items()}, open(f"{DRIVE}/bakeoff_zero_shot.json", "w"), indent=2)
print("saved -> MyDrive/mobile aeris/bakeoff_zero_shot.json (+ bakeoff_errors.*.jsonl)")
