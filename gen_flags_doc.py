"""Regenerate docs/FLAGS.md from the source.

    python gen_flags_doc.py

Flags are discovered by scanning, so this cannot silently miss one;
descriptions live in `core/flag_registry.py`. Exits non-zero if a discovered
flag has no description, or a described flag no longer exists — the same two
ways a generated doc starts lying.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    from core.flag_registry import discover_flags, render_markdown, stale, undocumented

    flags = discover_flags()
    missing, gone = undocumented(flags), stale(flags)
    out = os.path.join("docs", "FLAGS.md")
    os.makedirs("docs", exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(flags))
    print(f"wrote {out} - {len(flags)} flags discovered")
    if missing:
        print(f"  UNDOCUMENTED ({len(missing)}): {', '.join(missing)}")
        print("  -> add them to DESCRIPTIONS in core/flag_registry.py")
    if gone:
        print(f"  STALE ({len(gone)}): {', '.join(gone)}")
        print("  -> described but not found in the source; remove or re-add")
    return 1 if (missing or gone) else 0


if __name__ == "__main__":
    raise SystemExit(main())
