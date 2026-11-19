# %% [markdown]
# # AERIS brain · 01b — teacher chat (brain v2)
#
# Generates the **conversation** data the brain was missing (v1 had only ~3 % chat), plus
# understanding labels and memory facts, with an **open-weight teacher** (Qwen3-8B, Apache-2.0).
# Never Gemini/GPT outputs — their terms forbid training competing models (plan §6.5).
#
# Each conversation comes from a **diversity grid cell** — a persona used only once, a topic
# (40), a register (aap / tum / yaar / English), a code-mix level (English → mostly Hindi),
# a mood, a length and 1-4 turns — so the data can't collapse onto one style (brain/diversity.py).
# Every response is checked by strict verifiers before it's kept (brain/teacher.py):
# no Devanagari, no markdown/emoji, short spoken replies, **AERIS always male**
# ("raha hoon", never "rahi hoon"), labels from fixed sets, memory facts copied word-for-word.
#
# **Runtime: T4 GPU (free).** Run this in a **fresh** session — installing vLLM after other
# libraries are imported breaks Colab. Generation is chunked into Drive files; a disconnect costs
# at most one chunk — just run all again and it continues.
#
# Rough speed on a free T4: ~1,000-1,500 conversations/hour with vLLM (~300-500 with the
# transformers fallback). 12,000 cells ≈ 8-12 h with vLLM → run it over 2 sessions.

# %%
from google.colab import drive
drive.mount("/content/drive")
import os, json, glob, random, subprocess, time
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
OUT = f"{DRIVE}/data/teacher"
os.makedirs(OUT, exist_ok=True)

# %% [markdown]
# ## Config
# `N_CELLS`: total conversations to attempt (~75-85 % pass the verifiers).
# 12k cells → ~9-10k chats → TURN + ~22k NLU + ~9k MEMORY records — enough for the 40k mix.

# %%
TEACHER = "Qwen/Qwen3-8B-AWQ"        # 4-bit, fits a T4 (16 GB). Fallback below uses bitsandbytes.
N_CELLS = 12_000
CHUNK = 500
SEED = 2026
TEST_CELLS = 600                     # a held-out chat set the model is graded on (never trained on)

from brain.diversity import grid
from brain.teacher import chat_grid_jobs
cells = grid(random.Random(SEED), N_CELLS + TEST_CELLS)
print(cells[0])

# %%
# Engine: vLLM if it works on this GPU, else transformers (slower, always works).
ENGINE = None
try:
    !pip -q install vllm
    # vLLM 0.34 bug: its start-up warm-up imports a MiniMax-only kernel module for EVERY
    # model, and that module needs `cutlass` — missing on Colab, and the T4 can't use those
    # kernels anyway. The kernel_config switch below did not help (the import comes before
    # the check), so the installed file is patched: that one import becomes optional.
    import importlib.util, pathlib, re
    warmup_file = pathlib.Path(importlib.util.find_spec("vllm").origin).parent / "model_executor" / "warmup" / "kernel_warmup.py"
    warmup_src = warmup_file.read_text()
    minimax_import = re.compile(
        r"^(?P<indent>[ \t]*)from vllm\.model_executor\.warmup\.minimax_m3_msa_warmup import \(?\s*minimax_m3_msa_warmup,?\s*\)?", re.M)
    if "AERIS patch" not in warmup_src and minimax_import.search(warmup_src):
        def _optional_import(match):
            pad = match.group("indent")
            return (f"{pad}try:  # AERIS patch: MiniMax-only kernels need `cutlass`, absent on a T4 Colab\n"
                    f"{pad}    from vllm.model_executor.warmup.minimax_m3_msa_warmup import minimax_m3_msa_warmup\n"
                    f"{pad}except ImportError:\n"
                    f"{pad}    minimax_m3_msa_warmup = lambda *args, **kwargs: None")
        warmup_file.write_text(minimax_import.sub(_optional_import, warmup_src, count=1))
        print("patched vLLM warm-up:", warmup_file)
    from vllm import LLM, SamplingParams
    # vLLM 0.34 crashed on the T4 with "No module named 'cutlass'": its start-up warm-up
    # prepares CuTe-DSL kernels for an unrelated model (MiniMax) and imports `cutlass` for
    # every model. The T4 can't use those kernels anyway, so that warm-up is switched off
    # (enable_cutedsl_warmup=False). Installing the cutlass package did not fix it on Colab.
    engine_args = dict(model=TEACHER, dtype="half", max_model_len=3072, gpu_memory_utilization=0.90,
                       enforce_eager=True, seed=SEED)
    try:
        llm = LLM(**engine_args, kernel_config={"enable_cutedsl_warmup": False, "enable_jit_warmup": False})
    except TypeError:  # an older vLLM without kernel_config has no such warm-up either
        llm = LLM(**engine_args)
    tok = llm.get_tokenizer()
    params = SamplingParams(temperature=0.9, top_p=0.95, max_tokens=700, seed=SEED)
    ENGINE = "vllm"
except Exception as e:
    print("vLLM unavailable on this runtime → transformers fallback (works, ~3-4x slower):", repr(e)[:300])

if ENGINE is None:
    !pip -q install -U transformers accelerate bitsandbytes
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    BASE = "Qwen/Qwen3-8B"
    tok = AutoTokenizer.from_pretrained(BASE)
    tok.padding_side = "left"
    hf = AutoModelForCausalLM.from_pretrained(
        BASE, device_map="auto",
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16))
    ENGINE = "hf"
print("engine:", ENGINE)


def chat_prompt(text):
    msgs = [{"role": "user", "content": text}]
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)


def generate(prompts):
    texts = [chat_prompt(p) for p in prompts]
    if ENGINE == "vllm":
        return [o.outputs[0].text for o in llm.generate(texts, params)]
    outs = []
    for i in range(0, len(texts), 16):
        batch = tok(texts[i:i + 16], return_tensors="pt", padding=True).to(hf.device)
        with torch.no_grad():
            gen = hf.generate(**batch, max_new_tokens=700, do_sample=True, temperature=0.9, top_p=0.95)
        outs += tok.batch_decode(gen[:, batch["input_ids"].shape[1]:], skip_special_tokens=True)
    return outs

# %% [markdown]
# ## Generate (resumable)

# %%
def run_chunk(idx, part, split):
    path = f"{OUT}/chat_grid_{split}_{idx:04d}.jsonl"
    if os.path.exists(path):
        return 0, 0
    jobs = chat_grid_jobs(part, start_id=idx * CHUNK, split=split)
    t = time.time()
    outs = generate([j.prompt for j in jobs])
    kept, ok = [], 0
    for j, o in zip(jobs, outs):
        recs = j.accept(o)
        ok += bool(recs)
        kept += recs
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)   # only complete chunks ever appear
    print(f"{split} chunk {idx}: {ok}/{len(jobs)} conversations kept ({ok / len(jobs):.0%}) in {time.time() - t:.0f}s")
    return ok, len(jobs)

test_cells, train_cells = cells[:TEST_CELLS], cells[TEST_CELLS:]
run_chunk(0, test_cells, "test")
for i in range(0, len(train_cells), CHUNK):
    run_chunk(i // CHUNK, train_cells[i:i + CHUNK], "train")

# %% [markdown]
# ## Look at what was made
# Read a few — this is the moment to catch a bad pattern before training on it.

# %%
files = sorted(glob.glob(f"{OUT}/chat_grid_train_*.jsonl"))
rows = [json.loads(l) for p in files for l in open(p, encoding="utf-8")]
turns = [r for r in rows if not r.get("task")]
print(len(files), "chunks,", len(turns), "conversations,",
      sum(r.get("task") == "nlu" for r in rows), "NLU,", sum(r.get("task") == "memory" for r in rows), "MEMORY")
for r in random.Random(1).sample(turns, min(6, len(turns))):
    print("\n", r["meta"]["topic"], "|", r["meta"]["register"], "|", r["meta"]["mix"])
    for m in r["messages"]:
        c = m["content"]
        print(("  USER  " if m["role"] == "user" else "  AERIS ") + (c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)))
!python -m brain.audit {files[0]}
