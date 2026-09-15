# AERIS Mobile Assistant — "Google Assistant se zyada" Roadmap

**Goal:** aeris_remote ko laptop-remote se upgrade karke ek **standalone phone
assistant** banana jo:
1. App band ho tab bhi background mein efficiently chale
2. "Aeris" hotword se jaage, commands sunta rahe, "Aeris sleep" pe so jaye
3. Poora phone chala paye — apps kholna, calls/SMS/WhatsApp, settings, alarms
4. Net pe search karke answers de (LLM + live web)
5. Payments initiate kar paye (UPI) — voice se
6. Laptop on ho to purani bridge powers bhi rahe (hybrid brain)

Implementation: fresh Opus session, is doc ko context de kar, phase by phase.

---

## 0. Hard truths pehle (Android platform ki realities)

Ye jaan lena zaroori hai warna beech mein plan tootega:

| Chahiye | Android reality | Solution |
|---|---|---|
| Hamesha sunta rahe | Android background mic banned hai normal apps ke liye | **Foreground service** (`microphone` type) — persistent notification dikhega, ye avoid nahi ho sakta. Ya **default assistant app** banna (niche dekho). |
| "Aeris" hotword | Google STT continuously nahi chala sakte (battery + quota) | **Porcupine (Picovoice)** on-device wake-word engine — <1% CPU, custom "Aeris" keyword free console pe train hota hai. Hotword detect → tab Google STT start (voice stack untouched — sirf wake ke liye alag engine). |
| Payment "kar paye" | **UPI PIN kabhi automate nahi ho sakta** (NPCI/RBI + har payment app isse actively block karta hai). Screen-reading se GPay automate karna = account flag/ban risk. | `upi://pay?pa=...&am=...` **deep link** — AERIS bole "Ravi ko 500 bhej raha hoon", GPay/PhonePe prefilled khule, tum sirf PIN daalo. Ye legit, safe, aur practically wahi experience hai. |
| Poora phone control | Normal app dusre apps ko touch nahi kar sakti | **AccessibilityService** — ye superpower hai: kisi bhi app mein tap/scroll/type/read-screen. User ko Settings mein ek baar enable karna padta hai. Play Store pe daalna ho to justification chahiye; personal APK pe koi issue nahi. |
| Google Assistant jaisa integration | Sirf "default assistant app" ko power-button long-press + lockscreen access milta hai | Manifest mein `ACTION_ASSIST` + `VoiceInteractionService` declare karo → Settings > Default apps > Digital assistant mein AERIS chunna. **Ye karo — game changer hai.** |
| Battery na khaye | Doze mode services maar deta hai | Foreground service + user se **battery optimization exemption** (`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`) + Realme/Oppo (RMX3741 = Realme!) ka aggressive killer → autostart whitelist. ColorOS pe ye step skip kiya to service marti rahegi. |

**Flutter vs native:** UI Flutter mein rahega, lekin hotword service, accessibility,
assistant role, telephony — ye sab **Kotlin native** mein likhna padega, platform
channels se Flutter se juda hua. Ye is project ka sabse bada naya kaam hai.

---

## 1. Architecture

```
                    ┌─────────────────────────────────────┐
                    │  AERIS Phone App                     │
                    │                                      │
  "Aeris…" ──────▶ │  [Kotlin] WakeWordService (FG svc)   │
                    │     Porcupine on-device, always-on   │
                    │           │ hotword detect            │
                    │           ▼                           │
                    │  [Flutter] speech_to_text (en-IN)    │  ← voice stack same
                    │           │ transcript                │
                    │           ▼                           │
                    │  Intent Router (3-tier brain)        │
                    │   ├─ T1: on-device patterns (instant)│  torch, volume, call X,
                    │   │      Kotlin/Dart regex+skills    │  open app, alarm, UPI pay
                    │   ├─ T2: laptop AERIS via bridge     │  laptop on? → poora
                    │   │      (existing cloud_bridge)     │  Qwen brain + PC skills
                    │   └─ T3: cloud LLM + web search      │  laptop off → Gemini
                    │          (Gemini Flash, free tier)   │  Flash w/ grounding
                    │           │ reply                     │
                    │           ▼                           │
                    │  [Flutter] flutter_tts (Neerja)      │  ← voice stack same
                    │                                      │
                    │  [Kotlin] AerisAccessibilityService  │  screen actions
                    │  [Kotlin] AssistRole (power-button)  │
                    └─────────────────────────────────────┘
```

**3-tier brain kyun best hai:**
- T1 instant hai (torch on mein LLM ki zaroorat nahi), offline chalta hai
- T2 tumhara asli AERIS hai — laptop ke saare skills phone se (already built!)
- T3 Google-Assistant-killer hai: Gemini 2.x Flash free tier + Google Search
  grounding = live web answers, Hinglish samajhta hai, ~1s latency.
  (Option B: on-phone Qwen 0.5B via llama.cpp — private lekin slow + battery;
   Option C: apna serverless proxy — overkill. **Gemini Flash free tier = best.**)

---

## 2. Phases (har phase apne aap mein usable)

### Phase 1 — Always-on hotword + voice loop (foundation) ✅ BUILT 2026-07-11
Implementation note: Kotlin ki jagah **flutter_foreground_task + sherpa-onnx
keyword spotting** (Dart isolate FG service ke andar) — same result, kam native
code. (Porcupine plan hata: Picovoice free tier 2026-06-30 ko band, ab $6000+.
sherpa-onnx = Apache-2.0, no account, keyword plain text se — training hi nahi.)
- [x] `wake_service.dart`: FG mic service + sherpa-onnx KWS (zipformer 3.3M,
      assets/kws/, ~5MB); mic stream `record` package se; keywords.txt mein
      "AERIS" / "HEY AERIS" / "JARVIS" BPE tokens (boost :2.0)
- [x] Hotword → mic release → app launch → `speech_to_text` en-IN → transcript
- [x] Conversation mode (`chat_screen.dart`): reply bolne ke baad follow-up turn
      (10s listen / 4s pause); silence pe hotword re-armed. "Aeris sleep / so jao"
      (exact phrase) → service asleep; notification Sleep button se toggle
- [x] Boot auto-start (plugin ka autoRunOnBoot), battery-exempt + overlay +
      Realme autostart checklist → `assistant_settings.dart` (menu → Assistant)
- [x] Notification states: sun raha / Haan bolo / so raha + Sleep button
- [x] Mic-ownership contract: Porcupine idle owner; STT ke liye pause/resume
      (manual hold-to-talk bhi handoff karta hai); 30s watchdog + revive tick
- [ ] LIVE TEST pending: phone pe install → Assistant settings → switch ON →
      "Aeris" bol ke check; false-wake zyada ho to keywords.txt mein boost
      2.0→1.5 karo (kam pakde to 2.5, ya global keywordsThreshold ghatao)

### Phase 2 — On-device skills (T1) ✅ BUILT 2026-07-11
`lib/phone_skills.dart` — Tier-1 router, runs offline, no laptop. Wired into
`chat_screen.dart` `_send()` as the FIRST tier (before laptop/offline fallback).
- [x] App launch: "WhatsApp/YouTube/Instagram kholo" (25+ app map + Play Store
      fallback + settings/camera intents)
- [x] Comms: "Mummy ko call karo" (flutter_contacts → number → `ACTION_CALL`),
      "X ko SMS bhejo Y" (smsto: prefilled), "X ko WhatsApp pe bolo Y"
      (wa.me prefilled, +91 default). Messages open prefilled — user taps send.
- [x] Device: torch (torch_light), volume/mute (volume_controller),
      WiFi/BT/brightness/DND/location/aeroplane panels (Android 10+ blocks
      silent toggle → open panel for one tap)
- [x] Alarm ("subah 7 baje", saade/paune/sava parsing) + timer ("5 minute")
      via SET_ALARM / SET_TIMER SKIP_UI intents
- [x] Web search: "youtube pe X", "google karo X", "koi gaana chalao"
- [x] **one owner per phrase** + collision guard test (test/phone_skills_test
      .dart, 41 cases incl. 5 fall-through) — all green. Priority order matters
      (search before settings before openApp).
- [ ] LIVE TEST pending: install + say "torch on karo", "mummy ko call karo",
      "youtube kholo". First call/contacts use prompts CALL_PHONE/READ_CONTACTS.

### Phase 3 — Cloud brain + web answers (T3) ✅ BUILT 2026-07-11
`lib/cloud_brain.dart` — Gemini REST (generateContent), Hinglish spoken-first
system prompt, key/model/grounding in flutter_secure_storage.
- [x] Gemini integration (http package, v1beta REST, key from AI Studio free)
- [x] **Grounding reality (checked 2026-07-11): live Google Search is PAID on
      2.5 models** (free only on Gemini 3.x, 5k/month). So CloudBrain tries
      with `tools:[{google_search:{}}]` and, if the tier rejects it (400/403 +
      search/tool in msg), transparently retries WITHOUT grounding → still a
      smart knowledge answer. Grounding toggle + model field in settings.
- [x] Router: `_send()` = T1 phone skills → T2 laptop (if online) → T3 Gemini
      (laptop off) → "set up cloud brain" note if no key.
- [x] Settings: Gemini key (obscured) + model (default gemini-2.5-flash) +
      grounding switch + **Test button** (live round-trip check).
- [ ] LIVE TEST pending: paste AI Studio key → Test → ask "aaj ka mausam"
      with laptop off. Dialogue-context port (pronoun rewrites) = future.

---

## STATUS: Phases 1-3 all BUILT + on-device (2026-07-11, Opus). The 3-tier
brain is complete: hotword → phone skills → laptop → Gemini. Remaining:
Phase 4 UPI, Phase 5 accessibility, Phase 6 default-assistant role, Phase 7
hybrid polish. Live-test checklist: Picovoice n/a (using sherpa), Gemini key,
custom-voice keyword tuning.

### Phase 4 — UPI payments ~1-2 sessions
- [ ] Contacts/payees vault (E2E encrypted, secure storage): naam → UPI ID
- [ ] "Ravi ko 500 bhejo" → confirm speak-back ("Ravi Kumar, ravi@upi, ₹500 —
      bhejoon?") → "haan" → `upi://pay` deep link → GPay khulta hai prefilled →
      **PIN tum daalte ho** (ye by-design hai, bug nahi)
- [ ] Safety: amount cap (configurable, e.g. ₹5000), naya payee = extra confirm,
      har payment ka local log

### Phase 5 — Accessibility superpowers ✅ BUILT 2026-07-11
- [x] `AerisAccessibilityService.kt`: readScreen (top-to-bottom text),
      tapByText (climb to clickable), scroll fwd/back, global actions
      (back/home/recents/notifications/quick_settings). Channel aeris/a11y.
      a11y config XML + manifest service + strings.xml.
- [x] Skills (phone_skills.dart): "screen padho", "is page ko summarise karo"
      (screen text → Gemini — the laptop screen_agent's phone twin!), "back/
      home jao", "notification kholo", "scroll karo", "X pe tap karo".
      Guard: if service off → "enable screen control" message.
- [x] Media (`AudioManager.dispatchMediaKeyEvent`): "pause karo", "agla gaana",
      "pichla gaana", "music band karo" (media before search so control verbs
      win; "gaana chalao" stays a search).

### Phase 6 — Default assistant + polish ✅ BUILT 2026-07-11
- [x] `ACTION_ASSIST` intent-filter on MainActivity (lighter than the fragile
      VoiceInteractionService) → AERIS selectable under Settings → Default apps
      → Digital assistant. Power-button hold / assist gesture launches AERIS
      LISTENING. onCreate/onNewIntent set assistPending; aeris/assist channel
      `consume` (cold start) + `assist` invoke (warm) → `_startConversation()`.
      showWhenLocked+turnScreenOn so it works from lockscreen.
- [x] Settings tile → VOICE_INPUT_SETTINGS to pick AERIS as assistant.
- [ ] TTS ducking + "ruk jao" barge-in interrupt = future polish.

### Phase 7 — Hybrid magic (laptop + phone ek assistant) ✅ CORE BUILT
- [x] "Laptop pe chrome kholo" — regex `\b(laptop|pc|computer|desktop)\b`
      forces Tier-2 (bridge), so the phone-skill router never hijacks it.
- [x] File transfer + screen share already built (earlier phases) — voice
      hooks reuse the bridge.
- [ ] Cross-device shared context = future.

---

## 3. Naye permissions (manifest)
`FOREGROUND_SERVICE_MICROPHONE`, `RECEIVE_BOOT_COMPLETED`,
`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`, `CALL_PHONE`, `READ_CONTACTS`,
`SEND_SMS`, `BIND_ACCESSIBILITY_SERVICE` (service pe), assist intent-filters.

## 4. Naye dependencies
- `porcupine_flutter` (Picovoice) — wake word. Free tier: 1 custom keyword, kaafi hai.
- `google_generative_ai` ya plain REST — Gemini Flash
- `flutter_contacts`, `url_launcher`, `android_intent_plus`, `torch_light`
- Kotlin side: Porcupine Android SDK, AccessibilityService, VoiceInteractionService

## 5. Risks / gotchas
1. **ColorOS (Realme) service-killer** = #1 practical risk. Autostart whitelist +
   battery "Don't optimize" + notification lock, teeno karne padenge.
2. Porcupine "Aeris" accuracy Hinglish accent pe — console pe apni recordings se
   test karo; false-wake rate tune karna padega (sensitivity param).
3. speech_to_text continuous mode har ~30-60s restart hota hai — conversation
   window mein auto-restart loop chahiye (laptop wale STT loop jaisa).
4. Gemini free tier limits (~10-15 RPM) — personal use ke liye kaafi, lekin
   T1 ko maximally capable banao taaki LLM calls kam hon.
5. Accessibility + payments same app mein → Play Store reject karega. Personal
   sideload APK ke liye non-issue; kabhi publish karna ho to alag build flavor.
