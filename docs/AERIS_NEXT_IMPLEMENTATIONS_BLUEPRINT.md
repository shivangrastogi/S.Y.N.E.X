# AERIS — Next Implementations: Low-Level Design & Wireframe Blueprint
**v1 · 2026-07-13 · THE master forward doc** (supersedes `AERIS_UNIFIED_FORWARD_PLAN.md` §2;
detail-docs for history: `AERIS_AUTONOMOUS_YEAR_PLAN.md`, `AERIS_CONSCIOUSNESS_BLUEPRINT.md`,
`AERIS_MOBILE_AUDIT_AND_MASTERPLAN.md`, `MOBILE_ASSISTANT_ROADMAP.md`)

> Isme kya hai: (0) aaj ka AS-BUILT system map, (1) gap analysis, (2) curated
> priority queue P0–P9, (3) har phase ka **low-level design** — module specs,
> function signatures, data schemas, diagrams, test plan, eval gate, (4) UI
> **wireframes**, (5) dependency graph + sequencing, (6) risk register,
> (7) decision log. Sab kuch existing codebase pe grounded hai — koi
> hawa-hawaai module nahi.

---

## 0. AS-BUILT — aaj ka poora runtime (post loop-iter 21)

Pichhle roadmaps ke "pending" items ab REAL hain. Ye aaj ka actual data-flow hai
(har box ek existing, tested module):

```
                        ┌──────────────────────── LAPTOP (the MIND) ────────────────────────┐
                        │                                                                    │
  SENSORS               │   PERCEPTION                DECISION                ACTION         │
┌───────────┐           │  ┌──────────────┐        ┌───────────────┐      ┌─────────────┐   │
│ clock     │──────────▶│  │ world_model  │ situa- │ initiative_   │ tick │ initiative_ │   │
│ battery   │ power_    │  │ .Situation   │─tion──▶│ engine        │─────▶│ dispatch    │   │
│ presence  │ state,    │  │ battery/focus│        │ salience ×    │ ACT/ │ notify→speak│   │
│ journal   │ presence_ │  │ due/awaiting │        │ anti-nag ×    │OFFER │ resume_goal→│   │
└───────────┘ journal   │  └──────────────┘        │ quiet-hours   │      │ advance()   │   │
                        │         ▲                └───────┬───────┘      └──────┬──────┘   │
                        │         │                        │ every 15min         │          │
                        │         │                 __initiative__ heartbeat     ▼          │
  USER VOICE            │         │                 (main_engine scheduler)  ┌────────┐     │
┌───────────┐           │  ┌──────┴───────┐                                  │ agent_ │     │
│ Google    │  process_ │  │ memory_fabric│◀── recall_context (turn-1) ──────│ orches-│     │
│ en-IN STT │──text────▶│  │ semantic+KG+ │                                  │ trator │     │
│ (fixed)   │  pipeline │  │ user notes   │◀── "Lesson:" ◀── reflection ◀────│ ReAct+ │     │
└───────────┘  2a…2i    │  └──────────────┘    (Reflexion critic:            │ reflect│     │
                        │         ▲             in-loop nudge + post-run)    └───┬────┘     │
                        │         │                                              │          │
   LEARNING LOOPS       │  ┌──────┴────────────┐   GOVERNANCE (har tool call)    ▼          │
┌────────────────────┐  │  │ preference_learner│  ┌──────────────────────────────────────┐  │
│ presence → routine_│  │  │ memory_consolida- │  │ autonomy.TrustGate  L0–L5 + HARD_CAP  │  │
│ learner → offers → │  │  │ tion (nightly)    │  │ → allow / confirm(park) / deny        │  │
│ graduation → sync →│  │  └───────────────────┘  │ → Ledger (append-only, "why")         │  │
│ AutomationEngine   │  │                         └──────────────────────────────────────┘  │
│ (cron pe FIRE)     │  │   goal_system: captured→acting→blocked(need_user/time/tool)→done  │
└────────────────────┘  │                                                                   │
                        │   OBSERVABILITY+CONTROL: health_server /mind (self, initiatives,  │
                        │   learned routines, TRUST grants ▲▼ + PANIC, audit "kya kiya kyun")│
                        └───────────────────────────────┬───────────────────────────────────┘
                                                        │  cloud_bridge (Firebase relay,
                                                        │  E2E AES-GCM, zero-config QR)
                        ┌───────────────────────────────┴───────────────────────────────────┐
                        │                      PHONE (the BODY) — aeris_remote              │
                        │  wake_service (sherpa-onnx 2-stage + [WAKE] diagnostics)          │
                        │  chat_screen (persistent conv, "bye" ender) · assistant_overlay   │
                        │  (compact blur-sheet / cinematic HUD) · phone_skills (Tier-1)     │
                        │  cloud_brain (Gemini T3) · a11y bridge · assist-role · FCM        │
                        └───────────────────────────────────────────────────────────────────┘
```

**As-built inventory (sab tested, sab wired):**

| Layer | Modules | Tests |
|---|---|---|
| Memory | `memory_fabric` `memory_consolidation` `preference_learner` | ✅ |
| Goals | `goal_system` (park/resume/confirm-cycle) | ✅ |
| Governance | `autonomy` (Gate+Ledger+panic+quiet) `trust_view` (+controls POST) | ✅ |
| Agent | `agent_orchestrator` (ReAct+governance+Reflexion) `reflection` | ✅ |
| Proactivity | `world_model` `initiative_engine` `initiative_dispatch` + 15-min heartbeat | ✅ |
| Learning | `routine_learner` `routine_offers` `routine_graduation` `graduated_routines` `routine_voice` | ✅ |
| Self | `self_model` `health_server /mind` dashboard | ✅ |
| Mobile | wake (sherpa 2-stage), overlay (compact/cinematic), skills, a11y, bridge | ✅ built, ⚠ wake live-verify pending |

---

## 1. Gap analysis — kya bacha hai

```
  VISION: "self-thinking, action-taking, learn-by-self/things/surroundings, do body ek mind"

  DONE ✅                                    GAP ✗
  ─────────────────────────────             ──────────────────────────────────────────
  learn-by-self  (Reflexion)                ✗ P0 wake word phone pe reliably nahi sun raha
  learn-by-things (routines/prefs)          ✗ P1 overlay har app ke upar nahi aata (Option B)
  learn-by-surroundings (battery/           ✗ P2 do body, do mind — continuity nahi hai
    focus/time — LOCAL only)                ✗ P3 surroundings = sirf laptop-local; calendar/
  self-thinking (initiative+goals)              notifications/location andha hai
  action-taking (dispatch+automation)       ✗ P4 initiative ki openness fixed hai — seekhti nahi
  governance (ladder+ledger+GUI)            ✗ P5 autonomy badhane ka EVAL GATE nahi hai
  observability (/mind)                     ✗ P6 native Trust tab desktop GUI mein nahi
                                            ✗ P7 sub-agents / background queue nahi
                                            ✗ P8 web-hands (Playwright) nahi
                                            ✗ P9 personality (LoRA) + extended features
```

---

## 2. Curated priority queue

| P | Naam | Kyun is order mein | Depends on | Size |
|---|---|---|---|---|
| **P0** | Wake reliability + A6 personal wake | Sab kuch iske peeche hai — jo assistant sunta nahi wo assistant nahi | user ke `[WAKE]` logs | S |
| **P1** | Overlay Option B (system overlay) | Wake ke baad pehla UX moment; "har jagah Jarvis" feel | P0; user "haan karo B" | M |
| **P2** | Continuity — ek mind, do body | Convergence sprint; sab aage ke features iske upar | bridge (done) | L |
| **P3** | Perception widening (phone-as-sensor: notifications, calendar, location) | Initiative tabhi smart jab world dikhe; **phone se, OAuth ke bina** | P2 envelope | L |
| **P4** | Openness learning (initiative feedback) | Anti-nag ko data-driven banao — warna P3 ke naye triggers spam banenge | P3 se pehle bhi ho sakta | S |
| **P5** | Eval harness + Agent Report Card | Trust-before-autonomy ka objective gate; L3→L4 isi se unlock | — | M |
| **P6** | Trust tab (desktop GUI native) | /mind browser mein hai; GUI mein laao — controls wahin jahan user rehta hai | trust_view (done) | S |
| **P7** | Sub-agents + task queue | Parallel background kaam; M9 | P5 gate | L |
| **P8** | Web agent (Playwright) | Real-world hands; M8 | P5, P7 queue | L |
| **P9** | Personality: LoRA + voice ID + extended F1–F10 | Selfhood quarter | corpus export | L |

**+ parallel tracks** (P-queue ke saath interleave, §4 lanes dekho):
- **§3-L Laptop companion:** L1 mini-HUD · L2 laptop hotword · L3 screen
  companion v2 · L4 phone-notif toasts · L5 palette v2 · L6 window skills
- **§3-S Security:** S1 ledger hash-chain · S2 key rotation/revoke · S3
  at-rest coverage · S4 phone panic · S5 privacy page
- **§3-V Conversation polish:** V1 barge-in · V2 chime+ducking · V3 phone
  dialogue-context · V4 quiet-voice profile
- **§3-I Knowledge:** I1 docs-RAG→fabric · I2 temporal recall · I3 KG
  enrichment (confirm-gated) · I4 file-finder
- **§3-E App ecosystem hub:** expense · AppliTrack · Momentum · Vault adapters

---

## 3. Low-level designs

### P0 — Wake reliability (in-flight) + A6 personal wake

**State:** diagnostics shipped (2026-07-12): `[WAKE] hb` heartbeat (2s), raw-HIT
logs (stage-2 se pehle), stage-2 reject metrics, refractory logs. User ke
console logs ka wait hai.

**Decision tree (logs aane pe):**
```
[WAKE] hb aa raha hai?
├─ NAHI → service isolate mar gaya / mic stream dead
│         → onRepeatEvent watchdog check; recorder re-init path
└─ HAAN → bolte waqt rms kya hai?
    ├─ rms < 0.01 (heartbeat mein bhi)     → HW noise-suppression speech kha raha
    │   FIX: RecordConfig(noiseSuppress: false, echoCancel: false) — sherpa ka
    │        apna normalization hai; sirf autoGain rakho. (1-line, rebuild)
    ├─ rms healthy, HIT kabhi nahi         → threshold/spelling gap
    │   FIX 1: sensitivity 'high' (0.12) default karo
    │   FIX 2: A6 — user ki 5–6 recordings se exact-pronunciation BPE spellings
    │        (proven offline workflow: record → force-align → spelling variants
    │        keywords.txt mein, boost config se — NEVER inline `:2.0`)
    ├─ HIT plausible=false                 → stage-2 zyada strict is device pe
    │   FIX: voiced≥0.2→0.15; max≥median*2.0→*1.6 (metrics se exact number)
    └─ HIT plausible=true, WAKE FIRED nahi → refractory/downstream; logs batayenge
```

**A6 pipeline (user recordings mile to):**
```
recordings/*.wav → tools/wake_tune.py::extract_spellings()
  → sherpa streaming ASR se token-align → top-3 BPE variants
  → assets/kws/keywords.txt update (@AERIS)
  → offline validate: tools/wake_validate.py (5/5 hit, hiss reject)
  → device pe sensitivity presets re-verify
```
**Eval gate:** 10/10 wake in quiet room @1m, 8/10 @3m, 0 false-wake in 30-min
fan-noise soak. **Test:** offline validator + on-device soak checklist.

---

### P1 — Overlay Option B: system overlay (har app ke upar)

**Problem:** abhi wake pe `launchApp()` poora app foreground laata hai — ColorOS
pe background-launch restrictions + jarring UX. Option B = chhota system-overlay
bubble jo **kisi bhi app ke upar** float kare, Google-Assistant jaisa.

**Package:** `flutter_overlay_window` (SYSTEM_ALERT_WINDOW). ColorOS needs:
"Display over other apps" + "Display pop-up windows while running in background"
(dono settings-checklist mein already hain).

**Architecture:**
```
 wake_service (FG isolate)                    overlay isolate (NEW)
 ┌─────────────────────┐   showOverlay()      ┌──────────────────────────┐
 │ hotword fired        │────────────────────▶│ @pragma('vm:entry-point')│
 │ (mic released)       │  FlutterOverlay-    │ overlayMain()            │
 │                      │  Window.showOverlay │  OverlayHud widget       │
 └─────────┬───────────┘                      │  states: listening →     │
           │ shareData({state, partial,       │  thinking → speaking →   │
           │  reply, amp})  (both ways)       │  idle-collapse           │
           ▼                                  └───────────┬──────────────┘
 chat pipeline main isolate                               │ tap "expand"
 (STT → brain → TTS) — UNCHANGED;                         ▼
 overlay sirf ek VIEW hai                     full app (existing compact
                                              sheet ChatScreen continue)
```
**Files:**
- `lib/overlay_main.dart` — entry point + `OverlayHud` (reuses `reactor_painter.dart` — 56dp bubble, expand pe 320dp sheet-lite: last 2 bubbles + live partial)
- `lib/overlay_channel.dart` — `OverlayBus.push(OverlayState)` / `onCommand` (shareData wrapper, JSON: `{s:"listen|think|speak|idle", txt, amp}`)
- `wake_controller.dart` — wake pe: overlay-perm hai → `showOverlay(height:120, alignment:bottomCenter, flag:focusPointer)`; nahi → fallback current `launchApp`
- `chat_screen.dart` — conversation events ko `OverlayBus` pe mirror karo (5 lines)

**Rules:** mic-ownership contract untouched (overlay kabhi mic nahi leta) ·
"bye"/timeout → overlay collapse→dismiss · cinematic sirf assist-role/app ke
andar (overlay hamesha compact) · overlay isolate mein NO heavy init (sirf UI).

**Wireframe:**
```
  koi bhi app (YouTube etc.)              expand pe:
 ┌─────────────────────────┐   ┌─────────────────────────┐
 │  ...user ka content...  │   │  ...content (dimmed)...  │
 │                         │   │ ┌─────────────────────┐ │
 │                         │   │ │ ◉ tum: "kal ka       │ │
 │                         │   │ │   weather?"          │ │
 │        ┌─────────┐      │   │ │ ◉ AERIS: "Kal Delhi  │ │
 │        │  ◉ ~~~  │◀──── │   │ │   mein 34°C..."      │ │
 │        │ reactor │ 56dp │   │ │ [live partial....]   │ │
 │        └─────────┘      │   │ └─────────────────────┘ │
 │   listening pulse ring  │   │      ◉ reactor row      │
 └─────────────────────────┘   └─────────────────────────┘
```
**Tests:** overlay state-machine unit (bus JSON round-trip) + on-device: wake
from home/YouTube/lock(AOD skip), expand→app continuity, "bye" collapse.
**Gate:** wake→overlay-visible < 800ms; zero mic conflicts 20 conversations.

---

### P2 — Continuity: ek mind, do body

**Goal:** phone pe bolo "Rahul ko follow up yaad dilana" → laptop ka goal
system pursue kare → jawab **us body pe aaye jahan tum ho**. Personal facts
phone ke standalone (Gemini) jawabon mein bhi hon.

**Design principle:** laptop = mind (fabric, goals, agent). Phone = body
(sensors + voice + presence). Bridge (E2E AES-GCM) = spinal cord. **Naya
transport nahi banega** — existing `core/cloud_bridge.py` + Firebase relay ke
upar ek typed envelope layer.

**Envelope schema (`core/continuity.py`):**
```jsonc
{
  "v": 1,
  "kind": "goal.capture | goal.update | mem.slice | presence.beat |
           reply.route | notif.event | cal.slice | loc.event",
  "id": "c_9f3a…",            // dedupe
  "origin": "phone | laptop",
  "ts": 1784145600.0,
  "ttl_s": 3600,               // stale envelopes drop ho jaate hain
  "payload": { … }             // kind-specific, neeche
}
```
**Module: `core/continuity.py`** (pure, injectable — bridge fake karke test):
```python
class DeviceRegistry:            # presence arbitration
    def beat(device, state)      # "active" | "idle" | "away" (+ts)
    def active_device() -> str   # sabse recent active; tie → phone
class ContinuityRouter:
    def outbound(kind, payload) -> Envelope         # sign+wrap
    def inbound(env) -> None                        # dispatch table:
      # goal.capture  → goal_system.capture(text, source="phone")
      # presence.beat → registry.beat(...)
      # reply.route   → speak on THIS body if registry says so
    def route_reply(text) -> "phone" | "laptop"     # active_device()
def memory_slice(fabric, k=40) -> dict              # profile facts + top prefs
```
**Memory-slice sync (privacy-tiered):** sirf `fact` + `preference` kinds (KG
triples jaise "Sara is my sister"), **kabhi** episodic chat nahi. Nightly
consolidation ke baad + on-demand. Phone: `flutter_secure_storage` mein;
`cloud_brain.dart` Gemini prompt mein "Relevant memory:" block inject kare
(laptop ke `recall_context` ka mirror).

**Goal sync flow:**
```
 PHONE: "Rahul follow-up yaad dilana"
   └▶ looks_like_goal? (Dart port of _CAPTURE_RE — same regex)
        └▶ envelope goal.capture ──E2E──▶ LAPTOP goal_system.capture()
             heartbeat/due pe agent kaam kare … blocked(need_user)?
             └▶ reply.route envelope ──▶ registry.active_device()
                  ├─ phone active  → FCM push → phone TTS bole
                  └─ laptop active → laptop _speak()
```
**Presence beats:** phone FG service har 60s + screen-on events; laptop
presence_journal state-changes. Registry dono side sync (envelope) — split-brain
se bachne ke liye laptop authoritative, phone cache.

**Tests:** envelope round-trip + TTL-drop + dedupe; fake-bridge se goal.capture
→ real GoalStore; route_reply arbitration (phone-active / laptop-active /
both-idle→phone). Integration: mock relay pe end-to-end goal capture→park→
confirm-from-phone. **Gate:** phone-spoken goal laptop /mind pe < 5s; reply
correct body pe 10/10.

---

### P3 — Perception widening: phone-as-sensor (no-OAuth design)

**Insight:** Calendar/Gmail ke liye laptop OAuth bharari hai; **phone ke paas ye
sab pehle se hai** — notifications (NotificationListenerService), calendar
(CalendarContract provider), location (geofence). Phone = sensor body, envelopes
se mind ko feed karo. Zero cloud credentials, zero OAuth. **Privacy: local-only
classes; content E2E ke bahar kabhi nahi.**

```
 PHONE sensors                                LAPTOP world_model
 ┌────────────────────────┐                  ┌─────────────────────────┐
 │ NotificationListener   │ notif.event      │ Situation +=            │
 │  (whitelist: whatsapp, │─────────────────▶│  notifications: deque   │
 │   sms, gmail, calls)   │  {app, sender,   │  next_event: {...}      │
 │ CalendarContract query │   title, prio}   │  location: home|office| │
 │  (next 24h events)     │ cal.slice        │            unknown      │
 │ Geofence (home/office) │ loc.event        │ → initiative candidates │
 └────────────────────────┘                  └─────────────────────────┘
```
**Phone (`lib/sensor_feed.dart` + `NotifListenerService.kt`):** whitelist-only
apps; sender+title bhejo, **body optional-off by default**; priority heuristic
(known contact > OTP > promo-drop). Calendar: `next_24h()` every 30min +
on-change. Battery-frugal: batch envelopes, piggyback on FCM keepalive.

**Laptop (`core/world_model.py` extend):**
```python
@dataclass Situation:  # naya
    notifications: list  # [{app, sender, prio, ts}] last 30min
    next_event: dict     # {title, at, mins_away} | None
    location: str        # "home" | "office" | "unknown"
```
`situation_initiatives()` naye candidates (sab anti-nag ke andar):
- `notif_important` — "Rahul ka WhatsApp aaya — padhun?" (prio≥high, L2 offer)
- `leave_now` — next_event.mins_away ≤ travel-estimate → "nikalna hai" (L2)
- `morning_brief` — pehla phone-active beat subah → aaj ke events + pending
  goals ka ek-line brief (L1 suggest; graduated ho to L3)

**Tests:** fake envelopes → Situation fields; initiative candidates ke guards
(whitelist, prio, dedupe source_id `notif:{hash}`); leave_now maths. **Gate:**
0 spam complaints ek hafta soak; morning brief 7/7 din sahi.

---

### P4 — Openness learning (initiative feedback loop)

**Problem:** `Initiative.openness` hardcoded hai. "User is kind pe act karta
hai ya ignore?" — ye seekhna hi anti-nag ko intelligent banata hai.

**Module: `core/openness.py`:**
```python
class OpennessStore:                      # data/openness.json, atomic
    def record(kind, outcome)             # acted | dismissed | ignored
    def openness(kind) -> float           # EMA: acted=1.0, dismissed=0.0,
                                          #   ignored=0.25; α=0.2; start 0.6
    def stats() -> dict                   # /mind ke liye
```
**Wiring:** dispatch surface hone pe `pending_feedback[kind]=ts` register;
agla user-utterance ≤90s mein us initiative se related (kind-keyword match) →
`acted`; explicit "rehne do/mat bolo" → `dismissed`; 90s silence → `ignored`
(idle-tick pe settle). `initiative_engine` candidates banate waqt
`openness=store.openness(kind)` inject kare. Floor 0.15 (kabhi poora mute
nahi — critical battery jaise kinds ke liye min-importance override).
**Tests:** EMA maths, outcome classification windows, floor, engine injection.
**Gate:** 2-hafta soak mein ignored-rate ↓ trend dikhe /mind stats mein.

---

### P5 — Eval harness + Agent Report Card

**Kyun:** "trust before autonomy" ko objective banao. L3→L4 (act-on-goal) tabhi
jab report card pass. Ye hi Q3 ke sub-agents/web-agent ka gate hai.

**Golden tasks (`tests/golden/*.yaml`):**
```yaml
id: g_msg_confirm_cycle
goal: "Rahul ko message bhejo ki kal milte hain"
world: {contacts: [Rahul], time: "14:00"}
expect:
  parks: need_user           # message class = L2 → confirm
  after_confirm: {tool: send_message, args_contains: {to: rahul}}
  ledger: [{decision: confirm}, {decision: allow}]
  max_steps: 4
```
**Module: `core/eval_harness.py`:** mock-executor pe har task chalao (scripted
LLM **nahi** — real local LLM, mocked tools; wahi mock-executor testing rule),
per-task pass/fail + steps + latency + ledger-conformance → `data/report_card/
YYYY-MM-DD.json`. Nightly `__eval__` scheduler message (consolidation pattern).
`/mind` mein sparkline + last card. ~25 tasks: 8 single-tool, 6 multi-step, 5
governance (deny/confirm/panic), 3 park-resume, 3 memory-recall.
**Gate-use:** success ≥85% 7 din lagatar → L4 unlock discussion; regression
>10% drop → autonomy freeze + alert.

---

### P6 — Trust tab (desktop GUI native)

`ui/jarvis_v31/tab_panels.py` mein naya `TrustPanel(_GlassPanel)` — /mind ke
TRUST+AUDIT panels ka Qt twin, `trust_view.snapshot()` seedha call (HTTP nahi).
PANIC toggle → `set_panic()`; ▲▼ → `gate.set_grant()`. 30s QTimer refresh +
panic pe instant. Wireframe:
```
 ┌─ TRUST ─────────────────────────────────────┐
 │ [⏻ PANIC]  quiet 23–07  spend ₹0/5000       │
 │ device   torch,volume…      [Act·notify] ▲▼ │
 │ message  send msg/email     [Draft·conf] ▲▼ │
 │ payment  spend money        [Ask] 🔒CAP     │
 │ ── AUDIT ─────────────────────────────────  │
 │ 14:02 torch_on   device  ✓allow  "L3 grant" │
 │ 13:57 upi_pay    payment ✗deny   "HARD_CAP" │
 └─────────────────────────────────────────────┘
```
**Tests:** panel logic pure functions (row-build from snapshot dict). Size S.

---

### P7 — Sub-agents + background task queue (Q3·M9)

**Module: `core/task_queue.py`:** persistent jsonl queue; `Task = {id, goal_id,
priority, state: queued|running|done|failed, owner}`; worker pool (2 threads)
har task pe **apna** `AgentOrchestrator` instance — narrowed toolset
(`subagent_tools(profile)`) + L2-cap by default (sub-agent kabhi user-confirm
skip nahi kar sakta). Parent agent ko naya tool: `{"tool":"delegate",
"args":{goal, profile}}` → queue. Results envelope/notify se wapas.
Ledger entries mein `owner=sub:{id}`. **Depends:** P5 gate pass.
**Tests:** queue persistence/restart-resume, cap enforcement, delegate round-trip.

### P8 — Web agent (Playwright) (Q3·M8)

`core/web_agent.py`: allowlist domains (config), headless context, tools:
`web_open/web_read/web_fill/web_click/web_screenshot`; har action ledger mein
(`cls="web"` L2 → form-submit hamesha confirm); DOM-summary → LLM (token-diet:
readability extract). Sub-agent profile `web` (P7) mein mount hota hai.
**Gate:** golden web-tasks (search-and-extract 5/5) + 0 out-of-allowlist hits.

### P9 — Selfhood: personal LoRA + voice ID + extended features

- **LoRA:** `tools/export_corpus.py` (existing) → Colab QLoRA (docs/
  COLAB_TRAINING) → GGUF adapter → llama-cpp `--lora`. Data-collection AB SE
  on rakho (consented chat pairs).
- **Voice ID (F2):** sherpa speaker-embedding (3dspeaker model) — wake ke baad
  0.5s window pe verify; mismatch → ignore + log. Laptop `voice_id.py` port.
- Extended F1 (offline STT fallback), F3 (camera vision), F5 (caller announce),
  F7 (UPI on-demand), F9 (chime/ducking) — MOBILE_ASSISTANT_ROADMAP designs
  as-is, is queue ke S-slots mein interleave.

---

## 3-L. Track L — Laptop Companion (mind ko desk pe BODY do)

P-queue mostly "phone-as-body + laptop-as-mind" hai. Track L laptop ko bhi ek
poora **companion body** banata hai — HUD, true hotword, proactive screen-help,
quick capture. Grounding: `ui/jarvis_v31` mein `command_palette.py`,
`floating_dock.py`, `reactor.py`, `system_tray.py` **pehle se hain**; laptop
wake abhi sirf STT-phrase hai (`voice_engine.py` — "wake up jarvis" tabhi jab
STT sun raha ho); `notify_listener.py` (Windows-toast→TTS) exists;
`screen_actions.py` active-window jaanta hai; `voice_id.py` laptop pe hai.

```
                 LAPTOP COMPANION SURFACES (Track L)
 ┌─────────────────────────────────────────────────────────────────┐
 │  L2 sherpa hotword ─▶ L1 Mini-HUD (always-on-top)                │
 │       │                    │ expand                              │
 │  voice_gate (one owner) ──▶│ L5 palette v2 (Win+Shift+A,         │
 │                            │    type-or-speak, quick capture)    │
 │  L3 screen companion ──────▶ initiative ("is error pe 10 min     │
 │  (screen_agent+presence)     se atke ho — dekhun?")              │
 │  L4 phone-notif toasts ◀── P2/P3 envelopes (reverse mirror)      │
 │  L6 window/workspace skills ("chrome left snap", CODING layout)  │
 └─────────────────────────────────────────────────────────────────┘
```

### L1 — Desktop Mini-HUD (always-on-top reactor)
Frameless, translucent, click-through-when-idle Qt window (`ui/jarvis_v31/
mini_hud.py`) — phone ke compact overlay ka desktop twin, **`reactor.py` +
`floating_dock.py` reuse**. States: idle-dot(28px) → listening(pulse ring +
live partial) → speaking(amp spokes) → collapse. Qt flags:
`FramelessWindowHint|WindowStaysOnTopHint|Tool` + `WA_TranslucentBackground` +
`WA_ShowWithoutActivating` (focus kabhi nahi churata). Position: bottom-right,
drag-to-move, per-monitor DPI safe. Wake/palette/tray se summon; "bye"/idle →
collapse. AnimationBus se chat events subscribe (GUI thread pe hi).
```
 desktop (koi bhi app)                     expanded
 ┌───────────────────────────┐   ┌───────────────────────────┐
 │            work…          │   │ ┌───────────────────────┐ │
 │                           │   │ │ tum: "convert krdo pdf"│ │
 │                    ┌───┐  │   │ │ AERIS: "ho gaya — 2   │ │
 │                    │ ◉ │  │   │ │  files Desktop pe"    │ │
 │                    └───┘  │   │ │ [partial…]            │ │
 │              idle dot 28px│   │ └───────────────────────┘ │
 └───────────────────────────┘   │        ◉ reactor 48px     │
                                 └───────────────────────────┘
```
**Tests:** state-machine pure logic + AnimationBus event mapping. **Gate:** 0
focus-steal complaints; HUD visible <300ms after wake. **Size M.**

### L2 — True hotword on laptop (sherpa, phone assets reuse)
Abhi laptop wake = STT-phrase (STT chalna chahiye, battery/CPU bhaari, privacy
meh). Fix: `core/wake_laptop.py` — **wahi** sherpa-onnx KWS (phone ke
`assets/kws/*` models/keywords **reuse** — ek hi tuning, do body), sounddevice
16k mono stream, phone waala hi 2-stage plausibility check (code port).
Mic-ownership contract laptop pe bhi pavitra: spotter idle mein mic rakhta hai;
STT start hone pe `voice_gate` pause kare, conversation end pe resume (phone ke
pauseMic/resumeMic ka mirror). Optional stage-3: `voice_id.py` speaker-verify.
Voice-stack rule intact — Google STT/Neerja TTS untouched, sherpa sirf wake.
**Tests:** offline validator (phone waale samples reuse), gate arbitration unit.
**Gate:** phone waala hi (10/10 @1m, 0 false 30-min soak). **Size M.**

### L3 — Screen companion v2 (proactive madad, local-only)
`screen_agent.py` (OCR+LLM, live-verified) abhi sirf on-demand hai. v2: presence
FOCUS + same-window ≥10 min + error-pattern OCR match ("Exception|error|failed")
→ world_model `screen_context` → initiative `screen_help` (L1 suggest, openness-
gated): "Isi error pe kaafi der se ho — ek nazar daalun?" Haan pe existing
screen_assist flow. Sab **local** (OCR+Qwen on-device), screenshots disk pe
sirf opt-in. Palette se region-ask bhi (L5). **Tests:** trigger heuristics pure
(fake OCR strings + presence records). **Gate:** false-offer <1/day soak.
**Size M** (P4 openness ke baad — warna nag risk).

### L4 — Phone-notif toasts on laptop (reverse mirror) 
P3 ke `notif.event` envelopes ka laptop surface: Windows toast (winrt via
existing `notify_listener.py` infra का ulta — ab hum FIRE karte hain) + optional
TTS jab laptop hi active body ho (P2 registry decide kare — double-announce
kabhi nahi: **ek event, ek body**). Click → phone pe khole (FCM command).
**Tests:** routing (active-body matrix). **Size S** (P2/P3 ke saath free-ride).

### L5 — Command palette v2 + quick capture
Existing `command_palette.py` upgrade: global hotkey (Win+Shift+A, `keyboard`
lib) → floating palette **kahin se bhi**: type ya 🎤 hold-to-talk; quick verbs —
goal capture ("g: rahul follow up"), ask, screenshot-region-ask (L3 hook),
timer. Esc → gone, zero focus residue. Recent-3 + suggestions from
`SmartSuggestionsPanel` context. **Tests:** verb-parse pure. **Size S.**

### L6 — Window & workspace voice skills
"Chrome left snap", "sab minimize", "CODING layout lagao" (editor+terminal
arrangement per workspace profile). Build: `core/window_skills.py` —
pygetwindow/win32 move-resize + `screen_actions` active-window + profiles se
layout specs (`data/layouts.json`). Sab reversible (pehle wali geometry restore
= undo), `device` class L3. **Tests:** layout maths pure + undo round-trip.
**Gate:** 10 golden window-tasks. **Size M.**

---

## 3-S. Track S — Security & Privacy hardening

Assistant messages/payments/screen dekhta hai — iski security posture ko
first-class banao. Grounding: bridge AES-256-GCM E2E hai, `vault.py`
(Fernet+PBKDF2, user-memory encrypted) hai, `dpapi_vault.py` (Windows DPAPI
secrets) hai, panic switch hai. Gaps neeche.

### S1 — Ledger tamper-evidence (hash chain)
Audit trail tabhi audit hai jab badla na ja sake. Har entry mein
`prev_sha: sha256(prev_line)` — chain break = tamper flag. `Ledger.verify()
-> (ok, first_bad_line)`; `/mind` audit panel pe ✓chain badge; nightly verify
consolidation ke saath. Encryption NAHI (append-only + greppable rehna
chahiye — decision log). **Tests:** chain build/verify, tamper-detect,
legacy-lines (no prev_sha) grandfathered. **Size S.**

### S2 — Bridge key rotation + device revoke
Abhi pairing key static hai. Add: `core/cloud_bridge.py::rotate_key()` —
naya AES key envelope `key.rotate` (purani key se encrypted, one-time) →
dono side atomically switch, purana key 24h grace; `revoke_device(pid)` →
relay doc delete + local key purge → phone unpaired-state pe. Voice:
"aeris phone unpair karo" (destructive class → confirm). QR re-pair flow
unchanged. **Tests:** rotate round-trip fake-relay pe, grace-window, revoke
idempotence. **Size M.**

### S3 — At-rest coverage audit + sensitive stores encryption
`vault.py` sirf user-memory cover karta hai. Extend: `goals.json` (goal text
personal hota hai) + continuity mem-slices (phone pe already secure_storage)
→ Fernet via existing vault key-derivation; `data/secrets/*` → DPAPI wrap.
Ledger/routines plain rehte hain (S1 rationale + non-PII). Ek doc-table §9
mein: har store × {encrypted?, backup?, migration-ver}. **Tests:** encrypted
round-trip + passphrase-miss graceful. **Size S.**

### S4 — Phone-side panic + remote mute
Laptop panic word hai; phone se bhi: "aeris sab band karo" phone pe →
`panic.set` envelope → laptop `set_panic(True)` + saare FG services pause +
overlay dismiss. Reverse: laptop se "phone mute karo". Ye L0 hard-stop hai —
gate NAHI, seedha rasta (panic ko kabhi governance ke peeche mat rakho).
**Tests:** envelope→set_panic wiring, double-panic idempotent. **Size S.**

### S5 — Privacy page (`/mind/privacy`)
Ek nazar mein: kya store hota hai, kahan, encrypted?, kitna purana, delete
button per-store ("30 din se purana presence data delete"). `trust_view`
pattern ka twin: `privacy_view.py::snapshot()` + POST actions (loopback+header
guard same). **Trust ka doosra aadha privacy hai.** **Tests:** snapshot +
delete actions tmp stores pe. **Size S.**

---

## 3-V. Track V — Conversation polish (voice-stack FIXED, uske ird-gird)

Google en-IN STT + Neerja TTS **kabhi nahi badlenge** — ye track unke
*aas-paas* ka UX hai. Grounding: `tts.py` mein rate/pitch knobs already,
laptop dialogue-context (pronoun rewrite) already, `voice_gate.py` hai.

### V1 — Barge-in ("ruko" bolte hi chup)
AERIS bolte waqt mic band nahi — wake-spotter chalta rahe (low-power sherpa)
sirf "aeris/ruko/stop" keywords pe; hit → `tts.stop()` + turant listen. Phone:
TTS ke dauran spotter ko pause NA karo, sirf self-hearing guard text-match se
(apna hi bola "aeris" ignore — TTS text pata hai). Laptop: same via
`voice_gate`. **Tests:** self-hearing filter unit (TTS-echo transcript vs user
utterance), stop-latency <400ms manual gate. **Size M.**

### V2 — Wake chime + audio ducking (F9 concretize)
Wake pe 120ms subtle chime (asset, phone+laptop dono); AERIS bolte waqt music
duck (phone: AudioFocus `GAIN_TRANSIENT_MAY_DUCK`; laptop: pycaw se media
sessions −12dB, restore after). **Tests:** focus request/abandon lifecycle
unit; duck/restore idempotent. **Size S.**

### V3 — On-device dialogue context (phone T1/T2)
Laptop ka pronoun/follow-up rewriter ka LITE port Dart mein: last-entity slot
memory ("usko band karo" → last device/app), sirf Tier-1/2 ke liye (T3 Gemini
apna context rakhta hai). Pure Dart, testable. **Tests:** rewrite table-driven.
**Size S.**

### V4 — Quiet-voice profile (raat ka lihaaz)
Quiet-hours (gate se aata hai) mein TTS rate −10%, volume 60%, chime off,
non-urgent initiatives pehle se DROP hain. `tts.py` knobs hi use honge — voice
wahi Neerja. **Tests:** profile-select pure fn. **Size XS.**

---

## 3-I. Track I — Knowledge & recall depth

Grounding: `doc_index.py` (folder→chunks→embeddings→top-K QA) **already
built**; `presence_journal.day_summary()/digest_line()` hain; KG + fabric hain.

### I1 — Personal-docs RAG → fabric + skill
`doc_index` ko memory_fabric ka 4th recall source banao (`kind="docs"`,
salience 0.55) + voice skill: "mere documents mein dhundo — invoice kitne ka
tha" → index query → LLM answer with citation (file+chunk). Index folders
user-config (`data/doc_index_roots.json`), nightly re-index sirf changed files
(mtime). CPU guard: on-battery pe re-index skip. **Tests:** fabric-source
injection + ranking fit; index-refresh mtime logic. **Size M.**

### I2 — Temporal recall ("kal maine kya kiya tha?")
Query-parser date-window nikale (kal/parso/pichhle hafte/Mangalwar) →
`presence_journal.day_summary(day)` + episodic by-date + us din ke ledger
actions + done-goals → ek short Hinglish digest. New: `semantic_memory
.between(t0,t1)` accessor. **Tests:** date-parse table (Hinglish!), digest
compose with fakes. **Size S.**

### I3 — KG auto-enrichment (confirm-gated)
Conversations se entity-relation candidates (existing entity_extractor) →
"Yaad rakhun ki Sara tumhari sister hai?" → haan pe `kg.add_statement`. Kabhi
silent-write nahi (memory poisoning guard). Anti-nag: max 2 asks/day, sirf
high-confidence repeats. **Tests:** candidate extraction + gating counters.
**Size S.**

### I4 — Semantic file-finder skill
"Wo pdf dhundo jisme resume tha" → doc_index top-K + filename/mtime rank →
"3 mile — kholu pehla?" → open. Downloads/Desktop/Documents default roots.
I1 ke index ka hi reuse — naya infra zero. **Size XS** (I1 ke baad).

---

## 3-E. Track E — Personal app ecosystem hub

Tumhare doosre apps (aeris-expense, AppliTrack, Momentum, Vault) sab
Flutter+Firebase hain — AERIS unka **voice front-end** ban sakta hai. Ek
generic hub + thin adapters; har write L2 confirm-first (jab tak graduate na
ho jaye — routine_graduation isi ke liye hai).

```
 "aaj 250 ka khana"                     core/app_hub.py
   └▶ hub.classify() ──▶ adapter: expense ──▶ Firebase write (E2E jahaan
 "swiggy pe apply kiya"                       app already encrypt karta hai,
   └▶ adapter: applitrack                     wahi format follow)
 "aaj gym ho gaya"        adapters = {expense, applitrack, momentum, vault}
   └▶ adapter: momentum   har adapter: parse(text)->draft, confirm-line,
 "ye link vault mein"                  write(draft), undo(receipt)
```
**E1 expense** (F8): amount+category parse → "₹250 Food mein likh dun?" →
entry; undo = delete receipt-id. **E2 applitrack:** company/role parse →
application entry. **E3 momentum:** habit/journal quick-log. **E4 vault:**
share-sheet/link capture phone se (already share-inbox hai us app mein —
sirf envelope route). Sab adapters ke schemas apne app ke repos se (unke
models follow karo, naya format invent NA karo). **Tests:** parse tables per
adapter + hub routing + undo round-trip (fake Firebase). **Size M total,
per-adapter S.**

---

## 4. Dependency graph + sequencing

```
        P0 wake ──▶ P1 overlay B          (phone body)
                        │
        P2 continuity ──┼──▶ P3 perception ──▶ (morning brief, leave-now)
              │         │         │                    │
              │         ▼         ▼                    ▼
              └──▶ P4 openness ──▶ L3 screen companion │
                        │                              │
        P5 eval harness ──▶ L4-autonomy unlock ──▶ P7 sub-agents ──▶ P8 web agent
        P6 trust tab · L5 palette v2 · L1 mini-HUD (independent, kabhi bhi)
        L2 laptop hotword ──▶ L1 ko summon deta hai   (laptop body)
        P2+P3 ──▶ L4 notif toasts (free-ride)
        P9 LoRA/voice-id (data collection abhi se, training Q4)

 NOW (is hafta)      NEXT (2–3 hafte)          LATER (Q3/Q4)
 ┌──────────────┐    ┌───────────────────┐     ┌──────────────────┐
 │ P0 logs→fix  │    │ P2 continuity     │     │ P7 sub-agents    │
 │ P6 trust tab │    │ P3 perception     │     │ P8 web agent     │
 │ P4 openness  │    │ + L4 notif toasts │     │ P9 LoRA/voice-id │
 │ P5 harness   │    │ + S4 phone panic  │     │ L3 screen        │
 │ L5 palette v2│    │ P1 overlay B      │     │    companion     │
 │ L1 mini-HUD  │    │   (user haan pe)  │     │ I3 KG enrich     │
 │ S1 hash-chain│    │ L2 laptop hotword │     │ E2–E4 adapters   │
 │ S5 privacy pg│    │ L6 window skills  │     │ V1 barge-in      │
 │ I2 temporal  │    │ I1 docs-RAG       │     │ F-features       │
 │ S3 at-rest   │    │ I4 file-finder    │     └──────────────────┘
 └──────────────┘    │ E1 expense hook   │
                     │ V2 chime+duck ·V3 │
                     │ V4 quiet-voice    │
                     └───────────────────┘
```
NOW-column sab **laptop-side, user-independent** hai (P0 ke logs ke siwa) —
loop inhi pe chalega (order: P6→P4→P5→S1→S5→I2→S3→L5→L1). P1/P2/L2/V2-V3
rebuilds maangte hain; L3/V1 P4-openness+P0 ke baad.

---

## 5. Risk register

| Risk | Phase | Mitigation |
|---|---|---|
| HW noise-suppression speech khaata hai | P0 | diagnostics-first (ho gaya); NS off A/B |
| ColorOS overlay kill/deny | P1 | perm-checklist + fallback launchApp path rakhna |
| Split-brain replies (dono body bole) | P2 | laptop-authoritative registry + reply dedupe id |
| Notification privacy leak | P3 | whitelist + sender/title-only default + E2E + local-only class |
| Initiative spam with naye triggers | P3/P4 | openness floor+EMA, max_per_hour, source_id dedupe |
| Eval harness LLM flakiness | P5 | 3-run majority per task; latency budget alag metric |
| Sub-agent runaway | P7 | L2 cap + per-task step budget + queue depth limit + panic |
| Web agent prompt-injection | P8 | allowlist + read-only default + form-submit confirm + DOM sanitize |
| HUD focus-steal / game-mode annoyance | L1 | `WA_ShowWithoutActivating` + click-through idle + fullscreen-app pe auto-hide |
| Laptop mic contention (wake vs STT vs calls) | L2 | one-owner contract via voice_gate (phone pattern ka port); meeting/DND detect → wake off |
| Screen OCR privacy (passwords visible) | L3 | local-only processing, no disk persist default, password-field window-titles blocklist |
| Window-move data loss (unsaved dialogs) | L6 | sirf move/resize (kabhi close nahi bina confirm), geometry-undo hamesha |
| Key-rotation lockout (dono side out-of-sync) | S2 | 24h dual-key grace + QR re-pair hamesha zinda fallback |
| Docs-RAG CPU/battery drain | I1 | mtime-incremental re-index, on-battery skip, chunk cap |
| KG memory poisoning (galat "fact" ghus jaye) | I3 | writes HAMESHA confirm-gated; silent-write kabhi nahi |
| Ecosystem double-write / schema drift | E | receipt-id dedupe + undo per adapter; apps ke APNE model files follow (invent nahi) |
| Barge-in self-hearing (AERIS khud ko sune) | V1 | TTS-text echo filter (bola hua text transcript se match → ignore) |

---

## 6. Decision log (kyun aisa)

1. **brain_router SKIP** — laptop all-local (Qwen/llama-cpp); cloud tiers =
   unrequested privacy shift. Revisit sirf user maange to.
2. **Calendar/Gmail laptop-OAuth ke bajaye phone-as-sensor** — phone ke paas
   natively sab hai; OAuth surface + creds storage avoid; E2E already hai.
3. **Engine owns due-goals, world owns surroundings** — double-nudge dedupe
   (iter 21).
4. **Overlay = view-only isolate** — mic-ownership contract (ek owner) pavitra
   hai; overlay kabhi audio nahi chhoota.
5. **Voice stack fixed** — Google en-IN STT + Neerja TTS; sherpa sirf
   wake/fallback/voice-id. (Non-negotiable.)
6. **Sub-agents L2-capped** — delegation trust nahi badhaata; ladder per-class
   hi rehta hai.
7. **Eval gate before autonomy raise** — L4 sirf report-card se, vibes se nahi.
8. **Ledger = hash-chain, encryption NAHI** — audit append-only + greppable
   rehna chahiye; usme PII nahi hota (action names + classes). Tamper-evidence
   kaafi hai, confidentiality goals.json ki zaroorat hai (S3).
9. **Voice fixed → sirf prosody** — quiet-voice/chime/ducking sab rate/volume
   knobs se; Neerja/Google en-IN kabhi swap nahi (V-track ki hadd).
10. **KG writes confirm-gated** — memory poisoning guard; "yaad rakhun?" ke
    bina KG mein kuch nahi jaata (I3).
11. **App-hub = apps ke apne schemas** — expense/AppliTrack/Momentum/Vault ke
    model files unke repos se follow; har write L2 confirm-first, L3 sirf
    routine-graduation se (E-track).
12. **doc_index reuse** — naya RAG infra nahi banega; jo built+working hai
    usko fabric-source banao (I1).

---

## 7. Operating rules (unchanged, binding)

- Reliability → continuity → depth. Naya feature tabhi jab pichhla stable.
- Trust before autonomy: har autonomous capability = ladder-class + ledger +
  undo + (ab) eval-gate.
- Local-first privacy; PII sirf allowed classes mein, E2E ke andar.
- Har increment: tests green + (jahan ho sake) live-verify + docs/memory update.
- Training scripts user khud chalata hai. Python processes blanket-kill kabhi nahi.

---

## 8. North-star milestones + KPIs (assistant ka "IQ" measurable banao)

**Monthly north-star demos** (har mahine EK cheez jo pehle impossible thi):
```
 M+0  "Trust cockpit"      — GUI se panic/grants control + audit (P6) ✚
                             hash-verified ledger (S1)
 M+1  "Do body, ek mind"   — phone pe bola goal, laptop ne kiya, jawab
                             wahan aaya jahan tum the (P2)
 M+2  "Subah ka farishta"  — morning brief + "nikalna hai" + important-notif
                             triage, sab initiative se (P3+P4)
 M+3  "Report card ≥85%"   — 7-din rolling; L4 unlock discussion (P5)
 M+4  "Desk companion"     — laptop hotword + HUD + "isi error pe atke ho?"
                             (L1+L2+L3)
 M+5  "Har app ka voice"   — kharcha/job/habit bol ke likh jaata hai (E-track)
```

**KPI table** (nightly report card + /mind sparklines — P5 infra hi collect kare):
| KPI | Target | Source |
|---|---|---|
| Wake hit-rate quiet@1m | ≥95% | P0 soak checklist |
| False wakes / day | <1 | wake_last_debug counters |
| Wake→overlay visible | <800ms | P1 gate |
| Goal phone→laptop sync | <5s | P2 integration test |
| Reply-on-right-body | 10/10 | P2 registry test |
| Initiative act-rate (7d) | rising | openness stats (P4) |
| Initiative ignored-rate (7d) | falling | openness stats (P4) |
| Golden-task success (7d rolling) | ≥85% | report card (P5) |
| Autonomous actions ledger-logged | 100% | S1 verify + audit |
| Eval regression alert | >10% drop = freeze | P5 gate |

---

## 9. Data & schema registry (+ backup/migration + test strategy)

**Har persistent store ek jagah** — naya store banao to YAHAN row add karo:

| Store | Path | Ver | Encrypted | Since/Plan |
|---|---|---|---|---|
| Goals | `data/goals.json` | v1 | ✗ → Fernet (S3) | Q1·M2 |
| Ledger | `data/ledger.jsonl` | v1 | ✗ (by design, DL#8) + prev_sha (S1) | Q1·M3 |
| Trust grants | `data/trust_grants.json` | v1 | ✗ (non-PII) | iter-19 |
| Openness | `data/openness.json` | v1 | ✗ | P4 |
| Graduation | `data/routine_graduation.json` | v1 | ✗ | iter-9 |
| Routines | `data/routines.json` | v1 | ✗ | automation |
| Presence journal | `data/presence/*.jsonl` | v1 | ✗ (local-only class) | presence |
| Report cards | `data/report_card/*.json` | v1 | ✗ | P5 |
| Panic flag | `data/panic.flag` | — | — | iter Q1·M3 |
| Secrets | `data/secrets/*` | — | DPAPI (S3 audit) | bridge |
| User memory | (vault) | v1 | ✅ Fernet+PBKDF2 | existing |
| Doc index | `data/doc_index/*.pkl` | v1 | ✗ (derived data) | I1 |
| Layouts | `data/layouts.json` | v1 | ✗ | L6 |
| Backups | `data/backups/YYYY-MM-DD.zip` | — | inherits | S3 |

**Rules:** (1) har JSON store mein top-level `"v"` — loader `v` aur `v-1`
tolerate kare, usse purana = migrate-on-load + save; (2) sab writes
`atomic_io.write_atomic_json` se; (3) nightly consolidation ke saath
`data/` ka zip backup (secrets DPAPI-wrapped hi jaate hain), 7 rakhna;
(4) delete = privacy page se, backup se bhi purge option.

**Test strategy (binding):**
- **Fast lane** (default, har iteration): pure/injectable unit tests — no
  model, no disk beyond tmp_path, no network, no Qt event loop.
- **Golden lane** (P5): real local-LLM + mocked tools (mock-executor rule),
  nightly, report card mein.
- **Soak lane** (release se pehle): device checklists (wake 30-min fan-noise,
  overlay 20 conversations, initiative 1-week nag-count).
- **Pre-release checklist:** fast-lane green → `py_compile` all touched →
  live smoke (jahan surface hai: /mind, HTTP, device) → docs+memory update.
  Ye hi /loop ka har-iteration contract bhi hai.
