# AERIS Assistant (Android)

A voice-first personal assistant with a sci-fi HUD that's been decluttered. It's a new app, separate from `aeris_remote/` and `aeris_mobile/`.

- **Design rules:** [`docs/DESIGN.md`](docs/DESIGN.md). Read this before changing any screen. It explains why the Stitch export was rebuilt rather than copied.
- **Full plan:** [`docs/BUILD_GUIDE.md`](docs/BUILD_GUIDE.md)
- **Stitch prompts:** [`docs/STITCH_PROMPTS.md`](docs/STITCH_PROMPTS.md)

## Install on the phone

The on-device models (`assets/models/`, ~300 MB) are **not in git**. Rebuild them with `tool/model_export/README.md`, or copy them from a machine that has them.

```
flutter build apk --release --target-platform android-arm64   # ~340 MB
adb install -r build/app/outputs/flutter-apk/app-release.apk
```

Use the release build for daily use. Debug builds exaggerate animation jank (the aeris_remote lesson).

## What works in v0.1

| Area | Status |
|---|---|
| Boot ignition, 3-step onboarding (name, language, permissions) | ✅ |
| Home: reactor core, typed commands, suggestion chips, last action | ✅ |
| Voice: tap the core or mic → listening → thinking → speaking, keeps listening until "bas"/"bye" | ✅ |
| Reply lights up word by word as it's spoken (TTS progress events) | ✅ |
| Approval before anything leaves the phone (WhatsApp/SMS, web search): say "haan"/"nahi" or tap | ✅ |
| Follow-up questions ("alarm laga do" → "Kis time ka?") | ✅ |
| Skills: alarm, timer, torch, call (dialer), WhatsApp/SMS (prefilled), open ~40 apps, Google search, battery, time, date, maths, remember/recall | ✅ |
| Protocols: one phrase runs several actions, plus an editor | ✅ |
| Reminders ("kal 9 baje yaad dilana ki dawai leni hai", "10 minute baad batana"), rung by the Clock app as a labelled alarm/timer | ✅ 2026-11-17 |
| Alarm/timer cancel, "next alarm kab hai", relative alarms ("alarm for 5 minutes") | ✅ 2026-11-17 |
| Phone controls: silent/vibrate (needs Do Not Disturb access), volume, play/pause/next, "gaana bajao" / "play X on spotify", Wi-Fi/Bluetooth/data/location panels, directions ("ghar ka rasta dikhao") | ✅ 2026-11-17 (not yet tried on the phone) |
| "Which Rahul?": two equal contact matches → AERIS asks instead of guessing; family words (mummy ↔ Maa) and Hindi-script contacts match; any installed app opens by name | ✅ 2026-11-17 |
| Log with per-action detail (what you said, how it was parsed, latency) | ✅ |
| Memory: add/edit/delete/undo/search | ✅ |
| Settings: language (Hinglish / English IN / English US), speak replies, keep listening, speed, permissions, data, diagnostics | ✅ |
| **Own speech stack (default):** AERIS records the mic itself (no Google, no beep), Silero VAD finds the end of speech, a Hinglish Whisper model (Oriserve Swift, int8) transcribes on the phone, and `cleanTranscript` fixes known mishearings. 45/48 correct actions on the test set | ✅ |
| **JARVIS voice (default):** Supertonic 3 (MIT), male voice 9 at 1.35×, picked by ear from samples. Hinglish replies are spoken from Devanagari (`voice/hindi_speech.dart`: times like "saade chhe baje", Hindi numbers, dictionary + phonetic fallback), Roman stays on screen. Masculine Hindi verbs for male voices. Generated on the phone and sentence-pipelined | ✅ |
| Optional: Google recognizer, Microsoft neural voices (Neerja etc., edge v2 token), phone TTS, all switchable in Settings | ✅ |
| "Hey AERIS" always-on wake word | ⏳ Next: Kotlin FGS + openWakeWord (BUILD_GUIDE §7) |
| On-device LLM / cloud brain / agent | ⏳ Later milestones |

## Checks

```
flutter analyze
flutter test                                          # router corpus, parsers, session state machine
flutter test test/golden_test.dart                    # routing accuracy on test/data/golden_commands.tsv
AERIS_RENDER=1 flutter test test/render_screens_test.dart   # writes build/screens/*.png
```

**Golden commands:** `test/data/golden_commands.tsv` is one sentence per line plus the tool that must answer it. When the phone mishears or mis-routes something, add the sentence there with the tool it *should* reach, then fix the router until the test passes. It prints the score and every miss.

The render test is how the UI is reviewed without a phone. It renders boot, onboarding, home, listening, speaking, approval, log, memory, protocols and settings.

## Layout

```
lib/
  app/        boot gate, shell + nav, AppScope
  ui/         tokens, theme, kit (Panel, Brackets, HudButton, DecodeText…), reactor/
  brain/      parse.dart (time/duration/maths), router.dart (utterance → Plan),
              executor.dart (Plan → phone + reply), phone.dart (Android intents/plugins)
  voice/      io.dart (STT/TTS behind interfaces), session.dart (state machine)
  core/       models, store (shared_preferences, on-device only)
  features/   boot, onboarding, home, voice, log, memory, protocols, settings
```

## Build note (Windows)

`android/gradle.properties` sets `kotlin.incremental=false`. Kotlin's incremental cache crashes when the project (D:) and pub cache (C:) are on different drives.
