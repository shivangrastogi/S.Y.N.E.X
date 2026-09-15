# A.E.R.I.S — JARVIS v6 GUI (PyQt5)

A native PyQt5 port of the `new-latest-ui` **JARVIS v6** web design. This is a
**new, separate** GUI surface — the older `ui/jarvis_v31` and `ui/aeris_v4`
GUIs are left fully intact and still launch via `run_gui.py`.

## Launch

```bash
python run_aeris_v6.py
```

(The old GUI still runs via `python run_gui.py`.)

## Architecture

The web prototype loaded ~20 `.jsx` files via Babel; each becomes one Python
module here:

| Module | Web origin | Purpose |
|--------|-----------|---------|
| `tokens.py` | `jv3-tokens.jsx` | palette `J`, `JSTATES`, fonts, `ca()` QColor helper, QSS |
| `reactor.py` | `jv3-reactor.jsx` | `ArcReactor` — one custom-painted, 60 fps animated core |
| `widgets.py` | shared atoms | icon painter, `JTag`, `JLabel`, `Card`, `StatTile` |
| `dock.py` | `jv3-dock.jsx` | `FloatingDock` — hover-expanding left nav |
| `titlebar.py` | `jv5-app.jsx` | frameless drag bar + telemetry pills + window controls |
| `chat_panel.py` | `jv4-chat.jsx` | `MissionControlChatPanel` — AI cards, streaming, input |
| `stage.py` | `ChatView` left | reactor + state text + memory chips + HUD grid |
| `logs_bar.py` | `LogsBar` | collapsible system-log strip |
| `pages.py` | `jv5-page-*.jsx` | Home / System / Automations / Brain / Memory / Settings |
| `command_palette.py` | `jv6-command-palette.jsx` | ⌘K / Ctrl+K fuzzy launcher |
| `notifications.py` | `jv6-notifications.jsx` | proactive toast stack |
| `orb.py` | `jv6-orb.jsx` | minimized floating orb |
| `boot.py` | `jv3-boot.jsx` | optional in-window cinematic boot |
| `workers.py` | — | BrainWorker / SpeakWorker (same contract as the old GUI) |
| `app.py` | `jv5-app.jsx` | `AerisV6Window` — assembles everything + worker wiring |

## Backend wiring

The brain runs on a `QThread` via `BrainWorker` (identical contract to
`ui/jarvis_v31`): `initialize()` drives `JarvisMainEngine.setup_iter()`,
`process(text)` emits `responded(reply, meta)`. The window maps engine
activity to the four AI states (IDLE / LISTENING / PROCESSING / SPEAKING) which
recolour the reactor, titlebar pill, and chat input live. Pages read real data
(psutil, `core.automation`, `core.skill_registry`, `core.semantic_memory`).

## Not yet ported

- First-run **onboarding wizard** (`jv6-onboarding.jsx`) — boot + the rest are done.
- Live STT mic capture is stubbed to a visual LISTENING state; wire
  `VoiceWorker` (already present in `ui/jarvis_v31`) the same way the brain is.
