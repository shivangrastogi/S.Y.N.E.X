"""AERIS / Jarvis terminal entry point.

Modes:

    python main.py              voice mode — STT + TTS, single-shot listening loop
    python main.py --wake       wake-word mode — Vosk listens passively, fires on
                                "hey jarvis" / "hey aeris" / "jarvis" / "aeris"
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    print("AERIS voice mode. Press Ctrl-C to exit.")
    engine = JarvisMainEngine(memory_passphrase=passphrase)
    engine.run()


def run_wake(passphrase: str | None) -> None:
    """Wake-word mode: passively listen via Vosk, dispatch one turn per wake."""
    from core.wake_word import WakeWordDetector

    print("AERIS wake mode. Initialising brain...")
    engine = JarvisMainEngine(memory_passphrase=passphrase)

    try:
        detector = WakeWordDetector(_WAKE_MODEL_PATH)
    except FileNotFoundError as e:
        print(f"\nWake word detector failed to start:\n  {e}\n")
        print("Falling back to standard voice mode.")
        engine.run()
        return

    engine._ensure_io()
    engine._speak("AERIS standing by, sir.")
    print("\nSay 'Hey Jarvis' or 'AERIS' to activate. Ctrl-C to exit.\n")

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


def run_text(passphrase: str | None) -> None:
    print("AERIS text mode. Type 'quit' / 'exit' / Ctrl-C to leave.")
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
        print(f"AERIS: {response if response else '(silent)'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AERIS / Jarvis terminal entry point")
    parser.add_argument("--text", action="store_true", help="Text-only mode (no STT/TTS)")
    parser.add_argument("--wake", action="store_true",
                        help="Wake-word mode — passive listening for 'jarvis' / 'aeris'")
    parser.add_argument("--vault", action="store_true",
                        help="Prompt for memory vault passphrase before booting")
    parser.add_argument("--verbose", action="store_true", help="Enable INFO-level logging")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    passphrase = _maybe_passphrase(args.vault)

    if args.text:
        run_text(passphrase)
    elif args.wake:
        run_wake(passphrase)
    else:
        run_voice(passphrase)
    return 0


if __name__ == "__main__":
    sys.exit(main())
