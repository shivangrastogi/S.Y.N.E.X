# What leaves this machine

**Generated - do not edit by hand.** Run `python gen_privacy_doc.py`.

AERIS's *brain* is local: routing, memory, the embedded Qwen and Ollama at `localhost:11434` never touch the network. Its **ears and voice are not** - and that is the honest headline this file exists to state plainly.

## Always-on remote

These send data off the machine as part of normal use. Nothing here is accidental - they are the tested Hinglish voice stack - but you should know they exist.

| Module | Goes to | What is sent | How to avoid it |
| --- | --- | --- | --- |
| `core/cloud_bridge.py` | Firebase (your project) | Phone<->laptop messages, end-to-end encrypted with AES-GCM before upload. | AERIS_DISABLE_BRIDGE=1, or simply never pair a phone. |
| `core/stt.py` | Google Speech (en-IN) | Recorded audio of what you said, on every voice turn. | Install the Vosk model — a SLEEPING mic then transcribes locally first (§6.28), and AERIS_VOICE_STREAMING=1 is Vosk end-to-end. Typed input never reaches it. |
| `core/tts.py` | Microsoft Edge TTS | The TEXT of every reply AERIS speaks aloud. | Uninstall edge_tts to fall back to pyttsx3/SAPI5, which are fully offline — at the cost of the Neerja voice. |
| `core/voice_engine.py` | Google Speech (en-IN) | Recorded audio, same as core/stt.py — this is the in-process Qt path. | Same as core/stt.py. AERIS_SPLIT_VOICE=1 moves this to core/voice_service.py. |

## Remote, only when you ask

Skills that are network services by definition. They send only what the request needs.

| Module | Goes to | What is sent | How to avoid it |
| --- | --- | --- | --- |
| `skills/diagnostics.py` | Edge TTS voice list | A voice-list request when diagnosing TTS. | - |
| `skills/dictionary.py` | dictionary API | The word you asked to define. | - |
| `skills/info_skills.py` | public info APIs | The subject of the question. | - |
| `skills/productivity_pack.py` | various web endpoints | Whatever the invoked skill needs. | - |
| `skills/sheets_sync.py` | Google Sheets | Rows you asked to sync. | Do not use the sheets skills. |
| `skills/system_health.py` | a public host (reachability probe) | Nothing about you - an empty request used to answer 'is the internet up?'. | Do not run the connectivity check. |
| `skills/system_skills.py` | a public host (reachability probe) | Nothing about you - same connectivity probe. | Do not run the connectivity check. |
| `skills/weather.py` | weather API | The city you asked about. | Do not ask for weather. |
| `skills/weather_for_city.py` | weather API | The city name you asked about. | Do not ask for weather. |
| `skills/web_search.py` | search engine | Your search query. | Do not use search skills. |
| `ui/jarvis_v31/tab_panels.py` | whatever a panel fetches | A panel-initiated fetch, only when you open and use that panel. | - |

## Local only

Loopback or LAN. Listed for completeness: importing `requests` is not the same as leaking.

| Module | Goes to | What is sent | How to avoid it |
| --- | --- | --- | --- |
| `core/health_server.py` | 127.0.0.1:8765 | A status endpoint for local tooling. | - |
| `core/lan_link.py` | your LAN | Device discovery on the local network. | - |
| `core/llm_chat.py` | 127.0.0.1:11434 (Ollama) | Prompts to a locally-running model. Never leaves the machine. | - |
| `core/phone_bridge.py` | your LAN | Direct phone<->laptop traffic on the local network. | Do not pair a phone. |
| `core/single_instance.py` | 127.0.0.1 | A port probe to detect an already-running AERIS. | - |
| `skills/windows_power_utils.py` | your own machine | Hostname/IP lookups about this computer, for the network-info skill. | - |

## Why each module is listed

- `core/cloud_bridge.py` - from firebase_admin, import firebase_admin
- `core/health_server.py` - from http
- `core/lan_link.py` - import socket
- `core/llm_chat.py` - import requests
- `core/phone_bridge.py` - from http, import socket
- `core/single_instance.py` - calls urlopen, import urllib.request
- `core/stt.py` - calls recognize_google
- `core/tts.py` - calls edge_tts.Communicate, import edge_tts
- `core/voice_engine.py` - calls recognize_google
- `skills/diagnostics.py` - import edge_tts
- `skills/dictionary.py` - calls urlopen, import urllib.request
- `skills/info_skills.py` - calls urlopen, import urllib.request
- `skills/productivity_pack.py` - calls urlopen, import requests, import urllib.request
- `skills/sheets_sync.py` - import gspread
- `skills/system_health.py` - calls urlopen, import socket, import urllib.request
- `skills/system_skills.py` - calls urlopen, import socket, import urllib.request
- `skills/weather.py` - import requests
- `skills/weather_for_city.py` - calls urlopen, import urllib.request
- `skills/web_search.py` - import requests
- `skills/windows_power_utils.py` - import socket
- `ui/jarvis_v31/tab_panels.py` - calls urlopen
