# AERIS environment flags

**Generated — do not edit by hand.** Run `python gen_flags_doc.py`.

Discovered by scanning the source, so this cannot silently miss a flag; descriptions are hand-written in `core/flag_registry.py`, and `tests/test_flag_registry.py` fails if a flag is added without one.

## Split mode

| Flag | Default | Effect |
| --- | --- | --- |
| `AERIS_BRAIN_HIBERNATE_S` | 0 (off) | Retire the idle brain child after N seconds, carrying the conversation across the respawn (§6.22). ~478 MB → ~20 MB resting. |
| `AERIS_SPLIT_BRAIN` | off | Brain (torch + encoder + skills) runs in a supervised child process; the GUI imports no ML. Fixes the 0xC0000374 crash class. |
| `AERIS_SPLIT_VISION` | off | Camera + MediaPipe run in a child process; `get_gesture_engine()` returns a `RemoteGestureEngine` with the same surface (§6.30). |
| `AERIS_SPLIT_VOICE` | off | Mic + speaker run in a child process behind the same Qt signals `VoiceWorker` already consumes (§6.31). |

## Load

| Flag | Default | Effect |
| --- | --- | --- |
| `AERIS_BOOT_THROTTLE_MS` | tuned | Delay between staged boot chunks, so the first paint stays smooth. |
| `AERIS_CLASSIC_BOOT` | off | Skip the staged/instant boot path and build everything eagerly. |
| `AERIS_FORCE_ENCODER` | off | Always use the encoder, skipping the cheap router tiers. Debugging aid for routing comparisons. |
| `AERIS_IDLE_UNLOAD_S` | 300 | Drop model weights after N seconds idle (encoder, neural head, spaCy, local LLM). `0` never unloads. |
| `AERIS_LITE_ML` | off | Boot with no model weights; the tiered router pulls each in on the first utterance that needs it. |
| `AERIS_LLM_IDLE_UNLOAD_S` | AERIS_IDLE_UNLOAD_S, else 300 | Idle window for the local Qwen gguf alone — ~1 GB and the most expensive thing to reload, so you may want it held longer. |
| `AERIS_MATH_THREADS` | 1 | Overrides the BLAS/OMP thread pin (default 1, which avoids heap corruption when audio and encode threads run together). |
| `AERIS_PREWARM` | on (only acts with AERIS_LITE_ML) | After a lite boot, load the encoder, neural head, spaCy and chat gate on a background thread so the first heavy command doesn't stall. `0` keeps lite boot fully lazy. |

## Devices

| Flag | Default | Effect |
| --- | --- | --- |
| `AERIS_CAMERA_IDLE_S` | 0 (off) | Release the webcam after N seconds with no hand in frame. Trades a capability for resources: gestures stop until re-enabled. |
| `AERIS_DISABLE_BRIDGE` | off | Never start the phone bridge. The test suite sets this. |
| `AERIS_VOICE_STREAMING` | off | Live partial transcripts while you speak. **Off by default for a models reason**: `listen_streaming` is Vosk end-to-end, so the final never reaches Google en-IN (§6.29). |

## Behaviour

| Flag | Default | Effect |
| --- | --- | --- |
| `AERIS_AFFECT_OFF` | off (affect on) | Disable the Affective Core — no mood tracking, no proactive emotional check-ins. |
| `AERIS_ANTICIPATE_OFF` | off | Disable anticipation offers (habit-learned next-action nudges). |
| `AERIS_AUTONOMY_LEVEL` | per-class | Ceiling for the Autonomy Ladder, overriding per-class grants. |
| `AERIS_COGNITION_OFF` | off | Disable the higher cognition layer. |
| `AERIS_INTERPRET_OFF` | off | Disable the Interpreter strategy layer (chat vs command routing). |
| `AERIS_REASONING_CACHE_OFF` | off | Disable the reasoning cache on purely conversational turns. |
| `AERIS_REPAIR_MEMORY` | off | In-session self-correction: learn a failed phrasing from your rephrase and route it correctly from then on (§6.24). |
| `AERIS_SHOW_NODES` | off | Re-enable the telemetry stat-cards removed in §4.1. |

## Where each is read

- `AERIS_AFFECT_OFF` — core/affect.py:103
- `AERIS_ANTICIPATE_OFF` — core/anticipation.py:51
- `AERIS_AUTONOMY_LEVEL` — core/trust_ladder.py:67
- `AERIS_BOOT_THROTTLE_MS` — ui/jarvis_v31/main_window.py:169
- `AERIS_BRAIN_HIBERNATE_S` — core/brain_hibernator.py:51
- `AERIS_CAMERA_IDLE_S` — core/gesture_engine.py:76
- `AERIS_CLASSIC_BOOT` — run_gui.py:137
- `AERIS_COGNITION_OFF` — core/cognition.py:51
- `AERIS_DISABLE_BRIDGE` — core/cloud_bridge.py:74
- `AERIS_FORCE_ENCODER` — core/hw_encoder.py:79
- `AERIS_IDLE_UNLOAD_S` — core/brain.py:68, core/local_llm.py:62
- `AERIS_INTERPRET_OFF` — core/interpreter.py:60
- `AERIS_LITE_ML` — core/lite_ml.py:33
- `AERIS_LLM_IDLE_UNLOAD_S` — core/local_llm.py:62
- `AERIS_MATH_THREADS` — main.py:42, run_gui.py:78
- `AERIS_PREWARM` — core/lite_ml.py:46
- `AERIS_REASONING_CACHE_OFF` — core/reasoning_cache.py:57
- `AERIS_REPAIR_MEMORY` — core/main_engine.py:196
- `AERIS_SHOW_NODES` — ui/jarvis_v31/wiring_system.py:657
- `AERIS_SPLIT_BRAIN` — core/brain_backend.py:25, core/split_preflight.py:283, run_gui.py:162
- `AERIS_SPLIT_VISION` — core/remote_gesture_engine.py:38, core/split_preflight.py:120, core/split_preflight.py:122, core/split_preflight.py:156 (+1 more)
- `AERIS_SPLIT_VOICE` — core/remote_voice_engine.py:44, core/split_preflight.py:124, core/split_preflight.py:126, core/split_preflight.py:156 (+1 more)
- `AERIS_VOICE_STREAMING` — core/voice_service.py:75

## Internal / tooling

- `AERIS_GATE_DEBUG`
- `AERIS_LOG`
