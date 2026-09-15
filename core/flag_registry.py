"""Every `AERIS_*` environment flag, discovered from the source (§6.36).

Twenty-four flags now exist across `core/`, `ui/`, `skills/` and the launchers.
`CLAUDE.md` documented about ten. That gap is the ordinary fate of a
hand-maintained list next to code that keeps growing, and it matters more than
usual here because these flags are how every load-free and split-mode
behaviour is turned on — a flag nobody knows about is a feature nobody uses,
and a flag whose behaviour drifted from its description is worse than one that
was never written down.

So the list is **discovered**, not maintained: `discover_flags()` scans for
`environ.get("AERIS_…")` and friends and reports every flag with the places it
is read. Descriptions stay hand-written — a machine cannot say *why* a flag
exists — but `tests/test_flag_registry.py` fails when a discovered flag has no
description, so adding one without documenting it breaks the build rather than
quietly widening the gap.

`gen_flags_doc.py` renders `docs/FLAGS.md` from this.
"""
from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass, field
from typing import Dict, List

# Matches the ways this codebase reads a flag:
#   os.environ.get(...)  environ.get(...)  os.getenv(...)  os.environ[...]
#   and module constants such as  ENV_SPLIT_VOICE = "<the flag name>"
_FLAG_RE = re.compile(r'["\'](AERIS_[A-Z0-9_]+)["\']')

SCAN_DIRS = ("core", "ui", "skills")
SCAN_ROOT_GLOB = "*.py"

# Flags that are read only by tooling/tests and are not user-facing knobs.
INTERNAL = {
    "AERIS_LOG",              # log level for the preflight/CLI entry points
    "AERIS_GATE_DEBUG",       # prints chat-gate decisions while debugging
    "AERIS_PYTHON",           # interpreter override, read by the .bat launchers
}


@dataclass
class Flag:
    name: str
    sites: List[str] = field(default_factory=list)

    @property
    def internal(self) -> bool:
        return self.name in INTERNAL


def discover_flags(root: pathlib.Path | None = None) -> Dict[str, Flag]:
    """Every `AERIS_*` flag literal in the source, with where it appears.

    Deliberately textual rather than an AST walk: flags are read through at
    least four different call shapes plus module-level constants, and a regex
    over string literals catches all of them without needing to model each.
    The cost is that a flag *mentioned* in a comment counts — which is the
    safe direction, since it means the doc over-reports rather than missing
    one.
    """
    root = root or pathlib.Path(__file__).resolve().parents[1]
    out: Dict[str, Flag] = {}
    files: List[pathlib.Path] = []
    for d in SCAN_DIRS:
        base = root / d
        if base.exists():
            files += [f for f in base.rglob("*.py") if "_archive" not in str(f)]
    files += sorted(root.glob(SCAN_ROOT_GLOB))
    # Never scan this file. Every DESCRIPTIONS key is a string literal here, so
    # including it would rediscover each flag from its own description — and
    # `stale()` could then never fire, which is the one thing it exists to do.
    files = [f for f in files if f.resolve() != pathlib.Path(__file__).resolve()]
    for f in files:
        try:
            src = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(src.splitlines(), 1):
            for name in _FLAG_RE.findall(line):
                flag = out.setdefault(name, Flag(name=name))
                rel = str(f.relative_to(root)).replace("\\", "/")
                site = f"{rel}:{i}"
                if site not in flag.sites:
                    flag.sites.append(site)
    return out


# Hand-written, because a scanner cannot say why a flag exists. Keyed by flag
# name → (one-line effect, default, doc section). The test suite fails if a
# discovered non-internal flag is missing here.
DESCRIPTIONS: Dict[str, tuple] = {
    # ── process isolation / split mode ───────────────────────────────
    "AERIS_SPLIT_BRAIN": (
        "Brain (torch + encoder + skills) runs in a supervised child process; "
        "the GUI imports no ML. Fixes the 0xC0000374 crash class.", "off", "Split mode"),
    "AERIS_SPLIT_VISION": (
        "Camera + MediaPipe run in a child process; `get_gesture_engine()` "
        "returns a `RemoteGestureEngine` with the same surface (§6.30).", "off", "Split mode"),
    "AERIS_SPLIT_VOICE": (
        "Mic + speaker run in a child process behind the same Qt signals "
        "`VoiceWorker` already consumes (§6.31).", "off", "Split mode"),
    "AERIS_BRAIN_HIBERNATE_S": (
        "Retire the idle brain child after N seconds, carrying the "
        "conversation across the respawn (§6.22). ~478 MB → ~20 MB resting.", "0 (off)", "Split mode"),

    # ── load / memory ────────────────────────────────────────────────
    "AERIS_LITE_ML": (
        "Boot with no model weights; the tiered router pulls each in on the "
        "first utterance that needs it.", "off", "Load"),
    "AERIS_IDLE_UNLOAD_S": (
        "Drop model weights after N seconds idle (encoder, neural head, "
        "spaCy, local LLM). `0` never unloads.", "300", "Load"),
    "AERIS_LLM_IDLE_UNLOAD_S": (
        "Idle window for the local Qwen gguf alone — ~1 GB and the most "
        "expensive thing to reload, so you may want it held longer.", "AERIS_IDLE_UNLOAD_S, else 300", "Load"),
    "AERIS_FORCE_ENCODER": (
        "Always use the encoder, skipping the cheap router tiers. Debugging "
        "aid for routing comparisons.", "off", "Load"),
    "AERIS_MATH_THREADS": (
        "Overrides the BLAS/OMP thread pin (default 1, which avoids heap "
        "corruption when audio and encode threads run together).", "1", "Load"),
    "AERIS_BOOT_THROTTLE_MS": (
        "Delay between staged boot chunks, so the first paint stays smooth.", "tuned", "Load"),
    "AERIS_CLASSIC_BOOT": (
        "Skip the staged/instant boot path and build everything eagerly.", "off", "Load"),

    # ── devices ──────────────────────────────────────────────────────
    "AERIS_CAMERA_IDLE_S": (
        "Release the webcam after N seconds with no hand in frame. Trades a "
        "capability for resources: gestures stop until re-enabled.", "0 (off)", "Devices"),
    "AERIS_VOICE_STREAMING": (
        "Live partial transcripts while you speak. **Off by default for a "
        "models reason**: `listen_streaming` is Vosk end-to-end, so the final "
        "never reaches Google en-IN (§6.29).", "off", "Devices"),
    "AERIS_DISABLE_BRIDGE": (
        "Never start the phone bridge. The test suite sets this.", "off", "Devices"),

    # ── behaviour ────────────────────────────────────────────────────
    "AERIS_REPAIR_MEMORY": (
        "In-session self-correction: learn a failed phrasing from your "
        "rephrase and route it correctly from then on (§6.24).", "off", "Behaviour"),
    "AERIS_AUTONOMY_LEVEL": (
        "Ceiling for the Autonomy Ladder, overriding per-class grants.", "per-class", "Behaviour"),
    "AERIS_AFFECT_OFF": (
        "Disable the Affective Core — no mood tracking, no proactive "
        "emotional check-ins.", "off (affect on)", "Behaviour"),
    "AERIS_ANTICIPATE_OFF": (
        "Disable anticipation offers (habit-learned next-action nudges).", "off", "Behaviour"),
    "AERIS_COGNITION_OFF": (
        "Disable the higher cognition layer.", "off", "Behaviour"),
    "AERIS_INTERPRET_OFF": (
        "Disable the Interpreter strategy layer (chat vs command routing).", "off", "Behaviour"),
    "AERIS_REASONING_CACHE_OFF": (
        "Disable the reasoning cache on purely conversational turns.", "off", "Behaviour"),
    "AERIS_SHOW_NODES": (
        "Re-enable the telemetry stat-cards removed in §4.1.", "off", "Behaviour"),
}


def undocumented(flags: Dict[str, Flag] | None = None) -> List[str]:
    """Discovered, user-facing, and missing a description — the guard."""
    flags = flags if flags is not None else discover_flags()
    return sorted(n for n, f in flags.items()
                  if not f.internal and n not in DESCRIPTIONS)


def stale(flags: Dict[str, Flag] | None = None) -> List[str]:
    """Described but no longer present in the source — a removed flag whose
    documentation outlived it, which is how a doc starts lying."""
    flags = flags if flags is not None else discover_flags()
    return sorted(n for n in DESCRIPTIONS if n not in flags)


def render_markdown(flags: Dict[str, Flag] | None = None) -> str:
    flags = flags if flags is not None else discover_flags()
    lines = [
        "# AERIS environment flags",
        "",
        "**Generated — do not edit by hand.** Run `python gen_flags_doc.py`.",
        "",
        "Discovered by scanning the source, so this cannot silently miss a "
        "flag; descriptions are hand-written in `core/flag_registry.py`, and "
        "`tests/test_flag_registry.py` fails if a flag is added without one.",
        "",
    ]
    sections: Dict[str, list] = {}
    for name, f in sorted(flags.items()):
        if f.internal or name not in DESCRIPTIONS:
            continue
        desc, default, section = DESCRIPTIONS[name]
        sections.setdefault(section, []).append((name, desc, default, f))
    for section in ("Split mode", "Load", "Devices", "Behaviour"):
        rows = sections.get(section)
        if not rows:
            continue
        lines += [f"## {section}", "", "| Flag | Default | Effect |",
                  "| --- | --- | --- |"]
        for name, desc, default, _f in rows:
            lines.append(f"| `{name}` | {default} | {desc} |")
        lines.append("")
    lines += ["## Where each is read", ""]
    for name, f in sorted(flags.items()):
        if f.internal:
            continue
        lines.append(f"- `{name}` — {', '.join(f.sites[:4])}"
                     + (f" (+{len(f.sites) - 4} more)" if len(f.sites) > 4 else ""))
    lines += ["", "## Internal / tooling", ""]
    for name in sorted(INTERNAL):
        if name in flags:
            lines.append(f"- `{name}`")
    lines.append("")
    return "\n".join(lines)
