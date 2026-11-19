# Incoming calls by voice

When the phone rings, AERIS says who is calling and listens. The only visual
is a glow around the screen edges, drawn over whatever app is open. The glow
lets touches through, so the phone's own Accept / Reject buttons still work.

```
ringing → "Ravi Sharma ka call aa raha hai. Uthaun ya kaatun?"   (ringtone turned down)
  "uthao" / "haan" / "pick up"   → answer            glow: mint flash
  "speaker pe uthao"             → answer on speaker
  "kaat do" / "nahi" / "baad mein" → decline         glow: red flash
      saved contact → "Ravi ko message bhejun ki baad mein baat karte hain?"
          "haan" → SMS sent directly (no screen)
  unclear twice                  → AERIS stops; the phone keeps ringing
  answered / declined by touch   → AERIS stops at once
```

Settings → Calls → **Answer calls by voice** turns it on and asks for the
permissions it needs.

## Obeying the phone (lib/calls/call_voice_rules.dart)

AERIS behaves exactly like the ringtone. On silent / vibrate the earbuds get no
ringtone either (checked on the phone), so AERIS doesn't speak there.

| phone | earbuds | AERIS |
|---|---|---|
| Do Not Disturb | any | quiet: no voice, no glow |
| silent / vibrate | any | quiet: the phone just vibrates |
| ringer on | yes | speaks **only in the earbuds**, never on the speaker |
| ringer on | no | speaks aloud (alarm channel) |

**Bluetooth earbuds have two links: music (A2DP) and call (SCO).** While a call rings,
the phone sends the ringtone over the call link and suspends the music link. Audio
sent to the music link then "plays" into nothing: Android reports it as played, but
the user hears silence (found in the phone's Bluetooth log). So ringing speech goes
to the earbuds' **call link** (`TYPE_BLUETOOTH_SCO`, `USAGE_VOICE_COMMUNICATION`).
Listening already uses the earbuds' mic over the same link.

When the voice should go to the earbuds only, `RingingVoicePlayer` (Kotlin) starts
the audio muted, checks where Android actually sent it, and unmutes only if it went
to the earbuds. Otherwise AERIS stays quiet. During ringing, some phones keep
Bluetooth earbuds on the call link and refuse app audio there.

## Pacing

1. **Let it ring.** The phone rings normally for ~4 s (about 2 rings) while the
   sentence is synthesised. Synthesising while playing over the ringtone is what
   made the voice stutter.
2. **Fade out.** The ringtone fades to its lowest step, never 0, and only when
   the phone is in ring mode. On Android, ring volume 0 is vibrate mode, and raising
   the volume switches a vibrating phone to ring mode: an earlier build flipped the
   user's phone between the two this way. AERIS restores the user's ringer mode if
   anything changed it. Only the system dialer can fully silence a ringing call.
3. **Speak and listen** into silence.
4. **Act on the answer.** After answering or declining, the ringtone volume comes back
   at once. If there was no clear answer, the ringtone fades back in and the phone
   keeps ringing.

Each step is logged under the logcat tags `AERIS_CALL`, `AERIS_VOICE` and `AerisCalls`.

## Files

| file | job |
|---|---|
| `lib/calls/call_assistant.dart` | `CallAssistant`, the flow above. It shares the voice session's ears and voice. |
| `lib/calls/call_commands.dart` | Turns what the user said into `CallChoice` (answer / answer on speaker / decline). This is a pure function. |
| `lib/calls/call_phrases.dart` | Every sentence AERIS says during a call. The fixed ones are pre-made in the voice cache. |
| `lib/calls/call_bridge.dart` | `CallBridge` is the interface to Android. `AndroidCallBridge` is the real implementation; `FakeCallBridge` (test/fakes.dart) is used in tests. |
| `lib/features/settings/call_settings.dart` | The Settings section: the switch, plus a `PermissionRow` for each requirement. |
| `android/.../AerisEngine.kt` | One Flutter engine per process, so Dart keeps running while the screen is closed. |
| `android/.../calls/CallWatchService.kt` | Foreground service (microphone type) and the `PHONE_STATE` receiver. It sends ringing / answered / ended events. |
| `android/.../calls/CallControl.kt` | Answer, reject, speakerphone, lowering the ringer, direct SMS. |
| `android/.../calls/EdgeGlowOverlay.kt` | The glow: a non-touchable overlay window with layered strokes, a rotating aurora gradient and a comet on each side. |
| `android/.../calls/CallBridge.kt` | The method channel `aeris/calls` and the event channel `aeris/calls/events`. |

## Android rules this design works around

- **The overlay window's alpha is 0.8.** Android 12+ only lets touches through another
  app's overlay when the overlay is at most 80% opaque.
- **The service must be started while the app is on screen.** Android 14+ forbids starting a
  microphone foreground service from the background. If the phone kills AERIS, the service
  comes back the next time the app is opened.
- **The number arrives late.** `PHONE_STATE` arrives twice per change: first without the
  number, then with it (only if READ_CALL_LOG is granted). The service waits 700 ms for the
  second broadcast.
- **Answer / reject use deprecated APIs.** They call `TelecomManager.acceptRingingCall()` /
  `endCall()`. Both are deprecated, but they are still the only route for an app that isn't
  the default dialer, and they need `ANSWER_PHONE_CALLS`.
- **The ringtone is turned down, not silenced.** Silencing it would need Do-Not-Disturb access.
- **Realme / Oppo (ColorOS) phones:**
  - Allow Autostart for AERIS, or the system may kill the service.
  - adb can't grant runtime permissions on these phones, so tests must tap Allow on the phone.

## Not yet verified on a phone

The flow is unit-tested (`test/call_assistant_test.dart`, `test/call_commands_test.dart`).
These still need checking with real calls:
- Whether the glow shows over the lock screen. Many phones hide app overlays on the keyguard;
  the voice flow works either way.
- Whether the ColorOS dialer honours `acceptRingingCall()`.
