# %% [markdown]
# # AERIS brain · 01 — build the dataset (v2: the full brain)
#
# Builds `MyDrive/mobile aeris/data/final/` for **brain v2** — one model with three jobs
# (docs/AERIS_BRAIN_V2.md):
#
# * **TURN** — chat, commands, follow-up questions, memory-aware answers (the 5-type contract)
# * **NLU** — intent, act, slots, keywords, language, sentiment, emotion of any message
# * **MEMORY** — lasting facts worth remembering, in the user's own words
#
# Steps: template commands → public datasets → memory data → (teacher chat from notebook **01b**)
# → quality → intent-balanced NLU → **mix (40k, ~35 % conversation)** → **audit gate**.
#
# **Runtime: CPU is enough** (Runtime → Change runtime type → CPU), about 20-30 min.
# Every step writes to Drive and skips itself when its output exists — a disconnect costs nothing.
# Run **01b_teacher_chat first** (T4) — without it the mix has no conversation data and the
# audit gate fails on purpose.

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
!pip -q install pytest datasets
!python -m pytest -q   # the pipeline's own tests — must all pass

# %% [markdown]
# ### Optional: your own contacts / apps
# Put `contacts.txt` / `apps.txt` (one per line) in `MyDrive/mobile aeris/private/`. TRAIN split only.

# %%
os.makedirs("private", exist_ok=True)
for name in ("contacts.txt", "apps.txt"):
    src = f"{DRIVE}/private/{name}"
    if os.path.exists(src):
        subprocess.run(["cp", src, f"private/{name}"], check=True)
        print("using", src, "-", sum(1 for _ in open(src, encoding="utf-8")), "lines")

# %%
OUT = f"{DRIVE}/data"
VERSION = "v2.0"   # brain v2: balanced names pool, new tasks → rebuild derived files once
done = lambda p: os.path.exists(p) and os.path.getsize(p) > 0   # empty file = an earlier failed run
if not os.path.exists(f"{OUT}/.{VERSION}"):
    for p in glob.glob(f"{OUT}/templated/*.jsonl") + glob.glob(f"{OUT}/clean/*.jsonl") + glob.glob(f"{OUT}/v2/*.jsonl"):
        os.remove(p)
    os.makedirs(OUT, exist_ok=True)
    open(f"{OUT}/.{VERSION}", "w").write("1")

# %% [markdown]
# ## 1 · Template commands

# %%
if not done(f"{OUT}/templated/train.jsonl"):
    !python -m brain.generate --n 120000 --eval-n 6000 --out {OUT}/templated
print(json.load(open(f"{OUT}/templated/stats.json"))["train"]["families"])

# %% [markdown]
# ## 2 · Public datasets (human-labelled Hinglish/English commands + "when not to call a tool")

# %%
CONV = f"{OUT}/converted"
os.makedirs(CONV, exist_ok=True)
if not done(f"{CONV}/hinglish_top.train.jsonl"):
    !git clone --depth 1 https://github.com/google-research-datasets/Hinglish-TOP-Dataset /content/htop
    !python -m brain.convert.hinglish_top --dir "/content/htop/Dataset" --out {CONV} --max-synth 60000
if not done(f"{CONV}/massive.train.jsonl"):
    !python -m brain.convert.massive --tar https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz --out {CONV}
for which in ["mobile_actions", "when2call"]:
    if not done(f"{CONV}/{which}.train.jsonl"):
        !python -m brain.convert.hf_sets {which} --out {CONV}
!python -m eval.build_seed
!wc -l {CONV}/*.jsonl

# %% [markdown]
# ## 3 · Memory data (answers that use remembered facts, honest "you never told me", fact extraction)

# %%
V2 = f"{OUT}/v2"
if not done(f"{V2}/memory/turn_train.jsonl"):
    !python -m brain.memory_data --n 6000 --eval-n 400 --out {V2}/memory

# %% [markdown]
# ## 4 · Teacher chat (from notebook 01b) → split into its three kinds

# %%
TEACH = sorted(glob.glob(f"{OUT}/teacher/chat_grid_train_*.jsonl"))
print(len(TEACH), "teacher chunks")
assert TEACH, "Run notebook 01b_teacher_chat first — v2 needs conversation data"
!python -m brain.build_v2 split-teacher --out {V2}/teacher {" ".join(TEACH)}
TEST_T = sorted(glob.glob(f"{OUT}/teacher/chat_grid_test_*.jsonl"))
if TEST_T:
    !python -m brain.build_v2 split-teacher --out {V2}/teacher_test {" ".join(TEST_T)}

# %% [markdown]
# ## 5 · Quality — every source cleaned against **all** eval sets (nothing graded leaks into training)

# %%
EVALS = ["eval/seed_real.jsonl", f"{OUT}/templated/test.jsonl",
         f"{CONV}/hinglish_top.eval.jsonl", f"{CONV}/massive.eval.jsonl",
         f"{V2}/memory/turn_test.jsonl", f"{V2}/teacher_test/chat.jsonl"]
EVALS = [p for p in EVALS if os.path.exists(p)]
CLEAN = f"{OUT}/clean"
sources = {
    "template":       ([f"{OUT}/templated/train.jsonl"], "--cap-template 400"),
    "hinglish_top":   ([f"{CONV}/hinglish_top.train.jsonl"], ""),
    "massive":        ([f"{CONV}/massive.train.jsonl"], ""),
    "mobile_actions": ([f"{CONV}/mobile_actions.train.jsonl"], ""),
    "when2call":      ([f"{CONV}/when2call.train.jsonl"], ""),
    "chat":           ([f"{V2}/teacher/chat.jsonl"], "--near-dup"),
    "memory_turn":    ([f"{V2}/memory/turn_train.jsonl"], ""),
    "nlu_chat":       ([f"{V2}/teacher/nlu_chat.jsonl"], ""),
    "memory_extract": ([f"{V2}/memory/extract_train.jsonl", f"{V2}/teacher/memory_extract_chat.jsonl"], ""),
}
for name, (ins, extra) in sources.items():
    ins = [p for p in ins if os.path.exists(p)]
    if ins and not done(f"{CLEAN}/{name}.jsonl"):
        print(f"--- {name}")
        !python -m brain.quality --in {" ".join(ins)} --eval {" ".join(EVALS)} --out {CLEAN}/{name}.jsonl {extra}

# %% [markdown]
# ## 6 · NLU — intent-balanced (at most N per intent, so frequent commands can't drown rare ones)
# Commands get exact labels from their tool calls; chat turns carry the teacher's checked labels.

# %%
if not done(f"{CLEAN}/nlu.jsonl"):
    !python -m brain.build_v2 nlu --per-intent 260 --out {V2}/nlu_commands.jsonl {CLEAN}/template.jsonl {CLEAN}/hinglish_top.jsonl {CLEAN}/massive.jsonl
    !cat {V2}/nlu_commands.jsonl {CLEAN}/nlu_chat.jsonl > {CLEAN}/nlu.jsonl
!wc -l {CLEAN}/*.jsonl

# %% [markdown]
# ## 7 · Mix (40k for a free T4) + the audit gate
# The audit measures balance and variety (intents, English↔Hindi spread, name gender/region,
# distinct phrasing, duplicates, AERIS's male voice). If it FAILS, read the reasons — usually
# a source is too small (the mixer had to repeat it) → make more of it, don't train.

# %%
TOTAL = 40_000
!python -m brain.build_v2 mix --total {TOTAL} --clean {CLEAN} --out {OUT}/final/train.jsonl
!python -m brain.audit {OUT}/final/train.jsonl --gate

# %%
# Eval sets (never trained on) + dev
!mkdir -p {OUT}/final/eval
!cp {OUT}/templated/dev.jsonl {OUT}/final/dev.jsonl
!cp {" ".join(EVALS)} {OUT}/final/eval/
for kind in ("nlu_chat", "memory_extract_chat"):
    p = f"{V2}/teacher_test/{kind}.jsonl"
    if os.path.exists(p):
        !cp {p} {OUT}/final/eval/test_{kind}.jsonl
!cp {V2}/memory/extract_test.jsonl {OUT}/final/eval/test_memory_extract_tpl.jsonl
!ls -la {OUT}/final {OUT}/final/eval
print(json.dumps(json.load(open(f"{OUT}/final/train.jsonl.mix.json")), indent=1))
