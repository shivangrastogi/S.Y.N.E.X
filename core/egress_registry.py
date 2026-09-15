"""What actually leaves this machine (§6.38).

P4 asks for "everything local, per-user model, encrypted memory". `CLAUDE.md`
opens with "local inference … no cloud brain". Both are true about the *brain* —
routing, memory, the embedded Qwen and Ollama at `localhost:11434` never touch
the network. Neither is true about the assistant as a whole, and the gap is not
small:

* **every spoken utterance** goes to Google (`recognize_google`, en-IN);
* **every spoken reply** goes to Microsoft (`edge_tts`).

Those are deliberate, hand-picked choices — they are the tested Hinglish stack
and swapping them is explicitly out of bounds. The problem was never the
choice; it was that a system describing itself as local had no honest,
findable account of what it sends. §6.28 is what that costs: a "must not leave
the machine" claim about the sleeping mic that the code did not implement, and
nothing in the repo would have contradicted it.

So this is the flag-registry pattern (§6.36) pointed at privacy. Modules that
can talk to the network are **discovered** by scanning imports and call names;
what each sends is hand-written; and `tests/test_egress_registry.py` fails when
a module gains network access without an entry. A new skill that quietly phones
home breaks the build instead of shipping.

### The distinction that matters

`LOCAL` — loopback or LAN only (Ollama, the health server, the LAN link, the
single-instance port check). These do not leave the machine and are listed for
completeness, because "it imports `requests`" is not the same as "it leaks".

`REMOTE` — genuinely leaves. These are the ones a privacy-conscious user needs
to be able to enumerate, and `docs/PRIVACY.md` does.
"""
from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass, field
from typing import Dict, List

LOCAL = "local"
REMOTE = "remote"
OPTIONAL = "optional"        # remote, but only when the user invokes it

# Import roots that mean "this module can open a connection".
#
# `urllib` is deliberately NOT here: `urllib.parse` is pure string
# manipulation — quoting a search term is not egress — and counting it flagged
# four modules that never touch the network. A privacy document that cries
# wolf is one people learn to skip, so the submodule is matched instead.
_NET_IMPORTS = {
    "requests", "urllib3", "http", "httpx", "aiohttp", "socket",
    "websocket", "websockets", "edge_tts", "firebase_admin", "smtplib",
    "ftplib", "telnetlib", "gspread", "googleapiclient",
}
# Fully-qualified module names that DO mean network, where the root does not.
_NET_SUBMODULES = {"urllib.request", "urllib.error"}
# Call names that mean it, independent of how the module was imported.
_NET_CALLS = ("recognize_google", "recognize_bing", "recognize_wit",
              "urlopen", "edge_tts.Communicate")

SCAN_DIRS = ("core", "skills", "ui")


@dataclass
class Egress:
    module: str
    triggers: List[str] = field(default_factory=list)


def discover_egress(root: pathlib.Path | None = None) -> Dict[str, Egress]:
    """Modules that can reach the network, and why we think so.

    AST for imports (precise), substring for the call names (they appear as
    attribute chains on objects this scan does not resolve). Over-reporting is
    the safe direction: an extra entry costs one line of description, a missed
    one costs the honesty of the whole document.
    """
    root = root or pathlib.Path(__file__).resolve().parents[1]
    out: Dict[str, Egress] = {}
    me = pathlib.Path(__file__).resolve()
    for d in SCAN_DIRS:
        base = root / d
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            if "_archive" in str(f) or f.resolve() == me:
                continue
            try:
                src = f.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(src)
            except (OSError, SyntaxError):
                continue
            triggers = set()
            for n in ast.walk(tree):
                # ast.walk descends into function bodies, so a lazily-imported
                # network library is caught the same as a top-level one.
                if isinstance(n, ast.Import):
                    for a in n.names:
                        top = a.name.split(".")[0]
                        if top in _NET_IMPORTS:
                            triggers.add(f"import {top}")
                        elif a.name in _NET_SUBMODULES:
                            triggers.add(f"import {a.name}")
                elif isinstance(n, ast.ImportFrom) and n.module:
                    top = n.module.split(".")[0]
                    if top in _NET_IMPORTS:
                        triggers.add(f"from {top}")
                    elif n.module in _NET_SUBMODULES:
                        triggers.add(f"from {n.module}")
            for call in _NET_CALLS:
                if call in src:
                    triggers.add(f"calls {call}")
            if triggers:
                rel = str(f.relative_to(root)).replace("\\", "/")
                out[rel] = Egress(module=rel, triggers=sorted(triggers))
    return out


# Hand-written: a scanner can see that a module imports `requests`; only a
# person can say what it sends, to whom, and whether the user chose it.
# module → (scope, destination, what is sent, how to avoid it)
DESCRIPTIONS: Dict[str, tuple] = {
    # ── the two that matter most ─────────────────────────────────────
    "core/stt.py": (REMOTE, "Google Speech (en-IN)",
                    "Recorded audio of what you said, on every voice turn.",
                    "Install the Vosk model — a SLEEPING mic then transcribes "
                    "locally first (§6.28), and AERIS_VOICE_STREAMING=1 is "
                    "Vosk end-to-end. Typed input never reaches it."),
    "core/voice_engine.py": (REMOTE, "Google Speech (en-IN)",
                             "Recorded audio, same as core/stt.py — this is "
                             "the in-process Qt path.",
                             "Same as core/stt.py. AERIS_SPLIT_VOICE=1 moves "
                             "this to core/voice_service.py."),
    "core/tts.py": (REMOTE, "Microsoft Edge TTS",
                    "The TEXT of every reply AERIS speaks aloud.",
                    "Uninstall edge_tts to fall back to pyttsx3/SAPI5, which "
                    "are fully offline — at the cost of the Neerja voice."),

    # ── phone / LAN ─────────────────────────────────────────────────
    "core/cloud_bridge.py": (REMOTE, "Firebase (your project)",
                             "Phone<->laptop messages, end-to-end encrypted "
                             "with AES-GCM before upload.",
                             "AERIS_DISABLE_BRIDGE=1, or simply never pair a "
                             "phone."),
    "core/phone_bridge.py": (LOCAL, "your LAN",
                             "Direct phone<->laptop traffic on the local "
                             "network.", "Do not pair a phone."),
    "core/lan_link.py": (LOCAL, "your LAN", "Device discovery on the local "
                         "network.", "-"),
    "core/health_server.py": (LOCAL, "127.0.0.1:8765",
                              "A status endpoint for local tooling.", "-"),
    "core/single_instance.py": (LOCAL, "127.0.0.1",
                                "A port probe to detect an already-running "
                                "AERIS.", "-"),
    "core/llm_chat.py": (LOCAL, "127.0.0.1:11434 (Ollama)",
                         "Prompts to a locally-running model. Never leaves "
                         "the machine.", "-"),

    # ── user-invoked skills: remote by definition ────────────────────
    "skills/weather.py": (OPTIONAL, "weather API",
                          "The city you asked about.", "Do not ask for weather."),
    "skills/web_search.py": (OPTIONAL, "search engine",
                             "Your search query.", "Do not use search skills."),
    "skills/dictionary.py": (OPTIONAL, "dictionary API",
                             "The word you asked to define.", "-"),
    "skills/info_skills.py": (OPTIONAL, "public info APIs",
                              "The subject of the question.", "-"),
    "skills/sheets_sync.py": (OPTIONAL, "Google Sheets",
                              "Rows you asked to sync.", "Do not use the "
                              "sheets skills."),
    "skills/productivity_pack.py": (OPTIONAL, "various web endpoints",
                                    "Whatever the invoked skill needs.", "-"),
    "skills/diagnostics.py": (OPTIONAL, "Edge TTS voice list",
                              "A voice-list request when diagnosing TTS.", "-"),
    "skills/weather_for_city.py": (OPTIONAL, "weather API",
                                   "The city name you asked about.",
                                   "Do not ask for weather."),
    "skills/system_health.py": (OPTIONAL, "a public host (reachability probe)",
                                "Nothing about you - an empty request used to "
                                "answer 'is the internet up?'.",
                                "Do not run the connectivity check."),
    "skills/system_skills.py": (OPTIONAL, "a public host (reachability probe)",
                                "Nothing about you - same connectivity probe.",
                                "Do not run the connectivity check."),
    "skills/windows_power_utils.py": (LOCAL, "your own machine",
                                      "Hostname/IP lookups about this "
                                      "computer, for the network-info skill.",
                                      "-"),
    "ui/jarvis_v31/tab_panels.py": (OPTIONAL, "whatever a panel fetches",
                                    "A panel-initiated fetch, only when you "
                                    "open and use that panel.", "-"),
}


def undocumented(found: Dict[str, Egress] | None = None) -> List[str]:
    found = found if found is not None else discover_egress()
    return sorted(m for m in found if m not in DESCRIPTIONS)


def stale(found: Dict[str, Egress] | None = None) -> List[str]:
    found = found if found is not None else discover_egress()
    return sorted(m for m in DESCRIPTIONS if m not in found)


def remote_modules(found: Dict[str, Egress] | None = None) -> List[str]:
    """Everything that genuinely leaves the machine, unconditionally."""
    found = found if found is not None else discover_egress()
    return sorted(m for m in found
                  if DESCRIPTIONS.get(m, (None,))[0] == REMOTE)


def render_markdown(found: Dict[str, Egress] | None = None) -> str:
    found = found if found is not None else discover_egress()
    lines = [
        "# What leaves this machine",
        "",
        "**Generated - do not edit by hand.** Run `python gen_privacy_doc.py`.",
        "",
        "AERIS's *brain* is local: routing, memory, the embedded Qwen and "
        "Ollama at `localhost:11434` never touch the network. Its **ears and "
        "voice are not** - and that is the honest headline this file exists "
        "to state plainly.",
        "",
    ]
    for scope, title, blurb in (
        (REMOTE, "Always-on remote", "These send data off the machine as part "
         "of normal use. Nothing here is accidental - they are the tested "
         "Hinglish voice stack - but you should know they exist."),
        (OPTIONAL, "Remote, only when you ask", "Skills that are network "
         "services by definition. They send only what the request needs."),
        (LOCAL, "Local only", "Loopback or LAN. Listed for completeness: "
         "importing `requests` is not the same as leaking."),
    ):
        rows = [(m, DESCRIPTIONS[m]) for m in sorted(found)
                if DESCRIPTIONS.get(m, (None,))[0] == scope]
        if not rows:
            continue
        lines += [f"## {title}", "", blurb, "",
                  "| Module | Goes to | What is sent | How to avoid it |",
                  "| --- | --- | --- | --- |"]
        for m, (_s, dest, sends, avoid) in rows:
            lines.append(f"| `{m}` | {dest} | {sends} | {avoid} |")
        lines.append("")
    lines += ["## Why each module is listed", ""]
    for m in sorted(found):
        lines.append(f"- `{m}` - {', '.join(found[m].triggers)}")
    lines.append("")
    return "\n".join(lines)
