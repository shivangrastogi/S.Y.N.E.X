# The on-device brain

AERIS understands a request in two ways:

1. **Rule router** (`lib/brain/router.dart`) is instant (microseconds) and deterministic.
   It's always asked first.
2. **Brain** (`lib/brain/llm/`) is a small LLM (Qwen3 1.7B, GGUF) running in llama.cpp
   on the phone. It's asked only when the router has nothing (its "search the web?"
   fallback), or when the brain just asked a question and this utterance is the answer.

Nothing leaves the phone. Training happens in `../aeris_brain/` (see
`aeris_brain/docs/AERIS_BRAIN_V2.md`).

## Files

| file | job |
|---|---|
| `lib/brain/llm/brain.dart` | `AerisBrain` covers several jobs. **Settings:** the mode (off / shadow / on) and the thread count. **Model:** finding the model file, then load / unload (unloads itself after 10 idle minutes). **Prompt cache:** a KV cache of the fixed prompt, saved to a file. **`decide()`:** prompt → JSON → validation. **Log:** `brain_log.jsonl`. |
| `lib/brain/llm/runtime.dart` | `BrainRuntime` is the interface to the model. `LlamaRuntime` is the real implementation (llamadart 0.10.0). Tests use `FakeBrainRuntime` (`test/fakes.dart`). |
| `lib/brain/llm/prompt.dart` | The system prompt and the Qwen3 chat format. **This file must stay byte-identical to `aeris_brain/brain/prompt.py`.** |
| `lib/brain/llm/contract.dart` | The brain's 5 answer types, plus the validation. Grounding (names and numbers must appear in what the user said) is checked here. |
| `lib/brain/llm/grammar.dart` | GBNF grammar: llama.cpp can *only* produce valid contract JSON. |
| `lib/brain/llm/bridge.dart` | Contract → `BrainAction` (`BrainRunsPlan` / `BrainSpeaks` / `BrainCannotDoYet`). This is a pure function. |
| `lib/brain/memory_search.dart` | Finds which remembered facts match a sentence. It's shared by the router, the bridge and the prompt. |
| `lib/features/settings/brain_screen.dart` | Settings → Brain: shows the status, the mode, a "Try it" box, the speed setting and recent decisions. |
| `assets/brain/tools.json` | The 37 tools the model is trained on. It's synced from `aeris_brain`. |

## A turn (lib/voice/session.dart)

```
utterance → router.route()
  ├─ the router knows it ────────────────→ _carryOut(plan)      (instant)
  └─ fallback, or the brain is awaiting an answer
       → brain.decide() → actionFromContract()
            ├─ BrainRunsPlan   → _carryOut(plan)  (same approvals as the router's plans)
            ├─ BrainSpeaks     → speak; if it asked a question, listen for the answer
            └─ invalid / BrainCannotDoYet → _carryOut(router's fallback)
```

Messages and web searches still need the user's "haan", whoever chose them.
"bye" always ends the conversation, whatever the brain says.

## Speed (Qwen3 1.7B Q4_K_M, RMX3741)

| | time |
|---|---|
| Model load (mmap) | about 2–4 s |
| First prompt ever | about 35 s, then the fixed prompt's KV cache is saved to `brain_cache/*.kv` |
| Every later turn | about 3 s until the first token, at roughly 5.5 tokens/s |

The time and the remembered facts come **after** the fixed prompt, so they never invalidate the cache.

## Installing a model

```
adb push Qwen3-1.7B-Q4_K_M.gguf /sdcard/Android/data/com.aeris.aeris_assistant/files/models/
```

Then go to Settings → Brain → **Re-scan**. The newest `*.gguf` file in that folder is used.
When your trained model is exported (notebook 04), push it the same way.

## Keeping the phone and the training in step

After you change `aeris_brain/brain/prompt.py`, `contract.py` or `schema/tools.json`, run:

```
cd ../aeris_brain && py -3.10 -m scripts.sync_app
cd ../aeris_assistant && flutter test test/brain_contract_test.dart
```

The test compares the Dart prompt with golden text rendered by the Python code and the real chat template.
