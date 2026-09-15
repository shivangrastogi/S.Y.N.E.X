# AERIS skill catalog

_Auto-generated from the live skill registry on 2026-05-25T07:13:28._

**334 skills across 18 categories.**

To regenerate: `regenerate skill docs` (voice) or `python -c "from core.docs_gen import write_skill_docs; write_skill_docs()"`.

## Apps  (3)

| Skill | Example trigger | Description |
|---|---|---|
| `open_explorer_here` | `open explorer` | Open File Explorer at the project root |
| `open_file` | `X file kholo` | Search Documents/Downloads/Desktop/Pictures for a file by name and open it |
| `open_in_browser` | `open youtube in brave` | Open a website or search a topic in a specific browser (and optionally a specific profile). |

## Audio  (3)

| Skill | Example trigger | Description |
|---|---|---|
| `brightness_set` | `brightness 50` | Set screen brightness to an absolute percentage |
| `volume_mute` | `mute` | Mute or unmute system audio |
| `volume_set` | `volume 50` | Set system volume to an absolute percentage |

## Clipboard  (1)

| Skill | Example trigger | Description |
|---|---|---|
| `clipboard_paste` | `clipboard mein kya hai` | Read the current clipboard contents |

## Conversational  (2)

| Skill | Example trigger | Description |
|---|---|---|
| `clear_chat` | `clear chat` | Acknowledge a clear-chat request. The UI listens for this and wipes the chat history pane. |
| `greeting` | `hello` | Acknowledge a wake/hello with a time-of-day greeting. |

## Extensibility  (9)

| Skill | Example trigger | Description |
|---|---|---|
| `chain_path` | `chain path` | Print the chains.json absolute path so it can be edited. |
| `chains_list` | `chains list` | List every defined chain (trigger + step count). |
| `chains_on` | `chains on` | Activate the cross-skill chain engine — fires follow-up skills automatically when configured triggers happen. |
| `chains_reload` | `reload chains` | Reload data/chains.json after editing. |
| `plugin_disable` | `disable plugin` | Disable a plugin (won't load on next restart). |
| `plugin_enable` | `enable plugin` | Enable a plugin by name (also loads it now if possible). |
| `plugin_list` | `list plugins` | List discovered AERIS plugins under data/plugins/. |
| `plugin_load_all` | `load all plugins` | Load every enabled plugin (idempotent). |
| `plugin_path` | `plugin path` | Print the plugins folder absolute path. |

## Faces / Permissions  (8)

| Skill | Example trigger | Description |
|---|---|---|
| `face_gate_status` | `face gate status` | Explain whether the face gate is open/closed and the last-seen status. |
| `master_allow_all` | `allow all gestures for` | Grant a master full access to every gesture. |
| `master_block` | `block gesture` | Block a specific gesture for a master (removes from their allowlist). |
| `master_grant` | `grant gesture` | Grant a specific gesture to a master (adds to their allowlist). |
| `master_kid_mode` | `kid mode for` | Restrict a master to a small set of safe gestures (no lock screen, no volume control, no app-switch). |
| `master_permissions_clear` | `clear master permissions` | Wipe per-master gesture permissions (everyone reverts to allow-all). |
| `master_permissions_show` | `master permissions` | Show the per-master gesture allowlist. |
| `register_face` | `register my face` | Enroll a face from the current camera frame under a name. Pre-requisite for marking that name as a master. |

## Gestures  (15)

| Skill | Example trigger | Description |
|---|---|---|
| `gesture_bind` | `bind gesture` | Rebind a gesture to a registered skill name (e.g. 'bind peace to screenshot_full'). |
| `gesture_bindings` | `list gesture bindings` | List every custom gesture binding currently in effect. |
| `gesture_list_custom` | `list custom gestures` | List all trained custom gestures. |
| `gesture_record` | `record gesture` | Record a new custom gesture under a name — hold the pose until AERIS confirms it's saved. |
| `gesture_record_status` | `gesture record status` | Report whether a custom-gesture recording is in progress. |
| `gesture_sensitivity_set` | `gesture sensitivity` | Set the gesture engine sensitivity — very_sensitive / sensitive / normal / relaxed / very_relaxed. |
| `gesture_sensitivity_status` | `gesture sensitivity status` | Report the current gesture sensitivity level + multiplier. |
| `gesture_stats` | `gesture stats` | Aggregate gesture trace counts by name + face for the last hour. |
| `gesture_trace` | `gesture trace` | Show the last 10 gesture events (fires + blocks). |
| `gesture_trace_clear` | `clear gesture trace` | Wipe the gesture trace log. |
| `gesture_unbind` | `unbind gesture` | Remove a gesture binding override — revert to the built-in action. |
| `gesture_unteach` | `unteach gesture` | Forget a previously-trained custom gesture. |
| `practice_gesture` | `practice gesture` | Start a focused practice session for one gesture — counts hits over a window (default 30 s). |
| `practice_status` | `practice status` | Report current gesture-practice session stats. |
| `practice_stop` | `practice stop` | Stop the current gesture-practice session and return stats. |

## Memory  (1)

| Skill | Example trigger | Description |
|---|---|---|
| `vault_get` | `vault get` | Decrypt a vault secret and copy it to the clipboard (never to chat log) |

## Other  (194)

| Skill | Example trigger | Description |
|---|---|---|
| `add_expense` | `spent 500 on food` | Log a new expense (amount + description) into the local workbook with auto category. |
| `add_master` | `add master` | Add an already-registered face to the master_users list. |
| `add_meeting` | `schedule meeting with rohan tomorrow 5 pm` | Add a meeting entry to the Meetings tab. |
| `add_task` | `add task write the report` | Add a personal task to the Tasks tab with priority + due date. |
| `antonyms` | `antonyms of` | List antonyms (opposite-meaning words) for a word. |
| `app_mute` | `mute chrome` | Mute a specific application's audio (e.g. 'mute chrome'). |
| `app_unmute` | `unmute chrome` | Unmute a specific application's audio. |
| `app_volume_list` | `list app volumes` | List every app currently producing audio with its volume %. |
| `app_volume_set` | `set spotify to` | Set the per-app volume percentage (e.g. 'set spotify to 30%'). |
| `append_note` | `note this` | Append a quick note to data/scratch.md with a timestamp |
| `ask_jarvis` | `ask jarvis` | Free-form chat with the local LLM — model may auto-fire any registered AERIS skill to satisfy the request. |
| `auto_label_off` | `auto label off` | Stop auto object labeling. |
| `auto_label_on` | `auto label on` | Start auto object labeling — narrate items held up to the camera. |
| `auto_label_speak_off` | `stop speaking labels` | Stop speaking auto-label results (chat/log entries continue). |
| `auto_label_speak_on` | `speak labels` | Make auto-label speak each new object's name out loud. |
| `auto_label_status` | `auto label status` | Report whether auto-labeling is running and what was seen recently. |
| `base64_decode` | `base64 decode` | Base64-decode the clipboard (or given text) |
| `base64_encode` | `base64 encode` | Base64-encode the clipboard (or given text) |
| `brightness_down` | `dimmer` | Decrease screen brightness by ~10% |
| `brightness_up` | `brighter` | Increase screen brightness by ~10% |
| `cancel_lock` | `cancel lock` | Cancel a pending scheduled lock (from lock_after). |
| `cancel_timer` | `cancel timer` | Cancel an active timer by id, or all if 'all' is given. |
| `clear_search_cache` | `clear search cache` | Clear the local web-search knowledge cache. |
| `click_text` | `X pe click karo` | Find a piece of text on the screen and click its center |
| `clipboard_clear` | `clipboard clear` | Wipe stored clipboard history. |
| `clipboard_copy` | `yeh copy karo` | Copy a piece of text to the system clipboard |
| `clipboard_history` | `clipboard history` | Show the most recent clipboard items captured by the background watcher. |
| `clipboard_open_url` | `open clipboard url` | Open the URL currently in clipboard in the default browser. |
| `clipboard_say` | `say clipboard` | Speak the current clipboard text aloud (truncated to ~400 chars). |
| `clipboard_stats` | `clipboard size` | Quick stats about the current clipboard (chars, words, lines). |
| `clipboard_transform` | `uppercase clipboard` | Transform clipboard contents (upper/lower/slug/json/strip/reverse) |
| `compose_email` | `compose email` | Open an Outlook draft window pre-filled with recipient / subject / body parsed from your voice. Does NOT send. |
| `conversation_clear` | `clear conversation memory` | Wipe the rolling ConversationHistory buffer (does NOT clear the chat panel — see clear_chat for that). |
| `conversation_recap` | `recap` | Repeat the last N user/assistant exchanges so you remember what was just discussed. |
| `copy_history_item` | `copy item 1` | Push a previous clipboard entry back to the clipboard by index. |
| `create_folder` | `naya folder banao X` | Create a new folder by path or simple name (under Documents by default) |
| `daily_briefing` | `good morning` | Speak a quick personalized briefing: greeting, weather, tasks, expenses, system status. |
| `define_word` | `define` | Look up a word's definition (dictionaryapi.dev). |
| `delete_last_memo` | `delete last memo` | Delete the most recently recorded voice memo. |
| `dep_check` | `dep check` | Report every optional dependency + which skills go dark when it's missing. |
| `dep_skills_dark` | `dark skills` | List skills that are currently broken because of a missing optional dependency. |
| `detect_holding` | `what am I holding` | Look at the webcam and identify what the user is holding. |
| `detect_scene` | `what do you see` | Describe what the webcam currently sees. |
| `email_draft_blank` | `blank email` | Open an empty Outlook draft window. |
| `file_search` | `find file` | Search recent user files by substring (case-insensitive) |
| `find_file` | `find file` | Fuzzy-search the user's common folders for a filename, show top matches and open the best one. |
| `focus_deep_off` | `deep focus off` | Exit DEEP focus mode — restore apps + clear DND |
| `focus_deep_on` | `deep focus on` | Enter DEEP focus mode — close distracting apps + Windows DND |
| `focus_deep_status` | `deep focus status` | Report whether DEEP focus mode is currently on |
| `forget_command` | `forget command` | Remove a user-taught phrase (or all phrases for an intent) |
| `full_screen_ocr` | `full screen ocr` | OCR the entire current screen and return the text. |
| `full_system_health` | `full system health` | Deep system check: battery, CPU, RAM, disk, uptime, top processes, network ping, WiFi SSID. |
| `get_preference` | `what's my name` | Read back a saved preference (name/city/browser/voice/etc.). |
| `git_branch` | `git branch` | Current git branch + commit-ahead/behind summary |
| `git_commit_quick` | `git commit` | Commit currently-staged changes with a message taken from the spoken text. |
| `git_diff` | `git diff` | Short stat of uncommitted changes (lines added/removed per file). |
| `git_log` | `git log` | Last 10 commits of the project repo (short hash + subject + relative date). |
| `git_pull` | `git pull` | git pull --ff-only — fast-forward only, won't create merge commits. |
| `git_status` | `git status` | Short git status of the AERIS project root |
| `google_jump` | `google` | Open Google search for the spoken query (or google.com if blank). |
| `gpu_offload_off` | `gpu off` | Revert heavy ML models to CPU on next reload. |
| `gpu_offload_on` | `gpu on` | Switch heavy ML models (encoder / YOLO / InsightFace) to GPU on next reload — persists across restarts. |
| `gpu_status` | `gpu status` | Report GPU offload preference + CUDA availability. |
| `hash_text` | `hash` | SHA-256 hash of clipboard (or given text) |
| `help_catalog` | `help` | List every available skill with one example trigger phrase per skill. |
| `i_am_master` | `i am master` | Register the current face as a new master user and add them to the master_users list in one shot. |
| `image_to_clipboard` | `copy image to clipboard` | Copy an image (path or fuzzy name from ~/Pictures) to clipboard. |
| `journal_path` | `journal path` | Print the journal file path so it can be opened in an editor. |
| `journal_show` | `show journal` | Read back the last 10 journal entries. |
| `kg_facts_about` | `facts about` | List every stored fact about a subject. |
| `kg_forget` | `forget about` | Forget every stored fact about a subject. |
| `kg_list` | `list knowledge` | List every stored knowledge-graph triple. |
| `kg_query` | `who is` | Ask the knowledge graph a question — 'who is X', 'where do I live', 'what's my Y'. |
| `kg_remember` | `remember that` | Save a fact into the knowledge graph (e.g. 'remember that Sara is my sister'). |
| `kill_process` | `kill process` | Terminate a process by name (e.g. 'firefox', 'discord') |
| `last_notification` | `last notification` | Describe the most recent Windows toast notification. |
| `last_screenshot_to_clipboard` | `copy last screenshot` | Copy the most-recent AERIS screenshot to clipboard as image. |
| `list_browser_profiles` | `list chrome profiles` | List profiles configured in Chrome / Edge / Brave. |
| `list_generated_code` | `show generated code` | List recently generated code snippets. |
| `list_macros` | `list macros` | List every macro saved in data/macros.json. |
| `list_masters` | `list masters` | List every user marked as master (allowed to drive gestures). |
| `list_taught` | `list taught` | Show every user-taught phrase |
| `list_timers` | `list timers` | List all active timers. |
| `list_voice_memos` | `list memos` | List the most recent voice memos with timestamps. |
| `llm_status` | `llm status` | Report local-LLM health — model, reachable state, tool count. |
| `lock_after` | `lock after` | Schedule a lock-screen N minutes from now (default 5 min). Replaces any previously scheduled lock. |
| `lock_status` | `lock status` | Report how long until the scheduled lock fires. |
| `maps_jump` | `maps` | Open Google Maps for the spoken location or directions. |
| `monitor_list` | `list monitors` | List all physical monitors with their virtual-screen rectangles. |
| `monitor_swap` | `monitor swap` | Move the active window to the next physical monitor. |
| `month_summary` | `is mahine kitna kharcha` | Speak the current month's spending breakdown. |
| `mood_today` | `mood today` | Average sentiment of recent user messages (positive/negative trend) |
| `news_briefing` | `aaj ki news batao` | Fetch latest headlines and summarize them in Hinglish (categories: tech, india, business, world) |
| `next_meeting` | `next meeting` | Show the next upcoming Outlook appointment. |
| `note_append` | `log` | Append a timestamped line to the rolling journal (data/notes/journal.md). |
| `ocr_screen` | `ocr screen` | Read the text currently on screen (full virtual screen OCR) |
| `password_generate` | `generate password` | Generate a strong random password (default 20 chars, mixed) |
| `path_to_clipboard` | `copy path` | Copy the project root path to the clipboard |
| `play_last_memo` | `play last memo` | Play the most recently recorded voice memo. |
| `play_memo` | `play memo` | Play a memo by partial filename match (e.g. timestamp prefix). |
| `pomodoro_start` | `start pomodoro` | Start a Pomodoro session (default 25-min work + 5-min breaks; long 15-min break every 4th cycle). |
| `pomodoro_status` | `pomodoro status` | Report current pomodoro phase + time remaining. |
| `pomodoro_stop` | `stop pomodoro` | Stop the current pomodoro session. |
| `privacy_mode_off` | `privacy mode off` | Disable privacy mode (does NOT auto-resume subsystems — you re-enable what you want). |
| `privacy_mode_on` | `privacy mode on` | Hard 'stop listening' — disables wake-word + STT + gesture engine + camera + auto-label + notification mirror. |
| `privacy_mode_status` | `privacy mode status` | Report privacy mode state + per-subsystem on/off. |
| `profile_bind` | `in code bind` | Bind a gesture to a skill ONLY when a specific app is in foreground (e.g. 'in code bind peace to git_status'). |
| `profile_clear` | `clear profiles` | Wipe all per-app gesture profile overrides. |
| `profile_list` | `list profiles` | List every per-app gesture profile override. |
| `profile_unbind` | `in code unbind` | Remove a per-app gesture override. |
| `qr_code` | `qr code` | Generate a QR code for a URL or text (saves PNG + opens it) |
| `quick_calc` | `calculate` | Evaluate a math expression spoken in English / Hinglish. |
| `quick_math` | `math` | Evaluate a math expression (+ - * / ** sqrt sin pi etc.) |
| `quick_timer` | `5 minute timer` | Set a timer — '5 minute timer', '10 min timer', '30 minute pomodoro' |
| `read_screen` | `screen padho` | OCR the visible screen and return all extracted text |
| `real_weather` | `real weather batao` | Live weather for a city (defaults to user's stored location or Delhi) |
| `recall` | `recall` | Recall past conversations semantically (by meaning, not keyword) |
| `recent_files` | `recent files` | List the 10 most recently modified files across Documents, Downloads, Desktop, Pictures. |
| `record_voice_memo` | `record voice memo` | Record a short voice memo via the mic (default 10s, max 120s). Saved as WAV under data/notes/audio/. |
| `regenerate_skill_docs` | `regenerate skill docs` | Regenerate docs/SKILLS.md from the live skill registry. |
| `reload_macros` | `reload macros` | Reload macros from disk (after editing data/macros.json). |
| `remove_master` | `remove master` | Remove a name from the master_users list. |
| `repeat_last` | `repeat` | Re-execute the previous user command (skips this 'repeat' trigger itself). |
| `reset_preferences` | `reset preferences` | Restore all preferences to their default values. |
| `restart_explorer` | `restart explorer` | Restart explorer.exe (taskbar / desktop refresh) |
| `reveal_in_explorer` | `downloads kholo` | Open File Explorer at a common location |
| `routine_disable` | `disable morning routine` | Disable a routine so its trigger no longer fires |
| `routine_enable` | `enable morning routine` | Enable a routine so its trigger fires it |
| `routine_list` | `list routines` | List all automation routines and their current state |
| `routine_reload` | `reload routines` | Re-read data/routines.json from disk (after editing it manually) |
| `routine_run` | `run morning routine` | Run a routine right now by name (bypasses its trigger) |
| `routine_status` | `routine status` | Show the current state of a specific routine |
| `run_macro` | `run macro` | Execute a saved macro from data/macros.json (a chain of skills). |
| `scratchpad_summarize` | `summarize scratch` | Summarise data/scratch.md into 3 bullets via the brain |
| `screen_color_pick` | `pick color` | Read the pixel under the cursor and copy hex to clipboard |
| `screenshot_full` | `screenshot` | Capture the entire desktop (all monitors) to Pictures/AERIS/. |
| `screenshot_window` | `screenshot window` | Capture just the active window (focused app) to Pictures/AERIS/. |
| `screenshots_folder` | `open screenshots folder` | Open the folder where AERIS saves screenshots (Pictures/AERIS). |
| `search_cache_stats` | `search cache stats` | Show how many web searches are cached locally and the most recent ones. |
| `search_in_browser` | `search ai in brave` | Search Google for a query in a specific browser (and optionally a specific profile). |
| `send_whatsapp` | `whatsapp pe X ko bolo Y` | Send a WhatsApp message to a saved contact (resolves name → phone via data/contacts.json) |
| `set_default_browser` | `set default browser brave` | Set the assistant's preferred browser for searches and URL opens. |
| `set_default_profile` | `set default chrome profile 1` | Remember a default Chrome / Edge / Brave profile so AERIS stops asking. |
| `set_preference` | `set my name to Shivang` | Save a user preference (name/city/browser/voice/etc.) to settings.json. |
| `set_timer` | `set a 5 minute timer` | Set a countdown timer that fires a desktop toast/beep. |
| `settings_schema_migrate` | `migrate settings` | Run pending settings.json migrations + fill any missing default keys. Idempotent — safe to call repeatedly. |
| `settings_schema_status` | `settings schema status` | Report current settings schema version + whether a migration is pending. |
| `sheets_status` | `sheets sync status` | Show whether Google Sheets sync is configured and where the synced sheet lives. |
| `show_desktop` | `show desktop` | Minimize all windows (Win+D) |
| `smart_paste` | `smart paste` | Reformat the current clipboard content: JSON → pretty, URL → page title, long text → summary, code → de-indent. |
| `snip_and_ocr` | `snip and read` | Select a screen region and read the text inside it (OCR). |
| `spotify_next` | `agla gaana chalao` | Skip to next Spotify track |
| `spotify_pause` | `spotify pause karo` | Pause Spotify playback on the active device |
| `spotify_play_track` | `spotify pe X chala do` | Search Spotify for a specific track and start playback on the active device |
| `start_calibration_wizard` | `start calibration` | Launch the gesture calibration wizard — walks you through each gesture with live detection feedback. |
| `stop_voice_memo` | `stop voice memo` | Stop an in-progress voice memo recording. |
| `stt_prefer_google` | `use google for stt` | Mark Google as the preferred STT backend (default). |
| `stt_prefer_whisper` | `use whisper for stt` | Mark Whisper as the preferred STT backend in settings. |
| `summarize_window` | `summarize window` | Copy the active app's name and window title to clipboard. |
| `synonyms` | `synonyms of` | List synonyms for a word. |
| `tab_close` | `close tab` | Close the current browser tab (Ctrl+W). |
| `tab_new` | `new tab` | Open a new browser tab (Ctrl+T). |
| `tab_next` | `next tab` | Switch to the next browser tab (Ctrl+Tab). |
| `tab_prev` | `previous tab` | Switch to the previous browser tab (Ctrl+Shift+Tab). |
| `tab_reopen` | `reopen tab` | Reopen the last closed tab (Ctrl+Shift+T). |
| `tab_switch` | `tab 1` | Jump to a numbered browser tab (Ctrl+1..9). Accepts digits, ordinal words (first / third / last), and Hinglish (pehla / dusra). |
| `teach_command` | `from now on 'open ide' means open_app` | Teach AERIS a new utterance for an existing intent or skill |
| `text_expand` | `expand sig` | Expand a snippet trigger to its full text on the clipboard |
| `text_expand_add` | `add snippet` | Add or update a snippet: 'add snippet trig=value text' |
| `text_expand_list` | `list snippets` | List every available snippet trigger |
| `this_week_meetings` | `this week meetings` | List appointments in the next 7 days. |
| `todays_meetings` | `todays meetings` | List every appointment on today's calendar. |
| `todo_today` | `todo today` | Show unticked TODO lines from data/scratch.md (last 7 days) |
| `vault_delete` | `vault delete` | Remove a secret from the vault |
| `vault_list` | `vault list` | List all stored secret names (values never returned) |
| `vault_store` | `vault store` | Encrypt + store a secret in the Windows DPAPI vault |
| `volume_down` | `volume down` | Decrease system volume by ~10% |
| `volume_up` | `volume up` | Increase system volume by ~10% |
| `wallpaper_set` | `set wallpaper` | Set the Windows desktop wallpaper from a file path or a fuzzy name (looks under Pictures). |
| `weather_for_city` | `weather in` | Weather + today's forecast for a named city (Open-Meteo). |
| `what_does_gesture_do` | `what does peace do` | Describe the effective action for a gesture (override if set, else built-in default). |
| `whisper_set_model` | `set whisper model` | Switch Whisper model size — tiny/base/small/medium/large-v3. |
| `whisper_status` | `whisper status` | Report Whisper STT availability and current model size. |
| `whisper_transcribe_once` | `whisper transcribe` | Record ~4 seconds of audio and transcribe via Whisper. |
| `whoami_info` | `whoami` | Quick identity: username, hostname, local IP, OS, uptime. |
| `wikipedia_jump` | `wikipedia` | Open Wikipedia article for the spoken topic. |
| `window_pin_top` | `pin window` | Make the foreground window always-on-top (Win32 HWND_TOPMOST). |
| `window_snap_bottom` | `snap bottom` | Snap the active window to the bottom half of its monitor |
| `window_snap_left` | `snap left` | Snap the active window to the left half of its monitor |
| `window_snap_right` | `snap right` | Snap the active window to the right half of its monitor |
| `window_snap_top` | `snap top` | Snap the active window to the top half of its monitor |
| `window_unpin_top` | `unpin window` | Remove always-on-top from the foreground window. |
| `write_code` | `write me a python script that scrapes a website` | Generate a code snippet/script from a natural-language spec, save it under data/generated_code/, and open it in an editor. |
| `youtube_jump` | `youtube` | Open YouTube search results for the spoken query. |

## Productivity  (18)

| Skill | Example trigger | Description |
|---|---|---|
| `doc_clear` | `doc clear` | Wipe the document-QA index. |
| `doc_index_folder` | `index folder` | Walk a folder + embed every text file into the doc-QA index. |
| `doc_query` | `doc query` | Search the indexed documents for a query — returns top matching files + chunk indices. |
| `doc_status` | `doc status` | Report current doc-QA index size + indexed folder. |
| `focus_mode_off` | `focus mode off` | Exit focus mode and cancel the pomodoro. |
| `focus_mode_on` | `focus mode on` | Enter focus mode: close distracting apps, open work apps, start a pomodoro. |
| `open_workbook` | `open expense sheet` | Open the local jarvis workbook (expenses, tasks, meetings) in Excel. |
| `sync_default_path` | `sync default path` | Print the path the next sync export will write to. |
| `sync_export` | `sync export` | Pack all AERIS customisations (settings, custom gestures, voice ID, knowledge graph, macros, chains, faces) into a ZIP under ~/Documents (or a custom path). |
| `sync_import` | `sync import` | Restore AERIS customisations from a sync ZIP. |
| `sync_list` | `sync list` | List every file that the next sync export would pack. |
| `sync_to_sheets` | `sync to google sheets` | Upload the local AERIS workbook to Google Sheets. |
| `translate_clipboard` | `translate clipboard` | Translate the current clipboard contents into a target language (default English). |
| `translate_jump` | `translate` | Open Google Translate (with the spoken phrase pre-filled if any). |
| `translate_status` | `translate status` | Report which translation backends (LLM / argos / Google URL) are reachable. |
| `translate_to` | `translate this to` | Translate text into a target language. Format: 'translate <text> to <language>'. |
| `translate_to_english` | `english mein translate karo X` | Translate a Hindi or Hinglish phrase into English |
| `translate_to_hindi` | `hindi mein translate karo X` | Translate an English phrase into Hindi |

## Quick info  (6)

| Skill | Example trigger | Description |
|---|---|---|
| `battery_status` | `battery` | Battery percentage, plugged-in state, estimated time left. |
| `currency_convert` | `convert currency` | Convert between currencies (e.g. '100 usd to inr') |
| `current_date` | `what's the date` | Speak today's date and weekday. |
| `current_time` | `what's the time` | Speak the wall-clock time (24h + AM/PM). |
| `date_diff` | `days between` | Days between two dates ('days between 2026-01-01 and today') |
| `weather_local` | `weather` | Current weather + today's forecast (open-meteo, no API key) |

## System  (21)

| Skill | Example trigger | Description |
|---|---|---|
| `cancel_shutdown` | `cancel shutdown` | Abort a pending shutdown |
| `cpu_info` | `cpu info` | CPU model, core count, current frequency |
| `diagnostics` | `diagnose` | Full health check — probe TTS, gesture, vision, brain subsystems and report each as OK/MISSING with a fix hint. |
| `lock_screen` | `lock screen` | Lock the workstation (Win+L equivalent) |
| `memory_stats` | `memory stats` | Show semantic-memory size (records / embedded / queue) |
| `network_check` | `network check karo` | Quick network status: ping, public IP, WiFi name. |
| `network_status` | `network status` | Local IP, WiFi SSID, public IP |
| `notification_mirror_off` | `stop reading notifications` | Stop reading Windows toasts aloud. |
| `notification_mirror_on` | `read my notifications` | Read each new Windows toast notification aloud via TTS. |
| `notification_mirror_status` | `notification mirror status` | Report whether notification mirror is on / available. |
| `phone_pair_off` | `phone pair off` | Stop the phone-bridge HTTP server. |
| `phone_pair_on` | `phone pair on` | Start the LAN phone-bridge HTTP server so a phone browser on the same WiFi can fire AERIS skills. |
| `phone_pair_url` | `phone pair url` | Show the phone-bridge URL + access token. |
| `ping` | `ping` | Ping a host and report round-trip time |
| `presence_auto_pause_off` | `presence auto pause off` | Disable the camera-presence auto-pause for gestures. |
| `presence_auto_pause_on` | `presence auto pause on` | Auto-pause the gesture engine when you walk away from the camera and resume when you return. |
| `presence_status` | `presence status` | Report whether AERIS currently sees a user in front of the camera. |
| `restart_pc` | `restart pc` | Schedule a restart in 60 s (can be cancelled) |
| `shutdown_pc` | `shutdown` | Schedule a shutdown in 60 s (can be cancelled) |
| `sleep_pc` | `sleep pc` | Put the PC to sleep (S3 standby) |
| `system_stats` | `system stats` | Snapshot of CPU, RAM, disk, uptime |

## Telemetry  (8)

| Skill | Example trigger | Description |
|---|---|---|
| `log_digest_today` | `summarize logs` | Summarize today's data/logs/aeris.log entries by category. |
| `telemetry_digest` | `telemetry digest` | Print a text digest of usage stats (gestures, skills, memos, journal, KG, faces) over the last hour. |
| `workspace_clear` | `workspace clear` | Wipe the workspace tracker's rolling event buffer. |
| `workspace_recent` | `workspace recent` | Show the last 10 foreground-app switches. |
| `workspace_summary` | `workspace summary` | Summarise the last hour of foreground app usage. |
| `workspace_summary_today` | `workspace summary today` | Summarise the last 24 hours of app usage. |
| `workspace_track_off` | `workspace track off` | Stop the workspace tracker (keeps buffered events). |
| `workspace_track_on` | `workspace track on` | Start the autonomous workspace tracker (polls foreground app every 30 s, builds a usage timeline). |

## UI  (21)

| Skill | Example trigger | Description |
|---|---|---|
| `ar_overlay_off` | `ar overlay off` | Hide the AR camera overlay. |
| `ar_overlay_on` | `ar overlay on` | Show the AR camera overlay — translucent always-on-top live preview with YOLO bounding boxes. |
| `ar_overlay_status` | `ar overlay status` | Report whether the AR overlay is currently shown. |
| `hud_move` | `hud move` | Move the HUD to a named corner. |
| `hud_off` | `hud off` | Hide the heads-up overlay. |
| `hud_on` | `hud on` | Show the always-on-top AERIS heads-up overlay. |
| `hud_status` | `hud status` | Report whether the HUD is currently visible. |
| `open_command_palette` | `open command palette` | Open the AERIS command palette — fuzzy-search every skill. |
| `open_first_run_wizard` | `first run wizard` | Open the AERIS first-run setup wizard — guides through face enrollment + voice + theme + diagnostics. |
| `open_permissions_editor` | `open permissions editor` | Open the masters × gestures permissions matrix — edit every per-user gesture allowance in one grid. |
| `open_settings_panel` | `open settings panel` | Open the AERIS settings dialog — edit voice, gestures, masters, browser without touching settings.json. |
| `open_telemetry_dashboard` | `open telemetry` | Open the AERIS telemetry dashboard — usage stats for gestures, skills, workspace, memory. |
| `theme_cyber` | `cyber theme` | Switch the AERIS UI to the cyber (neon-on-black) theme. |
| `theme_cycle` | `cycle theme` | Rotate to the next available theme. |
| `theme_dark` | `dark theme` | Switch the AERIS UI to the dark theme. |
| `theme_light` | `light theme` | Switch the AERIS UI to the light theme. |
| `theme_status` | `theme status` | Report the current theme + available options. |
| `transcript_log` | `transcript log` | Print the last 10 STT events from the transcript bus. |
| `transcript_off` | `transcript off` | Close the live transcript pane. |
| `transcript_on` | `transcript on` | Open the live STT transcript pane — see your speech and AERIS replies stream in real-time. |
| `transcript_status` | `transcript status` | Report whether the transcript pane is visible. |

## Vision  (6)

| Skill | Example trigger | Description |
|---|---|---|
| `cursor_mode_off` | `cursor mode off` | Stop the air-cursor (gesture engine stays on for other gestures). |
| `cursor_mode_on` | `cursor mode on` | Turn your index finger into a mouse — pinch = left click. |
| `gesture_mode_off` | `gesture mode off` | Stop the gesture controller and release the camera. |
| `gesture_mode_on` | `gesture mode on` | Activate hand-gesture control — sequenced, collision-free gestures for hands-free desktop control. |
| `gesture_status` | `gesture status` | Report whether gesture control is currently active. |
| `snap_and_save` | `snap a photo` | Grab a webcam frame and save it to data/snapshots/. |

## Voice / STT  (14)

| Skill | Example trigger | Description |
|---|---|---|
| `speaker_enroll` | `enroll my voice` | Record 4 seconds of your voice and store a speaker signature for future identification. |
| `speaker_forget` | `forget speaker` | Remove an enrolled speaker from the voice-ID registry. |
| `speaker_identify` | `identify speaker` | Listen for 2 s and identify the loudest enrolled speaker. |
| `speaker_list` | `list speakers` | List every enrolled speaker. |
| `tts_voice_list` | `list voices` | List the curated TTS voice aliases. |
| `tts_voice_reset` | `reset tts voice` | Revert the TTS voice (language/accent) to the AERIS default (en-IN-NeerjaNeural). Note: separate from 'voice reset' which restores rate+volume. |
| `tts_voice_set` | `set voice to` | Switch the TTS voice. Accepts aliases (hindi/indian male/american female/etc.) or raw Edge-TTS neural names. |
| `tts_voice_status` | `tts voice status` | Report the currently selected TTS voice (language/accent). For rate+volume use 'voice status'. |
| `voice_faster` | `speak faster` | Speed up the TTS voice by one step (~25 wpm). |
| `voice_louder` | `speak louder` | Increase TTS voice volume by one step. |
| `voice_reset` | `reset voice` | Restore TTS voice rate and volume to defaults (175 wpm, 100%). |
| `voice_slower` | `speak slower` | Slow down the TTS voice by one step (~25 wpm). |
| `voice_softer` | `speak softer` | Decrease TTS voice volume by one step. |
| `voice_status` | `voice status` | Report current TTS voice rate + volume. |

## Web  (1)

| Skill | Example trigger | Description |
|---|---|---|
| `web_search` | `search online` | Search the web online, summarize the top results in Hinglish, and cache the answer locally for instant recall later. |

## Windows  (3)

| Skill | Example trigger | Description |
|---|---|---|
| `window_close` | `close window` | Close the active window (sends WM_CLOSE) |
| `window_maximize` | `maximize window` | Maximize the active window |
| `window_minimize` | `minimize window` | Minimize the active window |
