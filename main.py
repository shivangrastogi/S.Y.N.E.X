"""AERIS / Jarvis terminal entry point.

Two modes:

    python main.py              voice mode — uses STT + TTS, the production loop
    python main.py --text       text mode  — read stdin, print responses (no audio)
                                              great for dev or when audio deps
                                              aren't installed
    python main.py --verbose    enable debug logging

Both modes share the same JarvisMainEngine.process_text() pipeline; only the
input/output transport changes.

The PyQt GUI lives in `run_gui.py` (separate entry point). This file is the
terminal-first launcher.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.main_engine import JarvisMainEngine


def run_voice() -> None:
    print("AERIS voice mode. Press Ctrl-C to exit.")
    engine = JarvisMainEngine()
    engine.run()


def run_text() -> None:
    print("AERIS text mode. Type 'quit' / 'exit' / Ctrl-C to leave.")
    engine = JarvisMainEngine(stt="SKIP", tts="SKIP")
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
        if text.lower() in {":help", "help", "?"}:
            print("  Commands: quit | :stats | :facts | :help")
            continue

        try:
            response = engine.process_text(text)
        except Exception as e:
            print(f"  [error] {e}", file=sys.stderr)
            continue
        print(f"AERIS: {response if response else '(silent)'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AERIS / Jarvis terminal entry point",
    )
    parser.add_argument(
        "--text", action="store_true",
        help="Text-only mode (no STT/TTS, read stdin, print stdout)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable INFO-level logging from core modules",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.text:
        run_text()
    else:
        run_voice()
    return 0


if __name__ == "__main__":
    sys.exit(main())
