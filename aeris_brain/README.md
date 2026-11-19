# aeris_brain — the on-device brain for AERIS mobile

Everything needed to build, train and evaluate the phone's own model (plan:
`docs/AERIS_MOBILE_BRAIN_PLAN.md`). The data, eval and export pipeline runs
here or in Colab. **Training runs only in Colab**, by you; nothing here
trains on this PC.

```
schema/tools.json      the 37 tools — single source of truth (prompt, data, eval, phone)
brain/
  contract.py          the 5-type output contract + validator (grounding, enums, one_of)
  prompt.py            the system prompt (compact tool signatures) — phone must match it
  grammar.py           JSON Schema of the contract → constrained decoding (vLLM / llama.cpp)
  expand.py            template grammar  (a|b)  [opt]  (x)?  {slot}  with span tracking
  slots.py             value pools (names, numbers, messages, times…), ~12% held out for test
  templates.py         ~630 English + Hinglish phrasing templates
  augment.py           STT-style noise, fillers, wake words — never touches slot text
  dialogs.py           ask / multi-turn / pronoun / multi-call / plan / escalate / small talk
  generate.py          → neutral JSONL train/dev/test (split by template AND slot value)
  convert/             Hinglish-TOP, MASSIVE, Mobile Actions, When2Call, xLAM, SmolTalk
  teacher.py           open-weight teacher jobs: paraphrase, Hinglish chat, judge (+ verifiers)
  quality.py           validate → decontaminate vs eval → dedupe → near-dedupe → cap
  mix.py               blend sources at set proportions (+ a mix report with sha256)
  render.py            neutral record → {prompt, completion} exactly as the phone prompts
  prefs.py             near-miss preference pairs for DPO
  evaluate.py score.py run a model over eval sets; decision/action/exact/arg-F1/per-tool
eval/
  build_seed.py        the hand-written release-gate set (seed_real.jsonl, 96 items)
  bakeoff_prompt.txt   a realistic ~685-token prompt for on-phone speed tests
notebooks/             Colab: 00 bake-off · 01 dataset · 02 SFT (+Optuna) · 03 DPO/GRPO · 04 export
  src/*.py             notebook sources (edit these, then `py -m scripts.py2nb`)
scripts/               py2nb (build .ipynb) · pack (zip the code for Colab)
tests/                 py -m pytest  (from this folder)
```

## The output contract

Every turn, the model emits exactly one JSON object:

| type | when | example |
|---|---|---|
| `tool_call` | do something (1+ calls) | `{"type":"tool_call","calls":[{"name":"set_alarm","args":{"time":"subah 6 baje"}}]}` |
| `ask` | a required detail is missing | `{"type":"ask","text":"Ravi ko kya bolna hai?","pending":"send_message"}` |
| `reply` | small talk / sure answers | `{"type":"reply","text":"Main badhiya hoon! Tum batao?"}` |
| `plan` | needs operating apps (phone agent) | `{"type":"plan","goal":"…","steps":["Open Gemini","…"]}` |
| `escalate` | facts, live info, long tasks, no tool | `{"type":"escalate","reason":"live_info","query":"aaj mausam kaisa hai"}` |

**String arguments are spans.** They're copied exactly as the user said them
("shaam 6 baje", "7300 978845"), and the app's existing parsers normalise
them. This keeps the small model's job easy and lets the human-labelled
public data convert exactly. The validator enforces it on all training data.

## Run it locally (no GPU)

```bash
cd aeris_brain
py -3.10 -m pytest -q                                   # 28 tests
py -3.10 -m eval.build_seed                              # rebuild the release-gate set
py -3.10 -m brain.generate --n 5000 --eval-n 500 --out out/try
py -3.10 -m brain.quality --in out/try/train.jsonl --eval eval/seed_real.jsonl --out out/try/clean.jsonl
py -3.10 -m brain.render out/try/clean.jsonl            # see a rendered prompt
py -3.10 -m scripts.pack                                 # → dist/aeris_brain_code.zip for Colab
```

## The Colab workflow

Brain v2 (chat + understanding + memory, unbiased data) is described in **docs/AERIS_BRAIN_V2.md**.


1. Run `py -m scripts.pack` and upload `dist/aeris_brain_code.zip` to `MyDrive/mobile aeris/` in Google Drive.
2. Optional: put `contacts.txt` / `apps.txt` (one per line) in
   `MyDrive/mobile aeris/private/`. These go into training data only.
3. Open the notebooks in order (File → Upload notebook in Colab):

| notebook | runtime | what |
|---|---|---|
| `00_bakeoff` | T4 | zero-shot accuracy of each candidate with our prompt + guided JSON |
| `01b_teacher_chat` | T4 (fresh session) | **brain v2**: Qwen3-8B teacher writes ~10k diverse Hinglish/English conversations + NLU labels + memory facts, all verifier-checked |
| `01_build_dataset` | CPU | templates + public sets + memory data + teacher chat → quality → intent-balanced NLU → 40k mix → **audit gate** → `final/` |
| `02_train_sft` | T4 / A100 | QLoRA SFT, Drive checkpoints, eval on every set, optional Optuna sweep |
| `03_preference` | T4 / A100 | DPO on near-miss pairs (+ optional GRPO with a verifiable reward), gated vs SFT |
| `04_export` | T4 | GGUF Q4/Q5/Q8 + post-quantisation gate with grammar-constrained decoding |

Every notebook writes to Drive and resumes after a disconnect.

## Phase 0 on the phone (speed + RAM)

Accuracy comes from notebook 00. Speed has to be measured on **your** phone
(RMX3741, Dimensity 7050, 12 GB):

1. **Gemma 4 E2B / E4B:** install *Google AI Edge Gallery*, download each
   model in the app, paste `eval/bakeoff_prompt.txt` and note the
   prefill and decode tokens/sec it reports.
2. **Qwen3 1.7B (GGUF):** install *PocketPal AI*, download
   `Qwen3-1.7B Q4_K_M`, paste the same prompt and note tokens/sec.
3. Keep the phone connected over USB while each model runs, and Claude can
   read its real memory use with `adb shell dumpsys meminfo <app package>`.

Pick by: exact-match from 00 → decode ≥ 10 tok/s and RAM ≤ 3 GB → smaller wins ties.

## Data sources and licences

| source | use | licence |
|---|---|---|
| our templates (`brain/templates.py`) | ~42% of the mix | ours |
| Hinglish-TOP (Google Research) | human Hinglish parses; **human test split = eval** | Apache-2.0 |
| MASSIVE en-US (Amazon) | intents + slots; test partition = eval | CC-BY-4.0 |
| Mobile Actions (Google) | phone function calls | CC-BY-4.0 |
| When2Call (NVIDIA) | when to ask / decline instead of calling | CC-BY-4.0 |
| xLAM 60k (Salesforce) | general function calling | **CC-BY-NC-4.0, personal use only** |
| SmolTalk everyday-conversations | small talk | Apache-2.0 |
| teacher outputs | paraphrases, Hinglish chat | from an **open-weight** model only, never Gemini/GPT (their terms forbid it) |

## Adding a tool

1. Add it to `schema/tools.json` (params, required, `implemented`).
2. Add English + Hinglish templates in `brain/templates.py` (aim for 6+ each,
   so the split can hold some out).
3. If a family member could be confused with it, add it to `FAMILIES` in
   `brain/generate.py`.
4. Run `py -m pytest`. It checks every tool appears in generated data and
   every enum value has training phrasings.
5. Add a few real-style lines to `eval/build_seed.py`.

## Growing the release gate

`eval/seed_real.jsonl` is the number that matters. It's built from real
speech, never generated. Add every real miss from the phone (the plan's
Phase 8 miss log) to `eval/build_seed.py` with its correct answer.
Don't train on it; the quality pipeline decontaminates against it.
