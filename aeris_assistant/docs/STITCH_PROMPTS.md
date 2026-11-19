# AERIS Assistant: Google Stitch prompt pack (Sci-Fi HUD edition)

These prompts are for **Google Stitch** (stitch.withgoogle.com), which generates mobile UI screens. You can then export the screens to Figma or HTML and port them to Flutter by hand.

The product and engineering spec is in [`BUILD_GUIDE.md`](BUILD_GUIDE.md). The animation stack is in BUILD_GUIDE §12.5. This file covers the visual design.

**Direction (2026-11-16):** a full sci-fi **JARVIS-style holographic HUD**. It should be techy, animated and impressive at first glance. It uses **one holo-cyan colour family**, with amber only for alerts, so it looks like a real film-grade interface rather than a rainbow "gamer" UI.

---

## 0. How to use this pack

Stitch works best **one screen at a time, with the same design system in every prompt**. If you paste one huge "design the whole app" prompt, you get 3–5 generic screens and drifting colours.

1. **Start a new Stitch project** and pick **Mobile** (not Web). If your Stitch has a higher-quality/experimental mode, use it for Prompt A, since HUD detail needs it.
2. **Paste Prompt A, the Master Prompt.** It sets the visual language and generates the Home screen. Iterate on it until the reactor core, HUD frames and type feel right. **Everything else copies this screen's look.**
3. **Do the screens in order.** For each prompt in section 3, paste the **Design System Block** from section 2 first, then the screen prompt. The block is what keeps all 40-odd screens consistent. It also redefines words like "glass card", "pill" and "Core orb" as HUD panels, HUD buttons and the reactor core, so every screen prompt comes out sci-fi.
4. **Fix with small follow-ups.** When a screen is close, use one or two changes per prompt. Section 4 has ready-made follow-ups, including "more HUD" and "less clutter" dials.
5. **Upload a reference image when it drifts.** Screenshot your approved Home and attach it with "match this visual style exactly".
6. **Export.** Use Copy to Figma (if your Stitch mode offers it) or export HTML/CSS. Name the Figma frames with the screen IDs (`S10-Home-Idle` etc.) so they line up with the Flutter routes in `BUILD_GUIDE.md` §12.3.
7. **Stitch draws still frames; Flutter makes them move.** All animation (rotating rings, scan sweeps, speaking waveforms, boot sequence) is specified in §5 below and BUILD_GUIDE §12.4–12.5. Don't ship Stitch's code. Treat it as a pixel reference.

> Stitch prompts have a length limit. If a prompt is rejected as too long, drop the final "Mood" paragraph first.

---

## 1. Prompt A: Master prompt (paste first, on its own)

```
Design a stunning dark sci-fi Android app called "AERIS", a personal AI assistant whose entire interface is a holographic HUD, like the AI system interfaces in high-end sci-fi films: an arc-reactor style core, rotating telemetry rings, targeting brackets, scan lines and live data readouts. It must impress at first glance, but stay clean, legible and premium, like a real military-grade heads-up display, not a cluttered gamer UI.

VISUAL LANGUAGE "HOLO HUD":
- Background: near-black deep navy #04070B with a very faint hexagonal micro-grid (#38D9FF at 4% opacity) and a soft radial cyan haze behind the center (#0B2A36 fading out). Subtle film-grain texture. A few faint horizontal scan lines at 3% opacity.
- Primary colour family: holo cyan #38D9FF (lines, glows, active states), dim cyan #167A94 for secondary lines and grids, white-cyan #CFF6FF for the brightest highlights. Everything glows slightly (outer glow 6-12px of the same cyan at 35%).
- Alert colours only for meaning: amber #FFB454 = attention/approval, red #FF4D5E = stop/error, mint #5EE6B5 = success/online.
- Text: primary #DDF4FF, secondary #7FA6B8, tertiary #44616F.
- Typography: "Oxanium" for display titles and HUD headers in UPPERCASE with wide tracking; "Sora" for readable body text and conversation; "JetBrains Mono" for telemetry readouts, numbers, coordinates, timestamps (10-12px, uppercase, +10% tracking).
- Panels: no rounded bubbly cards. Use HUD PANELS: translucent dark fill (#38D9FF at 4%), 1px cyan hairline border at 25%, chamfered/cut corners (45° clipped top-right and bottom-left), small bright L-shaped corner brackets, a tiny mono label tab on the top edge (like "SYS-01"). Backdrop blur behind panels.
- HUD details (with restraint, max 3-4 per screen): tick-mark rulers along edges, tiny coordinate readouts, crosshair "+" marks at panel corners, thin connector lines with dots linking panels to the core, small rotating hexagon icons, segmented progress bars.
- Icons: thin 1.5px line icons, cyan, geometric, never filled, never emoji.

THE SIGNATURE ELEMENT, "the Reactor Core": centered on Home, about 220px. Layer it from the center outward:
(1) a bright white-cyan glowing nucleus with bloom;
(2) a triangular/hexagonal inner lattice like an arc reactor;
(3) a thick segmented ring of ~36 cyan segments;
(4) a thin outer ring of fine tick marks with degree numbers (000, 090, 180, 270) in tiny mono;
(5) two partial arc rings (open 270° arcs) at different radii, offset, as if rotating in opposite directions;
(6) a faint radar sweep wedge;
(7) small data callouts connected by thin leader lines: "VOICE ID ✓", "CORE 98.2%", "LAT 38MS".
The core glows and lights up the haze around it.

SCREEN TO GENERATE: "Home – Command Center" (Android, 412x915).
Top HUD bar: left "AERIS // ONLINE" in Oxanium with a mint pulsing dot; center tiny mono "SYS 21:04:11 · 16.11.2026"; right a settings gear inside a hexagon outline.
Under it, a mono status strip with 4 compact readouts separated by thin dividers: "BATT 82%", "NET 5G", "TEMP 24°C", "WAKE: ARMED".
Greeting in Oxanium uppercase 22px: "GOOD EVENING, SHIVANG" with a typing-cursor block at the end, and a secondary Sora line "All systems nominal. Say 'Hey AERIS'."
Center: the Reactor Core with its leader-line callouts.
Below the core: a horizontal row of 4 command chips shaped as chamfered HUD buttons with thin icons: "ALARM 06:30", "MSG RAVI", "SCAN SCREEN", "WORK MODE".
Then two side-by-side HUD panels: "NEXT EVENT" with "STANDUP · 10:30" and a small segmented countdown bar; "REMINDER" with "PAY ELECTRICITY BILL" and an amber alert triangle.
Then a "LOG" panel with 3 terminal-style mono lines with timestamps and tier tags: "21:02 ▸ ALARM SET 06:30 [LOCAL]", "20:47 ▸ MSG SENT → RAVI [LOCAL]", "20:15 ▸ WEATHER QUERY [CLOUD]".
Bottom: a command dock: chamfered panel with a text field "> ENTER COMMAND_" (blinking cursor), and on the right a circular mic button styled as a mini reactor (concentric cyan rings, glowing center).
Bottom navigation: 4 items with thin icons and tiny Oxanium labels: CORE (active, glowing underline bar), LOG, MEMORY, PROTOCOLS.

Mood: cinematic, precise, alive. Strong focal point on the core, everything else aligned on an 8pt grid with clear hierarchy and plenty of dark space between HUD elements. Readable body text (WCAG AA). It should look like a real shipped flagship app that someone would screenshot to show friends.
```

---

## 2. The design system block (paste before every screen prompt)

```
[AERIS HOLO-HUD DESIGN SYSTEM — keep identical across all screens]
App: AERIS, dark sci-fi Android AI assistant; the whole UI is a holographic HUD like film AI systems; cinematic but clean and legible, not cluttered.
Background #04070B + faint cyan hex micro-grid (4%) + soft radial cyan haze + faint scan lines + film grain.
Colour: ONE family — holo cyan #38D9FF (glow 35%), dim cyan #167A94 secondary lines, white-cyan #CFF6FF highlights. Alerts only for meaning: amber #FFB454 attention, red #FF4D5E stop/error, mint #5EE6B5 success. Text #DDF4FF / #7FA6B8 / #44616F.
Type: Oxanium UPPERCASE wide-tracked for titles and HUD headers; Sora for body and conversation; JetBrains Mono UPPERCASE for telemetry, numbers, timestamps.
TRANSLATIONS (apply everywhere): "glass card"/"card" = HUD PANEL (4% cyan fill, 1px cyan border at 25%, chamfered cut corners, bright L-shaped corner brackets, tiny mono label tab like "SYS-02", backdrop blur). "pill"/"chip"/"button" = chamfered HUD button. "Core orb"/"orb" = the REACTOR CORE (glowing white-cyan nucleus, arc-reactor lattice, segmented ring, tick ring with degree labels, two counter-rotating partial arcs, radar sweep, leader-line data callouts). "bubble" = HUD transcript line (user lines right-aligned with a "▸ YOU" mono tag, AERIS lines left with a "◂ AERIS" tag and a thin cyan left rule). "toggle" = segmented cyan switch with ON/OFF mono labels. "bottom sheet" = HUD panel rising from the bottom with a bright scanning top edge. "graphite" = the HUD background.
HUD details, max 3-4 per screen: tick rulers on edges, crosshair marks, coordinate readouts, connector lines with dots, segmented bars, rotating hexagon icons.
Icons: thin 1.5px cyan line icons, geometric, never filled, never emoji.
Bottom nav: CORE / LOG / MEMORY / PROTOCOLS with a glowing underline on the active item.
Android 412x915, status bar + gesture nav visible. 8pt grid, 20px side margins.
```

---

## 3. Screen prompts

Screen IDs match the Flutter routes in BUILD_GUIDE.md §12.3. **Paste the Design System Block first, then one of these.** The block's TRANSLATIONS turn the generic words ("card", "orb", "pill") into HUD elements automatically.

### Group 0: The showpieces (do these right after Prompt A)

These five screens carry the "impress in one glance" moment. Get them perfect before the rest.

#### X01 Voice: Listening (HUD)
```
SCREEN: "Voice – Listening" full-screen HUD.
Background darker, the hex grid brighter near the core (8%), screen framed by four large corner brackets.
Top: Oxanium "AERIS // LISTENING" with a pulsing cyan dot; right "✕" in a hexagon. Under it a tiny mono line "VOICE ID: SHIVANG ✓ · MIC 16KHZ · EN-IN".
Center: the Reactor Core at 260px in LISTENING mode: the segmented ring has become a circular audio spectrum — 72 radial bars pointing outward with varying lengths like a live equaliser wrapped around the core, the brightest bars white-cyan; the nucleus brightened; the outer tick ring rotating (show motion blur on one arc).
Below the core: the live transcript, typed out like a terminal in Sora 22px: confirmed words in #DDF4FF, the still-forming last words in #7FA6B8 with a blinking cyan block cursor: "Ravi ko WhatsApp karo ki main late▌".
Under that a flat horizontal oscilloscope waveform line (full width, thin cyan, glowing) showing the voice signal.
Bottom: three hexagon buttons: keyboard, a large red-outlined STOP hexagon in the middle, mute. Mono caption "SAY 'BAS' TO END SESSION".
```

#### X02 Voice: Thinking / processing (HUD)
```
SCREEN: "Voice – Processing" full-screen HUD.
Same frame. The Reactor Core in PROCESSING mode: the spectrum bars collapse into a tight ring; three concentric partial arcs spin at different speeds (show them at different angles); small data particles stream inward toward the nucleus along spiral paths; the nucleus pulses.
Around the core, 3 leader-line callouts appear one by one: "PARSING INTENT…", "TOOL: SEND_MESSAGE", "CONTACT: RAVI SHARMA ✓".
The transcript moved up and shrunk (secondary, 16px) with a "▸ YOU" tag.
Under the core a horizontal pipeline of 4 small chamfered nodes connected by a line: SKILLS (lit, mint check) → NEURAL CORE (pulsing cyan, active) → LAPTOP (dim) → CLOUD (dim), mono caption "ROUTE · ON-DEVICE · 412 MS".
Bottom: single STOP hexagon.
```

#### X03 Voice: Speaking (HUD)
```
SCREEN: "Voice – Speaking" full-screen HUD.
The Reactor Core in SPEAKING mode: 3 concentric shockwave rings expanding outward from the core at fading opacity (like sound waves), the nucleus bright white-cyan, the segmented ring segments lighting in sequence; behind the core a horizontal mirrored waveform (symmetrical bars above and below a center line, cyan, tallest in the middle) spanning the full width — the voice of AERIS.
Above the waveform, mono "◂ AERIS · VOICE: NEERJA".
The reply in Sora 22px, left aligned in a HUD panel with a thin cyan left rule, words appearing as spoken (the current word highlighted with a cyan underline): "Message ready for Ravi: 'Main 10 minute late hoon.' Bhej doon?"
Under it an approval HUD panel with an amber chamfered border and an amber label tab "AUTHORISATION REQUIRED": recipient "RAVI SHARMA", message preview, two HUD buttons: "TRANSMIT" (cyan filled glow) and "ABORT" (red outline). Mono "OR SAY 'HAAN' / 'NAHI'".
```

#### X04 Compact HUD over another app
```
SCREEN: "Voice – Compact HUD over another app".
Background: a blurred, darkened generic chat app screenshot (16px blur, 60% dark navy scrim with faint scan lines).
Bottom: a HUD panel rising from the bottom (chamfered top corners, bright scanning top edge line, corner brackets), 45% of the screen.
Inside: HUD transcript lines — "▸ YOU: Kal subah 6:30 ka alarm laga do" (right), "◂ AERIS: Done — alarm set for 6:30 AM tomorrow." (left, cyan left rule) followed by a confirmation chip panel with a mint left bar "ALARM · 06:30 · WED" and "UNDO".
Divider made of a dotted cyan line.
Bottom row: a 64px mini Reactor Core in LISTENING mode (spectrum ring), mono "LISTENING" in cyan, the live transcript "aur ek reminder…▌", and a small red STOP hexagon on the right.
```

#### X05 System status / diagnostics HUD (the screenshot screen)
```
SCREEN: "System Status" — a dense but beautiful sci-fi diagnostics dashboard.
Top: Oxanium "SYSTEM STATUS" with mono "UPTIME 06:12:44".
Center-top: a semicircular gauge cluster: three nested arc gauges (WAKE ENGINE 99%, NEURAL CORE LOAD 34%, BATTERY 82%) in cyan with tick marks and mono values at the arc ends.
Below: a 2x2 grid of HUD panels:
1) "WAKE CONFIDENCE" — a live scrolling line graph with a dashed amber threshold line and one mint spike labelled "0.91 ✓ YOU".
2) "AUDIO" — a small circular spectrum.
3) "MEMORY" — mono "1,284 NODES" with a tiny network-graph illustration of dots and lines.
4) "LINKS" — "LAPTOP: ONLINE 34MS" mint, "CLOUD: STANDBY" dim.
Bottom: a terminal panel scrolling mono log lines with timestamps: "21:04:11 WAKE 0.91 ACCEPT (VOICE 0.84)", "21:04:12 STT EN-IN START", "21:04:14 ROUTE SKILLS/SET_ALARM 38MS", one red line "20:51:02 FGS KILLED — RESTARTED".
```

### Group 1: First run and onboarding

#### S00 Boot sequence (the "wow" first launch)
```
SCREEN: "Boot – System Initialising" (the cinematic first-launch frame).
Full-screen HUD background. In the center, the Reactor Core mid-ignition: the outer tick ring is drawn 70% (a bright leading point where it is still drawing), the segmented ring has 24 of 36 segments lit, the nucleus is a dim glow just igniting, a horizontal bright scan line crosses the core.
Left side: a vertical terminal log in JetBrains Mono 10px, lines appearing top to bottom with mint "OK" on the right:
"> BOOT AERIS KERNEL v1.0 ......... OK"
"> LOAD WAKE ENGINE [OWW] ......... OK"
"> VOICE PROFILE: SHIVANG ......... OK"
"> NEURAL CORE (ON-DEVICE) ........ 72%"
"> LINK: LAPTOP ................... SKIP"
Bottom: the wordmark "A.E.R.I.S" in Oxanium 34px with very wide tracking and a soft glow, a mono tagline under it, and a segmented progress bar (20 segments, 14 lit) with "72%" on the right.
Corner brackets framing the whole screen at all four corners. No buttons.
```

#### S01 Onboarding: Welcome
```
SCREEN: "Onboarding 1/6 – Welcome".
Top: a thin segmented progress indicator (6 segments, first one holo cyan, rest #171C23) and a "Skip" text button on the right.
Upper half: the Core orb at 140px with gentle glow.
Headline (Sora 30px semibold, left-aligned): "Your assistant. On your phone. Under your control."
Body (secondary, 15px): "AERIS listens for its name, understands Hinglish and English, and does things on your phone — most of it without the internet."
Three compact feature rows with thin line icons in holo cyan: "Wakes on 'Hey AERIS'", "Runs on-device first", "Asks before it acts".
Bottom: full-width primary button (holo cyan fill #38D9FF, dark text #0B0E12, radius 16, 56px) "Get started", and below it a text link "I already have a backup".
```

#### S02 Onboarding: Language and voice
```
SCREEN: "Onboarding 2/6 – How should I talk?".
Progress indicator at segment 2.
Headline: "How should I talk to you?"
Subtitle: "You can change this anytime."
Three large selectable glass cards stacked vertically (radius 20), each with a radio indicator on the right:
1) "Hinglish" — "Hindi + English, the way you actually talk" — tag pill "RECOMMENDED" in holo cyan tint — this one SELECTED (holo cyan 1.5px border, 10% cyan tint fill).
2) "English (India)" — "Indian English, no Hindi".
3) "English (US)".
Below the cards a "Voice preview" row: a small play button (circle outline), a waveform of thin vertical bars in holo cyan, label "Neerja · Indian English voice" in mono.
Bottom: primary button "Continue", secondary text button "Back".
```

#### S03 Onboarding: Permissions
```
SCREEN: "Onboarding 3/6 – Permissions".
Headline: "A few permissions, explained honestly."
Subtitle: "Each one unlocks something specific. Nothing is uploaded."
A vertical list of 5 permission rows inside one glass card group, separated by hairlines. Each row: thin line icon in a 40px rounded-square with 10% cyan tint, title, one-line reason in secondary, and a right-side state:
1) Microphone — "To hear 'Hey AERIS' and your commands" — mint check "GRANTED".
2) Notifications — "To show that AERIS is listening" — mint check "GRANTED".
3) Contacts — "To call or message people by name" — holo cyan small button "Allow".
4) Screen control (Accessibility) — "To tap and type in apps for you" — holo cyan outline button "Set up".
5) Run in background — "So your phone doesn't stop AERIS" — amber pill "NEEDED".
Under the list an info callout (amber 10% fill, amber left accent line): "Realme / ColorOS phones also need Auto-launch ON. We'll take you there."
Bottom: primary "Continue" (enabled), and mono caption "3 of 5 ready".
```

#### S04 Onboarding: Train your wake word
```
SCREEN: "Onboarding 4/6 – Teach me your voice".
Headline: "Say 'Hey AERIS' three times."
Subtitle: "This lets me wake only for you, and ignore the TV."
Center: the Core orb in LISTENING state — brighter holo-cyan core, the orbital ring broken into amplitude-reactive tick marks of varying length (like an audio visualiser wrapped around the sphere).
Under the orb: three step indicators in a row (circles 40px): step 1 done (mint fill with check), step 2 active (holo cyan ring, pulsing, label "Listening…"), step 3 pending (outline).
Below: a live level meter — a thin horizontal bar with a marker, mono label "INPUT LEVEL · GOOD".
Helper text in secondary: "Speak normally, about an arm's length away."
Bottom: text button "Re-record", text button "Skip for now" (tertiary).
```

#### S05 Onboarding: Wake word test
```
SCREEN: "Onboarding 5/6 – Let's test it".
Headline: "Try waking me up."
A large glass card with a live "wake confidence" graph: a scrolling line chart over the last 10 seconds in holo cyan, with a horizontal dashed amber threshold line labelled "THRESHOLD 0.50" in mono, and one spike above the line with a mint marker labelled "DETECTED · 0.91 · YOU".
Under the card a 3-column stat strip in mono: "WAKES 3", "MISSED 0", "FALSE 0".
Then a segmented control "Sensitivity": Low | Balanced (selected) | High.
Helper text: "Balanced is right for most rooms. Choose High if I miss you, Low if I wake by mistake."
Bottom: primary "Looks good", secondary text "Train again".
```

#### S06 Onboarding: Ready
```
SCREEN: "Onboarding 6/6 – Ready".
Center: the Core orb fully ignited with a soft mint success ring around it (thin, single).
Headline centered: "AERIS is ready."
Subtitle: "Say 'Hey AERIS' anytime, or hold the power button."
A glass card with 3 "try saying" examples, each line prefixed with a small mono quote mark in holo cyan:
"Kal subah 6:30 ka alarm laga do"
"Ravi ko WhatsApp karo ki main late hoon"
"What's on my screen?"
Bottom: primary "Start using AERIS".
```

### Group 2: Home and the voice experience

#### S10 Home: Command Center
```
SCREEN: "Home – Command Center".
(Same as the approved master Home from Prompt A.) HUD top bar "AERIS // ONLINE" with a mint pulsing dot and the system clock; mono status strip BATT / NET / TEMP / WAKE: ARMED; Oxanium greeting "GOOD EVENING, SHIVANG"; the Reactor Core idle with leader-line callouts; command chips row; NEXT EVENT + REMINDER panels; LOG terminal panel; command dock with mini-reactor mic; bottom nav CORE / LOG / MEMORY / PROTOCOLS.
```

#### S11 Home: Wake disabled / paused
```
SCREEN: "Home – Wake engine offline".
Same Command Center layout, but the top bar reads "AERIS // WAKE OFFLINE" with an amber dot, and the Reactor Core is powered down: nucleus dark, segmented ring unlit (only outlines at 15%), arcs stopped, one amber warning callout on a leader line "WAKE ENGINE HALTED".
Under the greeting an amber-bordered HUD panel with an amber label tab "ALERT": title "I can't hear 'Hey AERIS' right now", body "Your phone stopped the background service.", and a chamfered button "RESTORE".
The mic button in the dock is still lit (hold-to-talk still works).
```

#### S12–S15 Voice states
Use the showpieces **X04** (compact over another app), **X01** (listening), **X02** (processing) and **X03** (speaking) from Group 0. Those are the canonical voice screens.

#### S16 Voice: Couldn't hear you
```
SCREEN: "Voice – No signal".
Full-screen voice HUD frame. The Reactor Core idle and dimmed, with a single amber ring pulse and a flat-line oscilloscope under it (a straight cyan line with tiny noise).
Oxanium centered "NO SIGNAL DETECTED", Sora secondary "Didn't catch that. Try again, or type instead."
Two chamfered HUD buttons: "RETRY" (cyan, mic icon) and "TYPE" (outline, keyboard icon).
Mono caption: "SILENCE · 6.0S · MIC OK".
```

### Group 3: Conversation and agent

#### S20 Conversation thread (chat)
```
SCREEN: "Conversation".
Top app bar: back arrow, title "Today" with mono subtitle "14 TURNS · ON-DEVICE", right overflow icon.
Scrollable thread with rich content, generous spacing:
1) User bubble (raised #171C23, right): "What's the weather and do I need an umbrella?"
2) Assistant answer (no bubble, left, primary text) + a weather card: large mono "24°", "Light rain after 5 PM", a tiny 6-hour precipitation bar chart in holo cyan, footer mono "SOURCE · OPEN-METEO · 2 MIN AGO".
3) User bubble: "Set a reminder at 4:45 to take umbrella".
4) Assistant: "Reminder set." + compact action card with mint left accent: bell icon, "4:45 PM · Take umbrella", "Undo".
5) Assistant answer to a knowledge question with a tier tag "CLOUD" pill and two small source chips "wikipedia.org", "britannica.com".
Each assistant message has a tiny row of actions on long-press hint: copy, speak, thumbs-up/down (thin icons, tertiary).
Bottom: floating input dock: "+" attach button, text field "Message AERIS…", mic button holo cyan.
```

#### S21 Agent: Multi-step task running
```
SCREEN: "Agent – Task in progress".
Top: mono label "TASK · RUNNING · 00:23" with a pulsing holo-cyan dot, and a red-outline "Stop" pill button on the right.
Task title (Sora 22px): "Make a birthday poster and send it to Ravi on WhatsApp".
A vertical step timeline (thin 1px line connecting nodes):
- Step 1 done (mint check node): "Opened Gemini app" mono "2.1s".
- Step 2 done: "Asked for a birthday poster image".
- Step 3 done: "Saved the image to gallery".
- Step 4 active (holo cyan pulsing node, slightly larger, row highlighted with 8% cyan tint): "Opening WhatsApp chat with Ravi…" with a thin indeterminate progress line.
- Step 5 pending (hollow node, tertiary): "Send image — needs your approval" with an amber "APPROVAL" mini tag.
Below the timeline: a small glass "live view" card showing a miniature, blurred phone screenshot thumbnail with caption mono "WHAT AERIS SEES".
Bottom: footer note in tertiary: "AERIS will never pay, buy, or delete anything."
```

#### S22 Approval sheet
```
SCREEN: "Approval – Send message".
Background: dimmed blurred conversation.
Bottom sheet (frosted, radius 28), with drag handle.
Header row: amber dot + mono label "NEEDS YOUR OK".
Title: "Send this to Ravi Sharma?"
A preview card: WhatsApp line icon, recipient avatar initials circle "RS", message text "Main 10 minute late hoon, start karo 🙏" (allow this single emoji since it's user content), attached image thumbnail (rounded 12) of a poster.
Row of options: checkbox "Always allow messages to Ravi without asking" (unchecked).
Buttons: full-width primary "Send" (holo cyan), full-width secondary outline "Edit message", text button "Cancel" (red text).
Mono caption: "OR SAY 'HAAN BHEJO' / 'NAHI'".
```

#### S23 Task finished summary
```
SCREEN: "Agent – Task complete".
Center: Core orb small (96px) with a mint success ring.
Title: "Done in 41 seconds."
A glass summary card: 5 compact rows with mint checks (Opened Gemini, Generated poster, Saved image, Opened Ravi's chat, Sent with your approval), mono durations right-aligned.
Below: two outline buttons side by side "Save as routine" and "View log".
```

### Group 4: Activity, memory, routines

#### S30 Activity (history)
```
SCREEN: "Activity".
Top bar title "Activity", right: filter icon, search icon.
Filter chips row: All (selected, cyan tint), Voice, Actions, Agent, Errors.
Grouped list by day with mono sticky headers "TODAY", "YESTERDAY".
Each row: left a 36px rounded-square icon (line icon), title ("Alarm set · 6:30 AM"), subtitle secondary ("You said: 'kal subah 6:30 ka alarm'"), right side mono time "21:04" and a tier tag pill ON-DEVICE / LAPTOP / CLOUD. One row has a red dot and subtitle "Failed: WhatsApp not installed". One row has an amber dot "Waiting for approval".
Bottom nav: Activity active.
Floating small pill at bottom above nav: "Recordings are never stored" with a lock icon, tertiary.
```

#### S31 Activity: Item detail (transparency)
```
SCREEN: "Activity – Detail".
Back arrow, title "Alarm set".
Section "WHAT YOU SAID" (mono label): quote card "kal subah 6:30 ka alarm laga do".
Section "HOW AERIS UNDERSTOOD IT": a code-like glass card in JetBrains Mono showing: tool: set_alarm, time: 06:30, day: tomorrow, confidence: 0.97.
Section "WHO ANSWERED": a horizontal 4-step ladder: Skills → On-device brain → Laptop → Cloud, with "Skills" highlighted holo cyan and the rest tertiary, caption "Answered in 38 ms, offline".
Section "RESULT": mint check "Alarm created in Clock".
Bottom: buttons "Undo" (outline) and "That was wrong" (text, amber) which teaches AERIS.
```

#### S32 Memory: What I know
```
SCREEN: "Memory".
Title "Memory" with subtitle secondary "What AERIS remembers about you. Only on this phone."
Search field (glass).
Segmented tabs: Facts | Notes | People | Places.
Facts tab content: list of glass cards, each with a fact in primary text ("You prefer Hinglish replies", "Your office is in Sector 62, Noida", "Ravi = Ravi Sharma (friend)"), a mono source line "LEARNED FROM CHAT · 12 NOV", and a trailing overflow icon. One card is amber-tagged "UNSURE · CONFIRM?" with two tiny buttons "Yes" / "No".
Floating action button (holo cyan, + icon) "Add memory".
Bottom nav: Memory active.
```

#### S33 Memory: Edit item
```
SCREEN: "Memory – Edit".
Top bar: close X, title "Edit memory", right a "Save" text button (holo cyan, enabled because changed).
A multi-line glass text field containing "Your office is in Sector 62, Noida".
Category selector chips: Fact (selected), Place, Person, Preference.
Toggle row: "Use this when answering" (on).
Destructive row at bottom: red text button "Delete memory" with trash icon.
An unsaved-changes bar docked above keyboard area: graphite raised bar "Unsaved changes" with "Discard" (text) and "Save" (holo cyan).
```

#### S34 Routines / Modes
```
SCREEN: "Routines".
Title "Routines", subtitle "One sentence, many actions."
A featured glass card at top "Work mode" with a toggle (ON, holo cyan) and mono "ACTIVE SINCE 09:30", chips listing actions: "DND on", "Open Slack", "Volume 30%", "Focus playlist".
List of other routines as cards with toggles: "Sleep mode — 'good night bolo'", "Driving — when Bluetooth 'Car' connects", "Morning brief — 7:30 AM weekdays".
Each card shows the trigger in mono at the top ("SAY · 'WORK MODE CHALU KARO'", "TIME · 07:30 MON–FRI", "EVENT · CAR BLUETOOTH").
A suggested routine card with amber dashed border: "Suggestion: you open Slack + mute every weekday at 9:30. Make it a routine?" buttons "Create" / "Dismiss".
Floating + button. Bottom nav: Routines active.
```

#### S35 Routine editor
```
SCREEN: "Routine – Edit".
Top bar: back, title "Work mode", "Save" text button.
Section "WHEN" (mono label): a card with trigger type selector chips Say / Time / Place / Event (Say selected) and a field "work mode chalu karo".
Section "DO": an ordered list of action rows with drag handles on the left, line icon, label, and a right chevron: 1 "Turn on Do Not Disturb", 2 "Set media volume to 30%", 3 "Open Slack", 4 "Play 'Focus' playlist". Dashed "+ Add action" row at the end.
Section "THEN SAY": field "Work mode on. All the best!".
Bottom: outline button "Test run" with play icon.
```

### Group 5: Abilities, devices, reminders

#### S40 Abilities library
```
SCREEN: "Abilities".
Title "What I can do", search field "Search abilities…".
Category chips: All, Phone, Messages, Apps, Screen, Media, Info, Laptop.
Grid of 2-column glass tiles (radius 20), each: 36px line icon in holo cyan, title ("Calls", "WhatsApp", "Alarms & timers", "Read my screen", "Open any app", "Flashlight", "Laptop control", "Translate"), mono count ("12 COMMANDS"), and a tiny status dot: mint = ready, amber = needs permission (e.g. "Read my screen" shows amber + "SETUP").
At top, a glass highlight card: "Try: 'Screen pe kya error hai?'" with a play/try button.
```

#### S41 Ability detail
```
SCREEN: "Ability – WhatsApp".
Header: large line icon, title "WhatsApp", status pill mint "READY".
Section "SAY IT LIKE": list of example phrases in quote cards with a small play icon each: "Ravi ko WhatsApp karo ki…", "Send this photo to Mom on WhatsApp", "Last message padh ke sunao".
Section "NEEDS": checklist rows: Contacts (mint check), Screen control (mint check), WhatsApp installed (mint check).
Section "SAFETY": text "AERIS always shows you the message before sending." and a toggle "Ask before sending" (ON, locked with lock icon for unknown contacts).
```

#### S42 Reminders and alarms
```
SCREEN: "Reminders".
Title "Reminders", segmented control: Upcoming | Alarms | Done.
Upcoming: grouped by "TODAY", "TOMORROW" mono headers; rows with a circular checkbox, title, mono time on the right, optional location pin icon ("When I reach office"). One overdue row in amber text "Overdue · 2h".
Alarms tab preview not needed.
Floating dock at bottom: mic button + "Say a reminder…" field.
```

#### S43 Linked devices (laptop, optional)
```
SCREEN: "Devices".
Title "Devices", subtitle "Optional. AERIS works fully without a laptop."
A glass card for a paired laptop: laptop line icon, name "SHIVANG-PC", mint pill "ONLINE · LAN · 34 ms", mono "END-TO-END ENCRYPTED", a row of quick actions as small outline buttons: "Lock", "Screenshot", "Open VS Code", "Send clipboard".
A second card for this phone: "This phone · RMX3741", mono "BATTERY 82% · WAKE ON".
Dashed card "+ Link a laptop" with a QR icon.
Bottom text tertiary: "Disconnect any time. Nothing is stored on servers."
```

### Group 6: Settings (HUD styled, standard behaviour)

#### S50 Settings hub
```
SCREEN: "Settings".
Large title "Settings".
A profile summary card: avatar circle "S", name "Shivang", mono "HINGLISH · NEERJA VOICE · ON-DEVICE FIRST", chevron.
Grouped list sections in glass group cards with hairline separators, each row = line icon in a 32px tinted rounded square, title, secondary value on the right, chevron:
"ASSISTANT": Wake word ("Hey AERIS · Balanced"), Voice & language ("Hinglish"), Brain ("On-device + Cloud fallback").
"PHONE": Permissions ("1 needs attention" in amber), Screen control ("On"), Default assistant ("AERIS").
"YOU": Memory, Routines, Privacy.
"SYSTEM": Battery & background ("Protected" mint), Diagnostics, About.
Mono footer: "AERIS 1.0.0 · BUILD 42".
```

#### S51 Settings: Wake word
```
SCREEN: "Settings – Wake word".
Top bar: back, title "Wake word".
Master toggle row (large): "Listen for 'Hey AERIS'" ON (holo cyan switch).
A live test card: small Core orb 64px, mono "SAY THE WAKE WORD TO TEST", a horizontal confidence meter (holo cyan fill) with a dashed amber threshold marker, last result mono "LAST · 0.88 · ACCEPTED · 14:02".
Segmented control "Sensitivity": Low | Balanced | High.
Rows: "Voice match (only wake for me)" toggle ON; "Retrain my voice" chevron with mono "3 SAMPLES · 12 NOV"; "Wake phrase" value "Hey AERIS" chevron; "Also wake on" value "Jarvis" chevron; "Chime on wake" toggle; "Battery saver: pause when screen off and battery < 15%" toggle.
Stats strip in mono at bottom: "TODAY · 14 WAKES · 0 FALSE · BATTERY 1.8%".
Small snackbar visible at bottom: "Saved" with mint check (instant-apply settings).
```

#### S52 Settings: Voice and language
```
SCREEN: "Settings – Voice & language".
Rows: "Language" (Hinglish), "Voice" (Neerja · Indian English) with play preview button, "Speaking speed" slider (1.0x) with mono ticks, "Reply length" segmented Short | Normal | Detailed, "Speak replies" toggle, "Continue listening after reply" toggle ON with caption "Ends when you say 'bas' or 'bye'".
Section "RECOGNITION": "Speech engine" value "Google · en-IN" (read-only, lock icon, caption "Tuned for Hinglish"), "Wait for pauses" slider "1.2 s".
```

#### S53 Settings: Brain
```
SCREEN: "Settings – Brain".
Explainer card at top: a vertical 4-step ladder graphic — 1 Skills (instant, offline), 2 On-device AI (private), 3 Laptop (if linked), 4 Cloud (optional) — each with a mono latency hint ("~40 ms", "~3 s", "~300 ms", "~2 s") and a toggle for 3 and 4.
On-device model card: name "AERIS Brain · Qwen3 1.7B Q4", mono "1.8 GB · LOADED · 5.5 TOK/S", buttons "Unload" (outline) and "Change model" (text).
Cloud card: "Gemini API key" obscured field "••••••••3f9a" with "Test" outline button, mint result "KEY WORKS · 412 ms"; toggle "Allow web search"; caption amber: "Cloud requests leave your phone."
Mode selector: Off | Shadow | On for the on-device brain, with "Shadow" explained in caption.
Form uses explicit Save button at bottom (disabled until changed).
```

#### S54 Settings: Permissions health
```
SCREEN: "Settings – Permissions & background".
A health score card at top: big mono "4/5", mint/amber ring progress, title "Almost bulletproof".
List rows with state on the right: Microphone (mint GRANTED), Notifications (mint), Contacts (mint), Screen control (mint ON), Battery optimisation (amber "RESTRICTED" + "Fix" button), Auto-launch (ColorOS) (amber "CHECK" + "Open"), Default assistant (mint "AERIS").
Info callout explaining why: "Some phones kill background apps to save battery. These two settings keep 'Hey AERIS' alive."
```

#### S55 Settings: Privacy
```
SCREEN: "Settings – Privacy".
Hero line: lock icon in holo cyan, "Your voice stays on your phone." secondary: "Wake word detection is 100% on-device. Audio is only sent for speech-to-text after you wake AERIS."
Rows: "Keep activity history" toggle with value "30 days" chevron; "Store voice recordings" toggle OFF with lock (never); "Allow cloud brain" toggle; "Export my data" chevron; "Delete all memories" red text row; "Delete everything" red text row.
Mono footer: "NO ANALYTICS · NO ADS · NO ACCOUNT REQUIRED".
```

#### S56 Diagnostics
```
SCREEN: "Diagnostics".
A 2x2 grid of metric tiles in mono: "WAKE SERVICE · RUNNING · 6h 12m" (mint), "MIC OWNER · SPOTTER", "BRAIN · LOADED · 1.8 GB", "LAST LATENCY · 38 ms".
A small sparkline card "Wake confidence (last hour)" with threshold line.
An event log card in JetBrains Mono 11px, dark inset background, lines like "21:04:11 WAKE 0.91 accepted (voice match 0.84)", "21:04:12 STT start en-IN", "21:04:14 ROUTE skills/set_alarm 38ms", one red line "20:51:02 FGS killed by system — restarted".
Buttons: "Copy log", "Share report".
```

### Group 7: System surfaces

#### S60 Persistent notification + quick settings tile
```
SCREEN: "Android notification shade showing AERIS".
Show the Android notification shade (dark) with a pinned AERIS foreground-service notification: small holo-cyan orb icon, title "AERIS is listening for 'Hey AERIS'", subtitle "On-device · 1.8% battery today", action buttons "Pause 1 hr", "Talk now".
Above, in the quick settings row, a tile "AERIS" with an orb icon, highlighted (active).
```

#### S61 Home-screen widgets
```
SCREEN: "Android home screen with AERIS widgets".
A generic dark Android launcher wallpaper (abstract graphite gradient). Show 3 AERIS widgets:
1) 4x1 bar widget: small orb + "Ask AERIS" + mic button (holo cyan).
2) 2x2 widget: Core orb with mono status "LISTENING" and "Next: Standup 10:30".
3) 4x2 widget "Routines": three pill buttons "Work mode", "Sleep", "Drive".
Glass styling consistent with the app.
```

#### S62 Lock screen voice
```
SCREEN: "Lock screen – AERIS answering".
Over a dark lock-screen wallpaper with clock "21:04", the compact AERIS voice sheet at bottom (frosted): the user said "Time kya hua?", assistant answer "Nau baj ke chaar minute." Mono note: "PERSONAL ACTIONS NEED UNLOCK". Small lock icon on actions like "Read messages".
```

### Group 8: Empty and error states

#### S70 Empty states (sheet of 3)
```
SCREEN: "Empty states" — show three phone frames side by side:
1) Activity empty: faint orb outline, "Nothing yet." secondary "Your conversations will show up here."
2) Memory empty: "I don't know much about you yet." with a button "Tell me something".
3) Routines empty: "No routines." with "Create from a template" button and 3 template chips.
Same design system, generous negative space.
```

#### S71 Offline / no network
```
SCREEN: "Home – Offline".
Home layout with a slim banner under the top bar: tertiary wifi-off icon, "Offline — on-device skills and brain still work." in secondary. Status pill "● ON-DEVICE ONLY". Suggestion chips switch to offline-capable ones: "Set timer", "Flashlight", "Calculate", "Open app".
```

#### S72 Mic permission denied
```
SCREEN: "Mic blocked".
Center illustration: Core orb dimmed with a thin red slash ring.
Title: "I can't hear you."
Body: "Microphone access is off. Without it, AERIS can only work by typing."
Primary button: "Open settings". Secondary: "Use keyboard".
```

---

## 4. Refinement follow-ups (one per message)

Use these after a screen is roughly right.

**Dial it up (more sci-fi):**
- `Make the Reactor Core more detailed: add an inner hexagonal lattice, a thicker segmented ring with 36 segments, degree labels on the outer tick ring, and a stronger white-cyan bloom at the nucleus.`
- `Add leader-line data callouts around the core (thin cyan lines ending in small dots, with tiny mono labels).`
- `Frame the whole screen with four large L-shaped corner brackets and a thin tick-mark ruler along the left edge.`
- `Make every panel a chamfered HUD panel with cut corners, bright corner brackets and a small mono label tab on its top edge.`
- `Add a faint hexagonal micro-grid and scan lines to the background, at very low opacity.`

**Dial it down (keep it premium, not cluttered):**
- `Too busy: remove decorative HUD details that carry no information, keep at most 3 per screen, and add more dark space around the core.`
- `Make all colour one cyan family (#38D9FF, #167A94, #CFF6FF). Remove any purple, pink, green-neon or rainbow gradients. Amber/red/mint only for alerts.`
- `Body and conversation text must be Sora, sentence case, high contrast. Only titles use Oxanium uppercase.`
- `Reduce glow intensity by 40% so text stays sharp and readable.`

**General:**
- `Change all small labels, timestamps and numbers to JetBrains Mono uppercase 11px with wide letter-spacing.`
- `Align every element to an 8px grid with 20px side margins.`
- `Replace filled icons with thin 1.5px geometric line icons.`
- `Show this same screen with the Reactor Core in the "processing" state.`
- `Generate a variant with an amber "attention" state: the core's segmented ring turns amber and an alert callout appears.`

---

## 5. Motion spec (what Flutter will animate)

Stitch draws still frames. Every element below is animated in Flutter (see BUILD_GUIDE §12.4–12.5 for which library does what).

### 5.1 Reactor Core states

| State | Motion | Timing |
|---|---|---|
| **Boot / ignition** | Tick ring draws clockwise with a bright leading point → segments light one by one (36 × 18 ms) → lattice fades in → nucleus ignites with bloom flash → arcs start spinning → callouts slide out on leader lines | 1.6 s total, choreographed |
| **Idle** | Nucleus breathes 85→100%; arc A rotates 1 rev/40 s, arc B −1 rev/60 s; radar sweep 1 rev/8 s; a random segment flickers every 3–6 s | continuous, cheap |
| **Wake detected** | Shockwave ring bursts out, all segments flash white-cyan, haptic tick, chime, screen-edge brackets snap inward 4 px | 220 ms |
| **Listening** | Segmented ring becomes a 72-bar radial spectrum driven by the **live mic FFT**; nucleus brightness follows mic RMS; oscilloscope line below follows the waveform | 60 fps, smoothing 0.35 |
| **Processing** | Spectrum collapses; 3 arcs spin at 1.2/0.8/2 s per rev in alternating directions; particles spiral into the nucleus; callouts type themselves out (`PARSING INTENT…`) | until reply |
| **Speaking** | Shockwave rings emitted on **TTS amplitude peaks**; mirrored waveform behind the core follows the TTS signal; segments light in sequence with syllables; reply text appears word by word, synced to TTS word-boundary events | 60 fps |
| **Approval needed** | Ring segments turn amber one by one, amber callout "AUTHORISATION REQUIRED", slow amber pulse | 600 ms in, pulse 1.5 s |
| **Success** | Mint ring expands + fades, segments flash mint once | 500 ms |
| **Error** | Red glitch: core jitters 2 px for 120 ms with RGB split, one red ring | 400 ms |
| **Reduced motion** | Static frames per state, 150 ms cross-fades, no particles or glitch | — |

### 5.2 Screen-level motion

| Element | Motion |
|---|---|
| Screen entry | Panels "materialise": border draws from corner brackets outward (250 ms), then content fades up 8 px, staggered 40 ms per panel |
| Text headers | Decode/scramble effect: random glyphs resolve into the real word left to right (300–500 ms) |
| Numbers | Count up to value with mono digits (400 ms) |
| Terminal log | Lines type in at 30 chars/frame with a block cursor |
| Bottom sheet / HUD panel up | Rises with a bright scan line on its top edge sweeping left→right |
| Buttons | Press = brightness flash + 1 px inset; hover/focus = corner brackets extend |
| Background | Hex grid drifts 1 px/s; scan line passes every 6 s; haze breathes with the core |
| Navigation | Active underline slides; the core shrinks into the dock mic button on route change (shared-element "hero") |

---

## 6. Figma hand-off checklist

- [ ] Frames named with screen IDs (`X01-Voice-Listening`, `S10-Home-CommandCenter` …)
- [ ] Colour styles from §2 only (no stray hex values)
- [ ] Text styles: `hud/display-28` (Oxanium), `hud/title-18` (Oxanium), `body/16` (Sora), `body/14` (Sora), `mono/11-caps` (JetBrains Mono)
- [ ] Components: ReactorCore (9 states as variants), HudPanel (with/without tab, alert variants), HudButton (primary/outline/danger), CornerBrackets, TranscriptLine (you/AERIS), Callout (leader line), SegmentedBar, Gauge, TerminalLog, StatusStrip, CommandDock, NavBar
- [ ] Export the Reactor Core layers as **separate SVGs** (lattice, segment ring, tick ring, arcs). Flutter redraws them procedurally, but the SVGs are the visual spec
- [ ] Every screen checked at 360 px wide (small Android) as well as 412
- [ ] Contrast checked: body text ≥ 4.5:1 against the haze, even where glow sits behind it
