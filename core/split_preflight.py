"""Can this machine actually run split mode? (§6.35)

Five subsystems now live behind flags — `AERIS_SPLIT_BRAIN`, `AERIS_LITE_ML`,
`AERIS_SPLIT_VISION`, `AERIS_SPLIT_VOICE`, `AERIS_BRAIN_HIBERNATE_S` — and each
was verified with fakes plus, where possible, a real spawn. What none of that
answers is the question actually standing between the work and the user:

    "if I set these on **my** machine, will they work?"

Turning a flag on and finding out from a silent degradation is a bad way to
learn. This runs the checks that matter and says which flags are safe.

### Design

Every check is a `Check` returning PASS / FAIL / WARN / SKIP with a *reason*
and, when it fails, a **fix hint** — a failure that does not say what to do
about it just moves the guessing somewhere else.

Checks are ordered cheapest-first and later ones are skipped when a
prerequisite failed, so a machine with no working bus does not spend 40 s
spawning children to tell you the same thing five times.

Nothing here opens the camera or the microphone. Device *presence* is checked
by importing the libraries and asking the services for `status`, which §6.25's
laziness rule guarantees does not claim hardware. Actually exercising the
devices is what `run_vision_split.py` and `run_voice_split.py` are for — this
answers "is it plausible", they answer "does it work".
"""
from __future__ import annotations

import importlib
import logging
import os
from dataclasses import dataclass, field
from typing import Callable, List, Optional

log = logging.getLogger(__name__)

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
SKIP = "SKIP"


@dataclass
class Check:
    name: str
    status: str
    reason: str = ""
    fix: str = ""
    unlocks: tuple = ()          # flags this check gates

    @property
    def ok(self) -> bool:
        return self.status in (PASS, WARN)


@dataclass
class Report:
    checks: List[Check] = field(default_factory=list)

    def add(self, c: Check) -> Check:
        self.checks.append(c)
        return c

    def by_name(self, name: str) -> Optional[Check]:
        for c in self.checks:
            if c.name == name:
                return c
        return None

    def failed(self) -> List[Check]:
        return [c for c in self.checks if c.status == FAIL]

    def safe_flags(self) -> List[str]:
        """Flags whose every gating check passed."""
        gated: dict = {}
        for c in self.checks:
            for f in c.unlocks:
                gated.setdefault(f, []).append(c.ok)
        return sorted(f for f, oks in gated.items() if all(oks))

    def render(self) -> str:
        width = max((len(c.name) for c in self.checks), default=0)
        lines = ["", "AERIS split-mode preflight", "=" * 40]
        for c in self.checks:
            lines.append(f"  [{c.status:4}] {c.name.ljust(width)}  {c.reason}")
            if c.fix:
                lines.append(f"         → {c.fix}")
        lines.append("")
        safe = self.safe_flags()
        if safe:
            lines.append("Safe to enable:")
            lines += [f"  {f}" for f in safe]
        else:
            lines.append("No split flags are safe to enable yet.")
        bad = self.failed()
        if bad:
            lines.append("")
            lines.append(f"{len(bad)} check(s) failed — see the → lines above.")
        lines.append("")
        lines.append("This checks plausibility, not behaviour. Confirm with:")
        lines.append("  python run_vision_split.py    (wave at the camera)")
        lines.append("  python run_voice_split.py     (speak)")
        return "\n".join(lines)


# ── individual checks ────────────────────────────────────────────────

def _mod(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def check_imports(report: Report) -> None:
    """Libraries each split needs, checked without touching hardware."""
    for label, mods, unlocks, hint in (
        ("mediapipe", ("mediapipe",), ("AERIS_SPLIT_VISION",),
         "pip install mediapipe — gestures cannot run in any mode without it"),
        ("opencv", ("cv2",), ("AERIS_SPLIT_VISION",),
         "pip install opencv-python — needed for the camera and JPEG snapshots"),
        ("speech_recognition", ("speech_recognition",), ("AERIS_SPLIT_VOICE",),
         "pip install SpeechRecognition — the STT front end"),
        ("audio output", ("pygame",), ("AERIS_SPLIT_VOICE",),
         "pip install pygame — edge-tts playback goes through its mixer"),
    ):
        missing = [m for m in mods if _mod(m) is None]
        if missing:
            report.add(Check(label, FAIL, f"missing: {', '.join(missing)}",
                             hint, unlocks))
        else:
            report.add(Check(label, PASS, "importable", unlocks=unlocks))

    # Optional: absence degrades rather than breaks, so WARN not FAIL.
    for label, mod, why in (
        ("vosk (offline STT)", "vosk",
         "without it a SLEEPING mic falls back to Google for wake words (§6.28)"),
        ("edge_tts", "edge_tts",
         "TTS falls back to pyttsx3/SAPI5 — a different, non-Hinglish voice"),
    ):
        if _mod(mod) is None:
            report.add(Check(label, WARN, "not installed", why))
        else:
            report.add(Check(label, PASS, "importable"))


def check_bus(report: Report, spawn_probe: Optional[Callable] = None) -> None:
    """Can this interpreter actually run a child service? Everything else in
    split mode is downstream of this, so it gates all the flags."""
    # NOT AERIS_SPLIT_BRAIN: the bus is necessary for it but not sufficient
    # (the brain child also needs the ML stack). `check_brain_stack` owns that
    # flag, and records a SKIP carrying it when this check fails — so a dead
    # bus still blocks the brain split, without a passing bus granting it.
    unlocks = ("AERIS_SPLIT_VISION", "AERIS_SPLIT_VOICE")
    try:
        ok, detail = (spawn_probe or _default_spawn_probe)()
    except Exception as e:
        report.add(Check("service bus", FAIL, f"spawn raised: {e}",
                         "multiprocessing 'spawn' is required — check that the "
                         "entry point is guarded by if __name__ == '__main__'",
                         unlocks))
        return
    report.add(Check("service bus", PASS if ok else FAIL,
                     detail,
                     "" if ok else "a child process could not be started or "
                                   "did not answer a ping",
                     unlocks))


def _default_spawn_probe():
    from core.service_bus import ServiceProxy, echo_handler_factory
    p = ServiceProxy("preflight", echo_handler_factory)
    if not p.start(ready_timeout=60):
        return False, "child did not come up"
    try:
        r = p.request("echo", {"text": "ping"}, timeout=20)
        return bool(r.ok), ("child answered" if r.ok else f"error: {r.error}")
    finally:
        p.stop()


def check_service(report: Report, label: str, factory_path: str,
                  unlocks: tuple, probe: Optional[Callable] = None) -> None:
    """Spawn one real service child and ask it for `status`.

    Deliberately only `status`: §6.25's laziness rule means that answers
    without opening a microphone, and `GestureEngine`'s constructor loads
    MediaPipe's model without claiming the camera.
    """
    bus = report.by_name("service bus")
    if bus is not None and not bus.ok:
        report.add(Check(label, SKIP, "service bus check failed",
                         unlocks=unlocks))
        return
    try:
        ok, detail = (probe or _default_service_probe)(factory_path)
    except Exception as e:
        report.add(Check(label, FAIL, f"raised: {e}",
                         "the child could not be built — run the matching "
                         "run_*_split.py to see the full error", unlocks))
        return
    report.add(Check(label, PASS if ok else FAIL, detail,
                     "" if ok else "the service started but reported it cannot "
                                   "run here", unlocks))


def _default_service_probe(factory_path: str):
    mod_name, _, attr = factory_path.rpartition(".")
    factory = getattr(importlib.import_module(mod_name), attr)
    from core.service_bus import ServiceProxy
    p = ServiceProxy("preflight", factory)
    if not p.start(ready_timeout=180):
        return False, "child did not come up"
    try:
        r = p.request("status", {}, timeout=30)
        if not r.ok:
            return False, f"status error: {r.error}"
        payload = r.payload or {}
        if "available" in payload and not payload["available"]:
            return False, "started, but reports the device stack unavailable"
        return True, f"child up, status={_brief(payload)}"
    finally:
        p.stop()


def _brief(payload: dict) -> str:
    keep = ("available", "enabled", "state", "mic_open", "speaker_ready")
    return "{" + ", ".join(f"{k}={payload[k]}" for k in keep
                           if k in payload) + "}"


# The brain child needs a stack nothing else here does, and the failure that
# matters is an ABI break — `numpy.dtype size changed` from a mismatched
# pandas/numpy, which is invisible to `find_spec` because it only happens on
# *import*. So this actually imports them, in a throwaway subprocess: catching
# the break is the whole point, and carrying torch into the preflight process
# afterwards would be a waste.
_BRAIN_MODULES = ("numpy", "torch", "sentence_transformers", "sklearn", "spacy")

_BRAIN_PROBE_SRC = """
import json, sys
bad = {}
for m in %r:
    try:
        __import__(m)
    except Exception as e:
        bad[m] = "%%s: %%s" %% (type(e).__name__, e)
print(json.dumps(bad))
"""


def _default_brain_probe(timeout: float = 180.0):
    import json
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-c", _BRAIN_PROBE_SRC % (_BRAIN_MODULES,)],
                         capture_output=True, text=True, timeout=timeout)
    line = (out.stdout or "").strip().splitlines()[-1] if out.stdout.strip() else "{}"
    try:
        bad = json.loads(line)
    except Exception:
        return False, f"probe produced no verdict (rc={out.returncode})"
    if bad:
        first = next(iter(bad.items()))
        return False, f"{len(bad)} import(s) failed — {first[0]}: {first[1][:70]}"
    return True, "torch + sentence-transformers + spaCy all import"


def check_brain_stack(report: Report,
                      probe: Optional[Callable] = None) -> None:
    """Does the heavy ML stack actually import here?

    `AERIS_SPLIT_BRAIN` was previously reported safe on the strength of the
    *echo* child alone, which proves only that spawning works. The brain child
    additionally needs torch, sentence-transformers, sklearn and spaCy — and
    this project has a documented history of exactly that stack breaking on an
    ABI mismatch while everything else stayed fine. Claiming the flag safe
    without checking it was the same overclaim pattern this file exists to
    prevent elsewhere.
    """
    unlocks = ("AERIS_SPLIT_BRAIN",)
    bus = report.by_name("service bus")
    if bus is not None and not bus.ok:
        report.add(Check("brain ML stack", SKIP, "service bus check failed",
                         unlocks=unlocks))
        return
    try:
        ok, detail = (probe or _default_brain_probe)()
    except Exception as e:
        report.add(Check("brain ML stack", FAIL, f"probe failed: {e}",
                         "could not run a subprocess to import the ML stack",
                         unlocks))
        return
    report.add(Check("brain ML stack", PASS if ok else FAIL, detail,
                     "" if ok else "reinstall the ML stack for this "
                                   "interpreter — an ABI mismatch (e.g. "
                                   "'numpy.dtype size changed') stops the "
                                   "brain child booting at all",
                     unlocks))


def run(spawn_probe: Optional[Callable] = None,
        service_probe: Optional[Callable] = None,
        brain_probe: Optional[Callable] = None) -> Report:
    report = Report()
    check_imports(report)
    check_bus(report, spawn_probe=spawn_probe)
    check_service(report, "vision service", "core.vision_service.vision_handler_factory",
                  ("AERIS_SPLIT_VISION",), probe=service_probe)
    check_service(report, "voice service", "core.voice_service.voice_handler_factory",
                  ("AERIS_SPLIT_VOICE",), probe=service_probe)
    # Last, and the slowest — importing torch + sentence-transformers costs
    # ~12 s even when healthy, so everything cheap reports first.
    check_brain_stack(report, probe=brain_probe)
    return report


def main() -> int:
    logging.basicConfig(level=os.environ.get("AERIS_LOG", "WARNING"))
    report = run()
    print(report.render())
    return 1 if report.failed() else 0
