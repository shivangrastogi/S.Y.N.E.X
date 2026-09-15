"""AERIS / Jarvis terminal entry point.

Modes:

    python main.py              voice mode — STT + TTS, single-shot listening loop
    python main.py --wake       wake-word mode — Vosk listens passively, fires on
                                "hey jarvis" / "hey aeris" / "jarvis" / "aeris"
    python main.py --standby    always-on low-power mode — Tier-0 wake tier stays
                                up; the heavy brain is DORMANT until woken, then
                                spun down again after idle
    python main.py --text       text mode — read stdin, print responses (no audio)
    python main.py --verbose    enable debug logging
    python main.py --vault      prompt for memory passphrase (encrypted memory mode)

All modes share the same JarvisMainEngine.process_text() pipeline; only the
input/output transport changes.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Console output as UTF-8 so status glyphs (·, —, …) render on modern terminals
# and can never hard-crash the encoder on Windows' legacy cp1252 console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Heap-corruption guard (Windows 0xc0000374): pin torch/MKL/OpenMP to one
# native thread before the engine (and torch) import, so concurrent audio +
# encode threads can't corrupt the heap. See run_gui.py for the full note.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
_math_threads = os.environ.get("AERIS_MATH_THREADS", "1")
for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS",
             "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, _math_threads)

from core import settings as _settings
from core.main_engine import JarvisMainEngine

_WAKE_MODEL_PATH = os.path.join("data", "models", "vosk-model-small-en-in-0.4")


def _maybe_passphrase(prompt: bool) -> str | None:
    if not prompt:
        return None
    pw = getpass.getpass("Memory vault passphrase: ").strip()
    if not pw:
        print("(empty passphrase — running without vault)")
        return None
    return pw


def run_voice(passphrase: str | None) -> None:
    print(f"{_settings.assistant_name()} voice mode. Press Ctrl-C to exit.")
    engine = JarvisMainEngine(memory_passphrase=passphrase)
    engine.run()


def run_wake(passphrase: str | None) -> None:
    """Wake-word mode: passively listen via Vosk, dispatch one turn per wake."""
    from core.wake_word import WakeWordDetector

    print(f"{_settings.assistant_name()} wake mode. Initialising brain...")
    engine = JarvisMainEngine(memory_passphrase=passphrase)

    try:
        detector = WakeWordDetector(_WAKE_MODEL_PATH)
    except FileNotFoundError as e:
        print(f"\nWake word detector failed to start:\n  {e}\n")
        print("Falling back to standard voice mode.")
        engine.run()
        return

    engine._ensure_io()
    name = _settings.assistant_name()
    engine._speak(f"{name} standing by, sir.")
    print(f"\nSay 'Hey {name}' to activate. Ctrl-C to exit.\n")

    def on_wake() -> None:
        engine._speak("Yes sir?")
        try:
            text = engine._stt.listen()
        except Exception as e:
            print(f"  [stt error] {e}")
            return
        if not text:
            return
        print(f"You: {text}")
        try:
            response = engine.process_text(text)
        except Exception as e:
            print(f"  [engine error] {e}")
            return
        if response:
            engine._speak(response)

    try:
        detector.listen(on_wake)
    except KeyboardInterrupt:
        print("\nShutting down.")


def run_standby(passphrase: str | None) -> None:
    """Always-on standby mode — the tiered-wake, low-power OS layer.

    Unlike ``--wake`` (which loads the *whole* brain and keeps it resident), this
    runs only the lightweight Tier-0 (Vosk wake word + STT + TTS + power monitor)
    and keeps the heavy Brain in its OWN process, **dormant** until you say the
    wake word — then spun up, and torn back down after the conversation goes
    idle. That is what lets AERIS stand by all day without eating the battery.

    Heavy imports are function-local so this only pays for what it uses.
    """
    from core.wake_word import WakeWordDetector
    from core.stt import STT
    from core.tts import TTS
    from core.service_bus import ServiceProxy
    from core.brain_service import brain_handler_factory
    from core.standby_runtime import BrainLifecycle
    from core.standby_config import StandbyConfig
    from core.standby_app import build_standby_stack
    from core.standby_controls import run_tray

    name = _settings.assistant_name()
    cfg = StandbyConfig.from_settings(_settings.get)
    print(f"{name} standby — Tier-0 always on, brain dormant until woken.")
    print(f"  config: {cfg.summary()}")

    # Tier-0: the tiny always-on pieces. Missing model → fall back to --wake.
    try:
        detector = WakeWordDetector(_WAKE_MODEL_PATH)
    except FileNotFoundError as e:
        print(f"\nWake model missing:\n  {e}\nFalling back to --wake mode.")
        return run_wake(passphrase)
    stt = STT()
    tts = TTS()

    # Tier-2: the heavy brain, isolated in its own process — spun up/down on
    # demand. auto_restart is NOT used here: the orchestrator owns the lifecycle.
    proxy = ServiceProxy("brain", brain_handler_factory)
    brain = BrainLifecycle(proxy, ask_timeout=cfg.ask_timeout_s)

    # Optional power reactions (drop the brain on a critical battery).
    power = None
    try:
        from core.power_state import get_monitor
        power = get_monitor()
        power.start()
    except Exception as e:  # psutil / platform hiccup — run without power tier
        print(f"  (power monitor unavailable: {e})")
        power = None

    # Assemble the whole standby subsystem (the wiring is tested in standby_app).
    stack = build_standby_stack(
        brain=brain, stt=stt.listen, tts=tts.speak, wake_detector=detector,
        power_monitor=power, cfg=cfg,
        stats_path=os.path.join("data", "standby_stats.json"),
        journal_path=os.path.join("data", "standby_journal.json"),
        log=print,
    )
    if stack.lifetime.sessions > 0:
        print(f"  {stack.lifetime.summary_line()}")

    tts.speak(f"{name} standing by, sir.")
    print(f"\nSay 'Hey {name}' to wake me. Ctrl-C to exit.\n")
    stack.daemon.start()
    print(f"\n{stack.health.format_report()}\n")
    try:
        try:
            run_tray(stack.controls)  # system tray — blocks; Quit stops the daemon
        except RuntimeError as e:
            print(f"  (no system tray: {e}) — running headless.\n")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down standby.")
    finally:
        stack.daemon.stop()
        # Bank this session's duty cycle into the lifetime total + flush the log.
        try:
            stack.journal.record("shutdown")
            stack.journal.flush()
            lt = stack.store.commit(stack.stats.snapshot())
            print(f"  {lt.summary_line()}")
        except Exception as e:
            print(f"  (could not save lifetime stats: {e})")
        if power is not None:
            try:
                power.stop()
            except Exception:
                pass


def run_standby_status() -> None:
    """Print the offline standby status — config, lifetime duty cycle, autostart
    and wake-model readiness — without booting the always-on loop. Cheap
    introspection: no brain, no mic, no Vosk model load."""
    from core.standby_config import StandbyConfig
    from core.standby_persist import StandbyStatsStore
    from core.standby_journal import StandbyJournal
    from core.standby_status import offline_status, format_offline_status

    cfg = StandbyConfig.from_settings(_settings.get)
    lifetime = StandbyStatsStore(os.path.join("data", "standby_stats.json")).load()

    journal = StandbyJournal(path=os.path.join("data", "standby_journal.json"))
    journal.load()

    autostart = False
    try:
        from core.autostart import AutostartManager
        autostart = AutostartManager().is_enabled()
    except Exception:
        pass

    status = offline_status(
        config=cfg,
        lifetime=lifetime,
        autostart_enabled=autostart,
        wake_model_present=os.path.isdir(_WAKE_MODEL_PATH),
        recent_events=journal.format_recent(10),
    )
    print(format_offline_status(status, name=_settings.assistant_name()))


def run_standby_journal(kind: str | None = None, limit: int = 30) -> None:
    """Print the standby event journal (journalctl-style) — per-kind counts plus
    the most recent events, optionally filtered to one kind. No boot."""
    from core.standby_journal import StandbyJournal

    journal = StandbyJournal(path=os.path.join("data", "standby_journal.json"))
    journal.load()

    total = journal.count()
    if total == 0:
        print(f"{_settings.assistant_name()} journal — no events recorded yet.")
        return

    summary = journal.summary()
    print(f"{_settings.assistant_name()} journal — {total} event(s):")
    print("  " + " · ".join(f"{k}: {c}" for k, c in sorted(summary.items())))

    lines = journal.format_recent(max(1, int(limit)), kind=kind)
    header = (f"  last {len(lines)} '{kind}' event(s):" if kind
              else f"  last {len(lines)} event(s):")
    print("\n" + header)
    if lines:
        for ln in lines:
            print(f"    {ln}")
    else:
        print(f"    (none of kind '{kind}')")


def run_text(passphrase: str | None) -> None:
    print(f"{_settings.assistant_name()} text mode. Type 'quit' / 'exit' / Ctrl-C to leave.")
    engine = JarvisMainEngine(stt="SKIP", tts="SKIP", memory_passphrase=passphrase)
    print()

    while True:
        try:
            text = input("You:   ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if not text:
            continue
        if text.lower() in {"quit", "exit", "q", ":q"}:
            print("Goodbye.")
            return
        if text.lower() in {":stats", "stats"}:
            for k, v in engine.feedback.stats().items():
                print(f"  {k}: {v}")
            continue
        if text.lower() in {":facts", "facts"}:
            facts = engine.memory.all_facts()
            print("  facts:" if facts else "  (no facts saved yet)")
            for k, v in facts.items():
                print(f"    {k}: {v}")
            continue
        if text.lower() in {":reminders", "reminders"}:
            if not engine.scheduler:
                print("  (scheduler not active)")
                continue
            upcoming = engine.scheduler.list_upcoming()
            if not upcoming:
                print("  (no upcoming reminders)")
            for r in upcoming:
                print(f"    [{r.fire_at:%I:%M %p, %d %b}] {r.message}")
            continue
        if text.lower() in {":skills", "skills"}:
            from core.skill_registry import all_skills
            sk = all_skills()
            print(f"  {len(sk)} plugin skills loaded:")
            for name, s in sk.items():
                print(f"    - {name}: {s.description or '(no description)'}")
            continue
        if text.lower().startswith(":vault on"):
            pw = getpass.getpass("New passphrase: ").strip()
            if not pw:
                print("  (cancelled — empty passphrase)")
                continue
            engine.memory.enable_vault(pw)
            print("  Memory vault enabled.")
            continue
        if text.lower() in {":help", "help", "?"}:
            print("  Commands: quit | :stats | :facts | :reminders | :skills | :vault on | :help")
            continue

        try:
            response = engine.process_text(text)
        except Exception as e:
            print(f"  [error] {e}", file=sys.stderr)
            continue
        print(f"{_settings.assistant_name()}: {response if response else '(silent)'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AERIS / Jarvis terminal entry point")
    parser.add_argument("--text", action="store_true", help="Text-only mode (no STT/TTS)")
    parser.add_argument("--wake", action="store_true",
                        help="Wake-word mode — passive listening for 'jarvis' / 'aeris'")
    parser.add_argument("--standby", action="store_true",
                        help="Always-on standby — Tier-0 wake tier, brain dormant "
                             "until woken (low-power OS layer)")
    parser.add_argument("--vault", action="store_true",
                        help="Prompt for memory vault passphrase before booting")
    parser.add_argument("--enable-autostart", action="store_true",
                        help="Register standby to launch at login, then exit")
    parser.add_argument("--disable-autostart", action="store_true",
                        help="Remove the login autostart entry, then exit")
    parser.add_argument("--standby-status", action="store_true",
                        help="Print offline standby status (config, lifetime, "
                             "autostart, readiness), then exit")
    parser.add_argument("--standby-journal", action="store_true",
                        help="Print the standby event journal, then exit")
    parser.add_argument("--kind", default=None,
                        help="Filter --standby-journal to one event kind "
                             "(wake / spinup / crash / breaker_open / control / …)")
    parser.add_argument("--limit", type=int, default=30,
                        help="Max events for --standby-journal (default 30)")
    parser.add_argument("--verbose", action="store_true", help="Enable INFO-level logging")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Offline status / journal are pure introspection — print and exit, no boot.
    if args.standby_status:
        run_standby_status()
        return 0

    if args.standby_journal:
        run_standby_journal(kind=args.kind, limit=args.limit)
        return 0

    # Autostart management is a quick registry touch — do it and exit, no boot.
    if args.enable_autostart or args.disable_autostart:
        from core.autostart import AutostartManager
        mgr = AutostartManager()
        if args.enable_autostart:
            cmd = mgr.enable()
            print(f"Autostart enabled — will launch at login:\n  {cmd}")
        else:
            print("Autostart disabled." if mgr.disable() else "Autostart was not set.")
        return 0

    passphrase = _maybe_passphrase(args.vault)

    if args.text:
        run_text(passphrase)
    elif args.standby:
        run_standby(passphrase)
    elif args.wake:
        run_wake(passphrase)
    else:
        run_voice(passphrase)
    return 0


if __name__ == "__main__":
    sys.exit(main())
