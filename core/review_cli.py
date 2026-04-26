"""Interactive review tool for low-confidence utterances.

Usage:
    python -m core.review_cli

For each pending utterance, shows the brain's top-3 guesses and lets you:
    1 / 2 / 3      - approve as the matching intent
    <intent_name>  - approve under any other existing intent
    s              - skip (leave pending; revisit later)
    r              - reject (mark resolved, do not add to intents.json)
    l              - list known intents
    q              - quit

Approved utterances are appended to data/intents.json under the chosen intent.
The brain's k-NN index will rebuild automatically the next time Jarvis boots
because the intents.json hash changes.
"""

from __future__ import annotations

import json
import os
import sys

from core.feedback import FeedbackStore

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_INTENTS_PATH = os.path.join(_ROOT, "data", "intents.json")
_DB_PATH = os.path.join(_ROOT, "data", "feedback_log.sqlite")


def _load_intent_names() -> list[str]:
    if not os.path.exists(_INTENTS_PATH):
        return []
    with open(_INTENTS_PATH, "r", encoding="utf-8") as f:
        return sorted(json.load(f).keys())


def _print_pending(p, intent_names: list[str]) -> None:
    print()
    print("─" * 64)
    print(f"  ID    : {p.id}")
    print(f"  Text  : {p.raw_text!r}")
    print(f"  Queued: {p.queued_at}")
    print(f"  Top guesses:")
    for i, (intent, conf) in enumerate(p.top3[:3], start=1):
        marker = " (known)" if intent in intent_names else " (UNKNOWN)"
        print(f"    [{i}] {intent:18s}  conf={conf:.3f}{marker}")
    print()


def _prompt() -> str:
    print("  Choose: [1/2/3] approve, <intent_name> approve, "
          "[s]kip, [r]eject, [l]ist intents, [q]uit")
    return input("  > ").strip()


def main() -> int:
    fb = FeedbackStore(_DB_PATH)
    intent_names = _load_intent_names()

    pending = fb.pending_patterns()
    if not pending:
        print("No pending patterns. Brain has nothing to learn from yet — keep using Jarvis.")
        fb.close()
        return 0

    print(f"\n{len(pending)} pending utterance(s) awaiting review.")

    for p in pending:
        # Refresh intent list each iteration in case earlier approvals
        # (or external edits) changed it.
        intent_names = _load_intent_names()
        _print_pending(p, intent_names)

        while True:
            try:
                choice = _prompt()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                fb.close()
                return 0

            if not choice:
                continue
            if choice in ("q", "Q", "quit", "exit"):
                fb.close()
                return 0
            if choice in ("s", "skip"):
                fb.skip_pattern(p.id)
                print("  -> skipped")
                break
            if choice in ("r", "reject"):
                fb.reject_pattern(p.id)
                print("  -> rejected")
                break
            if choice in ("l", "list"):
                print("  Known intents: " + ", ".join(intent_names))
                continue
            if choice in ("1", "2", "3"):
                idx = int(choice) - 1
                if idx >= len(p.top3):
                    print("  No top-N candidate at that slot.")
                    continue
                target = p.top3[idx][0]
                if target not in intent_names:
                    print(f"  '{target}' is not a known intent.")
                    continue
                ok = fb.approve_pattern(p.id, target, _INTENTS_PATH)
                print(f"  -> approved as '{target}'" if ok else "  -> failed")
                break
            # Treat anything else as a literal intent name
            if choice in intent_names:
                ok = fb.approve_pattern(p.id, choice, _INTENTS_PATH)
                print(f"  -> approved as '{choice}'" if ok else "  -> failed")
                break
            print(f"  '{choice}' is not a known intent. Use 'l' to list, "
                  "or pick 1/2/3, or s/r/q.")

    print("\nDone. Restart Jarvis to pick up the new patterns.")
    fb.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
