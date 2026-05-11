# A.E.R.I.S — New Capabilities (May 2026 build)

This sprint added 25+ new skills across web research, productivity, vision,
and system control. Everything is wired through the existing `@skill`
plugin system, so the brain auto-routes voice commands without further
configuration.

---

## 1. Web search with smart caching

**Voice triggers**

```
"search online what is python"
"tell me more about quantum computing in detail"
"define machine learning"
"ai ke baare mein vistar se batao"
```

**How it works**

- Detects depth: phrases like *"in detail / vistar se / deeply / more about"*
  switch to **deep mode** (5–7 sentence summary). Otherwise short mode (2–3
  sentences).
- Tries Wikipedia REST → DuckDuckGo (`ddgs`) → DDG HTML scrape, in that order.
- Branches on result shape: paragraph available, only links, image-heavy.
- Summarizer prefers Ollama if running; falls back to extractive TF-IDF.
- **Every successful search is cached** to `data/knowledge_cache.sqlite`
  (30-day TTL). Repeat queries answer instantly with *"Yaad hai sir, pehle
  search kiya tha…"*.

**Bonus skills**: `search_cache_stats`, `clear_search_cache`.

---

## 2. Workbook (expenses + tasks + meetings + reminders)

Single source of truth: **`data/jarvis_workbook.xlsx`** — fully styled,
opens cleanly in Excel/LibreOffice. Tabs: Dashboard · Expenses · Tasks ·
Meetings · Reminders · Category Summary · Charts.

**Voice triggers**

```
"500 rupees food pe kharch kiye"   → adds expense, auto-categorizes
"750 ka uber lagaya"
"is mahine kitna kharcha"           → speaks summary + breakdown
"add task finish report by friday urgent"
"schedule meeting with rohan tomorrow 5 pm"
"open expense sheet"                → launches Excel
"sync to google sheets"             → pushes to cloud (one-time setup)
```

**Auto-categorization**: Food & Dining, Groceries, Transport, Utilities,
Entertainment, Shopping, Health, Education, Bills & EMI, Travel, Misc.
Charts: pie (categories), bar (this vs last month), line (daily trend).

**Google Sheets sync**: drop a service-account JSON at
`data/google_credentials.json` and say *"sync to google sheets"*.

---

## 3. Vision: gestures + object recognition

Both share a single webcam multiplexer (`core/vision_engine.py`) so the
camera is opened/closed once.

### Gesture control

**Activate** with *"gesture mode on"* (or click the eye icon in the dock).

| Gesture | Action |
| --- | --- |
| **Fist** (held ~0.6 s) | Lock workstation |
| **Swipe left ←** (palm) | Alt+Shift+Tab — or Ctrl+Shift+Tab if browser focused |
| **Swipe right →** (palm) | Alt+Tab — or Ctrl+Tab if browser focused |
| **Thumbs up** | Volume + |
| **Thumbs down** | Volume − |
| **Open palm hold** (~0.9 s) | Media play / pause |

Browser detection inspects the foreground window title — Chrome, Brave,
Edge, Firefox, Opera, Vivaldi, Arc → tab cycling instead of window cycling.

### Object recognition

```
"what am I holding"        / "yeh kya hai mere haath mein"
"what do you see"          / "camera mein kya dikh raha hai"
"snap a photo"             / "selfie le lo"
```

Backed by **YOLOv8n** if `ultralytics` is installed (80 COCO classes,
~6 MB model, downloads once on first call). Falls back to MediaPipe's
EfficientDet-Lite0 if YOLO isn't available.

The "what am I holding" path ranks detections by frame-center proximity
+ area, so background clutter is down-weighted.

---

## 4. Productivity quick-skills

**Timer**

```
"5 minute ka timer lagao"
"set a 30 second timer"
"10 minute mein chai yaad dilana"
"list timers"
"cancel timer 2"     /     "cancel all timers"
```

Fires a Windows toast (via `win10toast`) when done; falls back to a system
beep. Timers persist as background threads — won't survive a JARVIS restart.

**Clipboard history**

A background watcher captures every distinct copy into
`data/clipboard_history.json` (last 50). Voice:

```
"clipboard history"           → list last 10
"copy item 3"                 → push #3 back to clipboard
"clipboard clear"
```

**Deep system health**

```
"full system health"
"network check"
```

Reports battery, CPU, RAM, disk per partition, uptime, top 3 CPU
consumers, ping latency, public IP, current WiFi SSID.

**Snip + OCR**

```
"snip and read"               → drag a region with cursor; OCR result spoken
"full screen ocr"
```

Needs `pytesseract` + the Tesseract binary
(<https://github.com/UB-Mannheim/tesseract/wiki>).

---

## 5. Code generator (foundation)

```
"jarvis write a python script that prints fibonacci"
"code likho jo csv file ko json mein convert kare"
"show generated code"
```

Calls the LLM with a code-focused prompt; saves to
`data/generated_code/<slug>_<timestamp>.<ext>`; opens in VS Code if
available, else Notepad. Languages auto-detected: python, javascript,
typescript, html, css, sql, bash, powershell.

If Ollama isn't running, drops a stub file with the spec as a comment so
you have something to iterate on manually.

---

## 6. GUI updates

Two new tabs in the floating dock (right-panel stack):

- **Vision** (eye icon) — live webcam status, gesture cheat-sheet, recent
  recognized gestures, voice trigger hints.
- **Workbook** (grid icon) — KPI tiles for this-month spend, top category,
  open tasks, cached searches; voice trigger reference; workbook path.

Both panels poll their backing engines every 800 ms / 2.5 s and stay in
sync without manual refresh.

---

## Setup / dependencies

Install everything new at once:

```
pip install ddgs beautifulsoup4 lxml openpyxl gspread google-auth ultralytics win10toast mss pytesseract Pillow
```

Some optional binaries:
- **Tesseract** (for OCR): <https://github.com/UB-Mannheim/tesseract/wiki>
- **Ollama** (for LLM-quality web summaries + code generation): <https://ollama.com>, then `ollama pull phi3:mini`
- **Google service account JSON** (for Sheets sync): drop at `data/google_credentials.json`

If a dep is missing, the matching skill self-disables with a friendly
message — the rest of AERIS keeps working.

---

## File map

```
core/
  knowledge_cache.py     SQLite cache for web searches
  summarizer.py          TF-IDF + LLM-boosted summarizer
  vision_engine.py       Shared webcam multiplexer
  gesture_engine.py      MediaPipe Hands → action dispatcher
  object_detector.py     YOLOv8n / MediaPipe object detection
skills/
  web_search.py          search + summarize + cache (3 skills)
  expense_tracker.py     workbook builder (5 skills)
  sheets_sync.py         Google Sheets push (2 skills)
  code_writer.py         LLM code generator (2 skills)
  gesture_skill.py       Voice on/off for gestures (3 skills)
  object_skill.py        "what am I holding" etc (3 skills)
  timer_skill.py         Countdown timer (3 skills)
  clipboard_history.py   Persistent clipboard tracker (3 skills)
  system_health.py       Deep system + network status (2 skills)
  snip_ocr.py            Region-OCR (2 skills)
ui/jarvis_v31/
  tab_panels.py          + VisionPanel, + WorkbookPanel
  floating_dock.py       + vision, workbook nav items + icons
data/
  jarvis_workbook.xlsx           ← lives here; the Excel home base
  knowledge_cache.sqlite         ← search cache
  generated_code/                ← LLM-generated scripts
  snapshots/, snips/             ← webcam + OCR captures
```
