# AERIS — Full Manual Testing Checklist (modules + edge cases)

A complete, tick-as-you-go test pass for the whole assistant. Organised by
subsystem, then by ability category, then a dedicated **edge-case** pass that
targets the things most likely to break (empty args, ambiguity, boundaries,
missing deps, state bleed, error handling).

**How to use**
- Say each phrase to AERIS (voice) *and* type it (text) — both paths matter.
- For each, note: ✅ correct · ⚠️ works but rough · ❌ wrong/crash.
- "Edge" rows are the important ones — they're where bugs hide.
- Legend for expected: **[does X]**, **[asks politely]** (a prompt is correct when
  the argument is genuinely missing), **[friendly error]** (never a raw traceback/crash).

---

## 0. Boot, core systems & stability

- [ ] **Cold start** — launch AERIS; window paints, no crash. Boot ≈ 20–27s.
- [ ] **2nd-prompt crash** — send 15+ commands back-to-back; no `0xC0000374` crash (split-brain).
- [ ] **Split-brain flag** — run with `AERIS_SPLIT_BRAIN=1`; confirm identical behaviour, no orphaned child process on exit.
- [ ] **GUI smoothness** — on battery (15 FPS) vs AC (30 FPS); animation still responsive while a command runs.
- [ ] **Voice stack** — Google en-IN STT hears Hinglish; edge-tts *Neerja* speaks the reply.
- [ ] **Embedded LLM** — `ask jarvis <open question>` responds locally (no internet).
- [ ] **Recovery** — kill only the GUI pid mid-run; relaunch; no corrupted data files.
- [ ] **Edge — rapid fire**: 5 commands within 2s; none dropped/swallowed.
- [ ] **Edge — empty input**: press enter with blank text → no crash, gentle nudge.
- [ ] **Edge — gibberish**: "asdkjfh qwerty" → graceful "samajh nahi aaya" (no crash, no wrong action).

## 1. 🖥️ System, Power & Diagnostics

- [ ] `cpu usage kitna hai` → **[shows CPU %]** (must be system_stats, not "kya calculate?")
- [ ] `ram usage`, `disk space kitna bacha hai`, `memory usage kya hai`
- [ ] `system info batao` → **[system stats]** (not whoami/fun_fact)
- [ ] `uptime`, `keep awake on`, `empty recycle bin`, `top process`
- [ ] `lock screen`, `mute chrome`, `unmute chrome`, `list app volumes`
- [ ] **DANGER — shutdown**: `shutdown karo`, `power off karo`, `restart karo pc`, `sleep`
      → confirm it does the RIGHT one (known issue: "shutdown karo" may hit `cancel_shutdown`; "power off" → `factorial_power`). *Verify + consider a confirm prompt before real shutdown.*
- [ ] **Edge**: `diagnose` / health check — reports degraded subsystems accurately.
- [ ] **Edge**: `cancel shutdown` when none pending → friendly "kuch scheduled nahi tha".

## 2. 🪟 Apps & Window Management

- [ ] `notepad kholo`, `chrome band karo`, `gmail kholo`
- [ ] `window minimize/maximize`, `snap left/right`, `next/prev desktop`
- [ ] **Edge — pronoun**: open notepad, then `ab isko band karo` → closes notepad (context inject).
- [ ] **Edge — WM_CLOSE**: `close_app` gracefully closes (not force-kill) a normal app.
- [ ] **Edge — not running**: `firefox band karo` when Firefox is closed → "chal nahi raha tha".
- [ ] **Edge — app vs site**: `amazon kholo` → opens app or site (NOT add_expense — guard).

## 3. 🌐 Web & Browser

- [ ] `google karo best laptops`, `youtube kholo`, `wikipedia kholo einstein`
- [ ] `web pe dhundo iphone price`, `python tutorials web pe search karo`
- [ ] **Edge**: `google` alone → opens google.com (no query).
- [ ] **Edge — leak**: `search karo` right after a slot-fill prompt → not swallowed as the previous answer.

## 4. 🎵 Media & Music

- [ ] `gaana bajao`, `arijit singh ka gaana bajao`, `koi acha gaana lagao`
- [ ] `volume badhao`, `volume kam karo`, `mute karo`, `unmute`
- [ ] **Edge — DIRECTION**: `volume tez karo` → UP (not mute); `awaaz dheemi karo` → DOWN (not up); `music start karo` → PLAY (not stop). *(These were fixed — regression-check them.)*
- [ ] **Edge — set level**: `volume 30 percent`, `brightness 75` → sets that value; `volume` alone → asks.
- [ ] **Edge — stop vs play**: `gaana band karo`/`gaana rok do` → STOP (not play).
- [ ] **Edge — boundary**: `volume 0`, `volume 100`, `volume 200` (clamp to 100).

## 5. 📋 Clipboard Superpowers

- [ ] `clipboard me kya hai`, `paste the clipboard`
- [ ] `clipboard uppercase karo`, `clipboard reverse karo`, `clipboard slug karo`
- [ ] `clipboard history dikhao`, `copy item 2`
- [ ] **Edge**: `clipboard uppercase karo` → transforms the CONTENT (not the word "clipboard").
- [ ] **Edge — empty clipboard**: transform on empty clipboard → "clipboard khaali hai".
- [ ] **Edge — no pyperclip**: friendly "pip install pyperclip" (not a crash).
- [ ] **Edge — referential**: `yeh copy karo` with a selection → copies the selection.

## 6. 📄 Documents, Files & Q&A

- [ ] `file dhundo report`, `resume kholo`, `naya folder banao ProjectX`
- [ ] `docs se batao <question>` (PDF/DOCX Q&A with citations)
- [ ] `transcribe <file>`, `compose email`
- [ ] **Edge**: `file dhundo report` → searches for "report" (doesn't ask "kaunsa file?").
- [ ] **Edge**: `open file resume` → opens/finds it; bare `file kholo` → asks.
- [ ] **Edge — missing file**: search a non-existent name → "nahi mila (N scanned)".
- [ ] **Edge — postfix Hinglish**: `productivity file kahaan hai` → file search (not currency!).

## 7. 💻 Developer Tools

- [ ] `qr code banao hello world`, `uuid generate karo`, `hash of hello`
- [ ] `base64 encode/decode <text>`, `42 to binary`, `json pretty <paste>`
- [ ] `code likho python fibonacci`, `caesar cipher <text>`
- [ ] **Edge**: `qr code banao hello world` → QR for "hello world" (doesn't ask "kya text?").
- [ ] **Edge — URL preserved**: `make qr https://Example.com/Path` → keeps case/path.
- [ ] **Edge — bad input**: `json pretty <invalid json>` → "valid JSON nahi hai" (no crash).

## 8. ✍️ Text, Writing & Language (AI)

- [ ] `grammar fix <sentence>`, `summarise <text>`, `rephrase <text>`
- [ ] `hello ko hindi me translate karo`, `namaste ka english kya hai`
- [ ] `leetspeak me likho hello`, `count characters in hello`, `reverse abcde`
- [ ] **Edge — translate reached**: `hello ko hindi me translate karo` → translates OR "install argostranslate" (NOT "kya translate karna hai?").
- [ ] **Edge — count the arg not the command**: `count characters in hello` → 5 (not counting "count/characters/in").
- [ ] **Edge — missing dep**: translate with argostranslate absent → actionable install hint.

## 9. 🧮 Math, Finance & Calculators

- [ ] `12 plus 37 kitna hai`, `18 ka 20 percent`, `150 divided by 12`
- [ ] `100 usd to inr`, `10 km me kitne mile`, `1 hour in minutes`
- [ ] `emi calculate karo 500000 10% 5 years`, `gst on 2000`, `bmi 70 kg 175 cm`
- [ ] `gcd of 48 and 36`, `is 29 prime`, `factors of 24`
- [ ] `days between 2026-01-01 and 2026-02-01`
- [ ] **Edge — plain arithmetic wins**: `12 plus 37` → `calculate` (not gcd_lcm/log_calc).
- [ ] **Edge — not a sum**: `kal 9 baje reminder`, `5 minute ka timer` → NOT calculate.
- [ ] **Edge — currency reached**: `100 usd to inr` → converts (offline snapshot), not "Format: ...".
- [ ] **Edge — date_diff reached**: proper ISO dates → computes `+N days` (not a format prompt).
- [ ] **Edge — divide by zero / huge numbers / negatives** → friendly result or message, no crash.

## 10. ⏰ Time, Productivity & Automation

- [ ] `time kya hua`, `kitne baje hain`, `aaj ki date`
- [ ] `add task write the report`, `reminder set karo doodh lene ka`, `5 minute timer`
- [ ] `daily note`, `work mode chalu karo`, `enable morning routine`
- [ ] **Edge — reminder NOT destructive**: `yaad dilana bill bharne ka` → set_reminder (NOT empty_recycle_bin/dice_roll).
- [ ] **Edge — task arg**: `add task write the report` → adds "write the report" (doesn't ask "kya task?").
- [ ] **Edge — routine name**: `enable morning routine` → enables "morning" (fake name → "nahi mili", safe).
- [ ] **Edge — weather ≠ reminder**: `mausam kaisa rahega` → weather (NOT a created reminder!).
- [ ] **Edge — time not a sum**: `kal 9 baje` doesn't get parsed as arithmetic.

## 11. 🎙️ Voice & Speech

- [ ] `speak faster/slower`, `louder`, `quieter`, `stop speaking`
- [ ] `voice memo`, `transcribe this`, `dictate`
- [ ] **Edge — Hinglish STT**: mixed "screenshot le lo AERIS" recognised correctly.
- [ ] **Edge — background noise / accent**: does STT still land the intent?
- [ ] **Edge — barge-in**: speak while Neerja is talking → does it stop/queue sensibly?
- [ ] **Edge — never swap voice**: confirm still Google en-IN + edge-tts Neerja (per your curation).

## 12. 👁️ Vision, Gestures & Screen

- [ ] `screenshot lo`, `screen ka photo lo`, `poori screen ka screenshot`
- [ ] `is page ko summarise karo`, `ye error kya hai` (screen agent OCR + LLM)
- [ ] `gesture mode on/off`, `pick color`, `what color is this`
- [ ] **Edge — ss shorthand**: `ss lelo` → screenshot (not repeat_last).
- [ ] **Edge — screen agent latency**: ~60s on CPU — shows a "processing" state, doesn't look frozen.
- [ ] **Edge — gesture engine**: confirm it does NOT freeze the GUI on construction (peek default engine).

## 13. 📱 Continuity & Phone Bridge

- [ ] `phone pair karo` (QR), `bridge on/off`, `ring my phone`, `phone battery`
- [ ] Screenshot transfer laptop↔phone; clipboard transfer.
- [ ] **Edge — E2E**: payloads AES-GCM encrypted; a wrong key fails cleanly.
- [ ] **Edge — offline phone**: command when phone unreachable → "phone offline hai" (no hang).
- [ ] **Edge — FCM push / presence routing** works when app backgrounded.

## 14. 🧠 Memory & Knowledge Graph

- [ ] `remember my favourite colour is blue`, `mera favourite colour kya hai`
- [ ] `recall mera favourite colour`, `facts about <topic>`, `brain health`
- [ ] **Edge — recall arg**: `recall mera favourite colour` → recalls it (doesn't ask "kya recall?").
- [ ] **Edge — recall ≠ store**: `mera favourite colour kya hai` (a question) does NOT store "kya".
- [ ] **Edge — empty memory**: recall on fresh memory → "memory khaali hai" (no crash).
- [ ] **Edge — vault**: `vault me github_token daalo`, `vault se github_token nikalo` → never echoes the secret (length only), fake key → "nahi mila".

## 15. 🎨 Personalization & Themes

- [ ] `set my name to Shivang`, `what's my name`, `dark theme`, `reset preferences`
- [ ] **Edge**: `what's my name` vs `who are you` → user name vs AERIS identity (don't confuse).
- [ ] **Edge**: change theme mid-run → applies live, persists after restart.

## 16. 🔧 Users, Permissions & Plugins

- [ ] `i am master`, `add master`, `face gate status`, `list plugins`, `plugin path`
- [ ] **Edge — permission gate**: a restricted action without master → politely refused.
- [ ] **Edge — plugin hot-reload**: drop a new skill file → skill_watcher registers it (k-NN needs retrain for fuzzy routing).

## 17. 📊 Quick Info, Notifications & Briefings

- [ ] `weather batao`, `aaj ka weather`, `news`, `activity digest`, `what did you do`
- [ ] `what can you do`, `kya kya kar sakte ho`, `mere jarvis mein kya hai`
- [ ] **Edge — help overview**: capability question → concise 18-category overview (not a 500-line wall).
- [ ] **Edge — help drill-down**: `system commands kya hain` / `math commands` → just that category.
- [ ] **Edge — full list**: `full list` → complete detailed catalog.
- [ ] **Edge — weather scatter**: `kal ka mausam`, `baarish hone wali hai kya` → a weather skill (not day_of_week/detect_holding).

## 18. 🎉 Fun & Casual

- [ ] `ek joke sunao`, `koi kahani sunao`, `motivate karo`, `ek pep talk do`
- [ ] `sikka uchalo`, `dice roll`, `random number`, `fortune`, `zodiac`
- [ ] **Edge — joke≠music**: `chutkula sunao yaar` → joke (not play_music!).
- [ ] **Edge — story≠time**: `bedtime story sunao` → story (not current_time/keep_awake_on).
- [ ] **Edge — pep talk ≠ wipe**: `ek pep talk do` → motivation (NEVER clears the chat!).
- [ ] **Edge — insta/success story**: `instagram story dekho` / `success story sunao` → NOT tell_story.
- [ ] **Edge — motivational story**: resolves to tell_story (story wins over the motivate cue).

---

## 19. Cross-cutting edge cases (the bug-prone stuff)

### Dead-ends (arg given but it re-asks?) — should NOT ask
- [ ] clipboard_transform, file_search, kill_process, qr_code, translate ×2, date_diff,
      recall, text_expand, currency_convert, vault_get, add_task, brightness_set,
      volume_set, routine_enable/disable, copy_history_item, open_file, create_folder.
      *Each: give the arg in one phrase → it should act, not prompt.*

### Safety guards (must NOT misfire) — should NOT do the wrong/destructive thing
- [ ] `mausam kaisa rahega` → weather, never `set_reminder` (would create a reminder!)
- [ ] `likho ye note grocery list` → create_note, never `add_expense` (junk expense!)
- [ ] `ek pep talk do` → motivate, never `clear_chat` (wipes conversation!)
- [ ] `amazon kholo` → open, never `add_expense`
- [ ] `kill firefox` → kill_process; `kill time`/`kill the lights` → NOT kill_process.

### State & concurrency
- [ ] **Slot-fill swallow**: after a "kaunsa?" prompt, the NEXT unrelated command is NOT eaten as the answer.
- [ ] **Disambiguation**: pick-one prompt → an exact new command rescues out of it.
- [ ] **Pending state**: cancel/escape mid-slot-fill returns to normal.

### Errors & missing deps (never a raw crash)
- [ ] Missing pyperclip / argostranslate / qrcode / psutil → friendly install hint.
- [ ] Invalid math/JSON/date → friendly message, not a SyntaxError/traceback leak.
- [ ] Skill breaker: a stuck skill times out (5s) and 3 failures auto-disable it 60s (not a wedge).

### Cold-boot / time-sensitive
- [ ] Fresh boot → greeting says "good morning/afternoon" (NOT "welcome back") — the `_cool` fix.
- [ ] Quiet hours (night) → proactive suggestions suppressed.

---

## 20. This-session regressions to spot-check
Confirm each still behaves after any future change:
- [ ] Routing anchors: get_time, search_web, define_word, gcd_lcm, number_properties,
      text_transform, count_chars, who_are_you, system_stats, unit(time), base_convert,
      uuid, clipboard, file_search, kill_process, joke/story/motivate, volume ×3, play_music, help.
- [ ] 8 route guards fire correctly (weather/system/screenshot/note/clear_chat/brainstorm + reminder + open-X).
- [ ] Help system: overview → category drill-down → full list.
- [ ] Categorizer: add_task/qr_code/caesar_cipher etc. in the RIGHT category.

## 21. Automated safety net (run before/after any change)
```bash
# Fast lane (unit + fast integration) — should stay green:
python -m pytest -q -m "not slow"          # ~2368 passing
# Full suite:
python -m pytest -q                         # + ~894 slow = ~3260
# Routing accuracy (end-to-end predict + guards):
python tools/validate_command_routing.py          # current ~65.5% strict / behaviourally higher
# Regenerate the command reference after skill changes:
python gen_commands_readme.py
```

> Tip: work through one category per sitting. Mark ⚠️/❌ rows and paste them back
> to me — I'll fix them. The **Edge** rows are where the real value is.
