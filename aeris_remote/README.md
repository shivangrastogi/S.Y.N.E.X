# AERIS (phone)

A voice assistant that runs on the phone: wake word, speech in and out,
phone actions, multi-step app tasks, and its own on-device AI model. It
works on its own; a paired laptop and a Gemini key add more.

- **Build & connect a laptop:** [SETUP.md](SETUP.md)
- **What it can do with a laptop:** [AERIS_COMPANION_GUIDE.md](AERIS_COMPANION_GUIDE.md)
- **The on-device brain (training + plan):** `../docs/AERIS_MOBILE_BRAIN_PLAN.md`
- **Roadmap:** `../docs/MOBILE_ASSISTANT_ROADMAP.md`

## How a command flows

```
wake word (sherpa-onnx) → speech-to-text → on-device brain (off / shadow / on)
   → phone skills (rules) → laptop (if paired) → Gemini (if a key is set)
```

## Code layout

| Folder | What's in it |
| --- | --- |
| `lib/main.dart` | App start, theme, pairing gate |
| `lib/home/` | Conversation screen, voice overlay, reactor animation |
| `lib/assistant/` | Phone skills (rules), phone agent (multi-app tasks), utterance stitching, Gemini client, app launcher, accessibility bridge |
| `lib/brain/` | On-device LLM: contract, prompt, grammar, llama.cpp runtime, executor, memory, Brain screen |
| `lib/settings/` | Settings pages |
| `lib/wake/` | Wake-word foreground service |
| `lib/laptop/` | Pairing, encrypted bridge, LAN/WebRTC screen mirroring, file transfer, continuity |
| `lib/ui/` | Theme (Aurora Pro) and shared widgets (sections, rows, save patterns) |
| `lib/core/` | Language mode, in-app error log |
| `assets/brain/tools.json` | The brain's 37 tools. Synced from `../aeris_brain` by `py -3.10 -m scripts.sync_app` — don't edit by hand |
| `assets/kws/` | Wake-word model |
| `assets/fonts/` | Sora + IBM Plex Mono (OFL) |

## Checks

```bash
flutter analyze
flutter test        # includes golden tests that pin the brain's prompt to the training pipeline
flutter build apk --release --target-platform android-arm64
```

The model file (`.gguf`) isn't in the app. Push it with
`adb push model.gguf /sdcard/Android/data/com.aeris.aeris_remote/files/models/`
or add it from Settings → On-device brain.
