# AERIS — Unified Forward Plan (2026-07-12)

> ⚠ **SUPERSEDED (2026-07-13):** aage ka plan ab
> **`AERIS_NEXT_IMPLEMENTATIONS_BLUEPRINT.md`** hai — as-built map + P0–P9
> low-level designs + wireframes + eval gates. Is doc ke Sprint 1/3/4 ke items
> (Ladder+Ledger, World Model, Initiative, Reflexion, graduation, trust GUI)
> 2026-07-12 ke /loop session mein BAN CHUKE hain. Ye doc sirf history/context
> ke liye rakha hai.

Ek jagah sab kuch: har purane roadmap ka status, aage ka merged plan, aur nayi
extended functionalities — priority order mein. Ye ab **master index** hai; baaki
docs detail ke liye hain.

---

## 1. Status board — saare roadmaps ek nazar mein

| Roadmap | Status | Pending |
|---|---|---|
| **Laptop core** (`ROADMAP.md`, 12 checkpoints + v2 sprint) | ✅ largely done (intent engine, skills, GUI, presence, conversation layer, screen agent…) | 3 user-tasks: `python -m core.train_intent` chalana; Defender exclusion; **Qwen2.5-3B upgrade decision** (ab Year-plan Q3·M7 mein merge) |
| **Mirroring v2** (`MIRRORING_V2_ARCHITECTURE.md`) | ✅ Phases 0–7 implemented (2026-07-07) | sirf real-world tuning if needed |
| **AERIS Bridge** (phone↔laptop relay, E2E) | ✅ live (Phase 1, 2A, 2B) | — |
| **Mobile assistant** (`MOBILE_ASSISTANT_ROADMAP.md`, Phases 1–9 + HUD) | ✅ built: hotword (sherpa), 3-tier brain, phone skills, a11y, assist-role, continuous HUD, universal app launch, Gemini context | Phase 4 **UPI** (user-skipped, on demand); TTS ducking; dialogue-context on-device |
| **Mobile audit** (`AERIS_MOBILE_AUDIT_AND_MASTERPLAN.md`) | ✅ A1–A5, A7, A9–A11, A13–A14 fixed | **A6 personal wake model** (biggest lever, needs user recordings); on-device verify of wake fixes; release-build test |
| **Autonomous Year** (`AERIS_AUTONOMOUS_YEAR_PLAN.md`) | ✅ Q1·M1 Memory Fabric, Q1·M2 Goal System (tested, wired) | **M3 → M12** (ladder/ledger, world model, initiative, brain upgrade, web agent, sub-agents, learning) |

**Iska matlab:** foundation-layer sab bana hua hai. Aage ka kaam do dhaaron mein
bahta hai — **(A) mobile ko rock-solid + feature-rich karna**, **(B) laptop agent
ko autonomous banana** — aur beech mein **Track 1 bridge** jo dono ko ek mind
banata hai.

---

## 2. Aage ka plan — 6 sprints (merged spine)

Har sprint shippable; har item ka "source" bataya hai taaki purane roadmaps se
traceability rahe.

### Sprint 1 — Verify + Trust spine  *(reliability first)*
1. **On-device verify** — wake fixes (quiet/noisy room, 30s+ baat), sensitivity
   selector, error log, pair/unpair. *(audit)*
2. **A6 — personal wake**: user ki 5–6 "Aeris" recordings → exact-pronunciation
   spellings (proven offline workflow). Optional 2-stage verify. *(audit — biggest lever)*
3. **Q1·M3 — Autonomy Ladder + Ledger** (laptop): L0–L5 per action-class,
   append-only `data/ledger.jsonl` + "why", budgets, panic word. *(year plan — Q3
   autonomy isi pe rukti hai)*
4. USER: `train_intent` + Defender exclusion. *(old ROADMAP)*

### Sprint 2 — Track 1: ek mind, do body  *(the convergence sprint)*
5. **Memory-slice sync**: Memory Fabric ka relevant subset phone pe (E2E bridge)
   → standalone Gemini answers personal ho jayein ("mera naam", "Sara kaun").
6. **Goal sync**: phone pe bola goal → laptop ka resumable orchestrator pursue
   kare → jawab jis body pe user ho wahan aaye. *(year plan M2 ka cross-device rup)*
7. **Dialogue-context on phone**: pronoun follow-ups T1/T2 pe bhi (T3 pe already).
   *(mobile roadmap ka pending)*

### Sprint 3 — Perception  *(agent ko aankhein)*
8. **Q2·M4 World Model**: calendar + Gmail read-only + phone location/geofence +
   workspace snapshot → ek `Situation` object. *(year plan)*
9. **Phone notification reading**: NotificationListenerService → "notifications
   padho", important-notification events world model mein. *(new, mobile)*

### Sprint 4 — Initiative  *(the make-or-break)*
10. **Q2·M5 Initiative Engine**: salience-scored triggers, anti-nag budget,
    quiet hours; ladder-governed act/offer/drop. *(year plan)*
11. **Phone = presence surface**: initiative phone se bole (FCM push → TTS),
    kyunki phone hamesha saath hai. Morning/leave-now/follow-up briefs (M6).
12. **Goal resurface demo** — Q1 north-star ab poora: "Rahul follow-up" din baad
    sahi waqt pe khud surface ho.

### Sprint 5 — Depth  *(dimaag bada karo)*
13. **Q3·M7 brain upgrade**: Qwen2.5-3B/7B GGUF (old-ROADMAP decision resolve) +
    brain router (local↔Gemini↔optional Claude) + Reflexion critic.
14. **Q3·M8 web agent** (Playwright) + phone a11y multi-step flows.
15. **Q3·M9 sub-agents + background task queue.**

### Sprint 6 — Selfhood  *(Q4)*
16. Routine graduation (L3 auto), preference learning, "AERIS learns you" report.
17. Cross-device continuity ("continue where we left off").
18. **Q4·M12 eval harness + Agent Report Card** — nightly golden tasks.

---

## 3. Extended functionalities — naye features (prioritized)

Grounded additions jo existing stack pe fit hote hain. Har ek ka sprint-slot diya hai.

| # | Feature | Kya karega | Builds on | Slot |
|---|---|---|---|---|
| F1 | **Offline STT fallback** | Internet nahi to bhi commands samjhe — sherpa-onnx ASR (streaming zipformer, ~50MB) as fallback jab Google STT fail ho. *Voice-stack rule intact: primary Google en-IN hi rahega.* | sherpa already integrated | S2 |
| F2 | **Voice ID (speaker verify)** | Sirf TUMHARI awaaz pe wake confirm — 2-stage verify ka natural rup; dusron ki "Aeris" ignore. | sherpa speaker-id models; laptop pe `voice_id.py` already! | S1–S2 (A6 ke saath) |
| F3 | **Camera vision — "ye kya hai?"** | Camera frame → Gemini vision → jawab bol ke. "Is bill ka total kya hai", "ye plant kaunsa hai". | CloudBrain + camera | S3 |
| F4 | **Live translate mode** | "translate mode on" → sun-ke Hindi↔English bol de (STT→translate→TTS loop). | existing voice loop; laptop `translator.py` | S3 |
| F5 | **Caller announce + call actions** | Incoming call pe naam bole ("Rahul ka phone hai — uthaun?"); "reject karo" voice se. | phone state listener + contacts cache | S4 |
| F6 | **Notification triage** | F(9) listener ke upar: "important kya hai?" → Gemini summarize; spam mute suggestions. | S3 ka listener + T3 | S4 |
| F7 | **UPI payments (Phase 4)** | "Ravi ko 500 bhejo" → confirm → GPay prefilled (PIN user). Payee vault E2E. | deep links (design ready in mobile roadmap) | on-demand |
| F8 | **Expense hook** | Bola gaya kharcha ("aaj 250 ka khana") → aeris-expense app/Firebase mein entry. | existing expense apps + bridge | S5 |
| F9 | **Wake chime + TTS ducking** | Wake pe subtle chime; AERIS bolte waqt music duck. | audio focus APIs | S2 polish |
| F10 | **Personal LoRA** | Apne corpus pe local model ki personality fine-tune (Colab). | export_corpus + COLAB_TRAINING | S6 |

---

## 4. Operating rules (change nahi hote)

- **Reliability → continuity → depth** — naya feature tabhi jab pichhla stable.
- **Trust before autonomy** — koi autonomous capability apne ladder-class +
  ledger + undo ke bina ship nahi hoti.
- **Voice stack fixed** — Google en-IN STT + Neerja TTS primary; sherpa sirf
  wake/fallback.
- **Local-first privacy** — PII cloud pe sirf allowed classes mein.
- Har increment: tests green + demo + docs/memory update.

**Agla concrete kadam:** Sprint 1 — tum APK verify karo + "Aeris" recordings do
(A6), main parallel mein Q1·M3 Autonomy Ladder + Ledger banata hoon.
