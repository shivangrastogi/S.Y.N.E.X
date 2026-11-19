# %% [markdown]
# # AERIS brain · 04 — export for the phone + post-quantisation gate
#
# 1. Merge the chosen adapter and export **GGUF** (Q4_K_M, Q5_K_M, Q8_0) for llama.cpp on the phone (plan §5).
# 2. Re-run the eval sets **on the quantised file**, with grammar-constrained decoding exactly as the phone will run it.
#    Gate: ≤ 1 point drop in exact-match against the full-precision eval (plan §7, S4).
# 3. Copy the winner to Drive → download to the PC → push to the phone.
#
# LiteRT-LM (`.litertlm`, GPU path via flutter_gemma) is the other runtime option for Gemma models. Its conversion is a separate step, handled in Phase 4 once the bake-off picks a runtime.

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
if not os.path.exists(CODE):
    subprocess.run(["unzip", "-q", f"{DRIVE}/aeris_brain_code.zip", "-d", "/content"], check=True)
os.chdir(CODE)
!pip -q install unsloth
RUN = f"{DRIVE}/runs/Qwen3-1.7B-dpo-v1"      # the adapter that passed its gate (SFT or DPO run folder)
cfg = json.load(open(f"{RUN}/run.json"))
TEMPLATE_KW = cfg["template_kw"]
EXPORT = f"{RUN}/export"
os.makedirs(EXPORT, exist_ok=True)

# %%
from unsloth import FastLanguageModel
model, tok = FastLanguageModel.from_pretrained(f"{RUN}/adapter", max_seq_length=2048, load_in_4bit=False)
for q in ("q4_k_m", "q5_k_m", "q8_0"):
    if not glob.glob(f"{EXPORT}/*{q.upper()}*.gguf") and not glob.glob(f"{EXPORT}/*{q}*.gguf"):
        model.save_pretrained_gguf(EXPORT, tok, quantization_method=q)
tok.save_pretrained(f"{EXPORT}/tokenizer")
!ls -la {EXPORT}

# %% [markdown]
# ## Gate: score the quantised files with grammar-constrained decoding

# %%
!CMAKE_ARGS="-DGGML_CUDA=on" pip -q install llama-cpp-python
from llama_cpp import Llama, LlamaGrammar
from brain.contract import load_tools, tools_for
from brain.grammar import contract_schema
from brain.render import offered_specs, end_marker
from brain.evaluate import prompts_for, score_preds

TOOLS = load_tools()
END = end_marker(tok, **TEMPLATE_KW)
full = json.load(open(f"{RUN}/eval.json"))

def read(path, limit=None):
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    return rows[:limit] if limit else rows

gate = {}
for gguf in sorted(glob.glob(f"{EXPORT}/*.gguf")):
    llm = Llama(model_path=gguf, n_ctx=4096, n_gpu_layers=-1, verbose=False)
    for path in sorted(glob.glob(f"{DRIVE}/data/final/eval/*.jsonl")):
        name = os.path.basename(path).replace(".jsonl", "")
        recs = read(path, 600)
        by_id = {r["id"]: r for r in recs}
        preds = []
        for rid, turn, prompt in prompts_for(recs, tok, TOOLS, **TEMPLATE_KW):
            r = by_id[rid]
            schema = contract_schema(offered_specs(r, tools_for(r, TOOLS)))
            g = LlamaGrammar.from_json_schema(json.dumps(schema), verbose=False)
            out = llm(prompt, max_tokens=256, temperature=0.0, grammar=g, stop=[END])
            preds.append({"id": rid, "turn": turn, "output": out["choices"][0]["text"]})
        rep = score_preds(recs, preds, TOOLS, title=f"{os.path.basename(gguf)} · {name}")
        rep.pop("errors")
        ref = (full.get(name) or {}).get("exact_pct")
        gate[(os.path.basename(gguf), name)] = (ref, rep["exact_pct"], rep["valid_pct"])
        print(f"{os.path.basename(gguf):40s} {name:22s} exact {ref} → {rep['exact_pct']}  valid {rep['valid_pct']}%")
    del llm

# %% [markdown]
# Pick the **smallest** file whose `seed_real` exact-match is within 1 point of full precision. Its `valid` should read 100% thanks to the grammar.
# Then download it from Drive (`runs/…/export/`) and copy it to the phone. Phase 4 adds the in-app loader and benchmark screen.
