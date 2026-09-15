"""Regenerate docs/PRIVACY.md - what leaves this machine.

    python gen_privacy_doc.py

Modules with network access are discovered by scanning; what each sends is
hand-written in core/egress_registry.py. Exits non-zero if a module gained
network access without an entry, or an entry outlived its module - the two
ways a privacy document starts lying.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    from core.egress_registry import (
        discover_egress, remote_modules, render_markdown, stale, undocumented,
    )
    found = discover_egress()
    missing, gone = undocumented(found), stale(found)
    os.makedirs("docs", exist_ok=True)
    out = os.path.join("docs", "PRIVACY.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(found))
    print(f"wrote {out} - {len(found)} module(s) can reach the network")
    print(f"  always-on remote: {', '.join(remote_modules(found)) or 'none'}")
    if missing:
        print(f"  UNDOCUMENTED ({len(missing)}): {', '.join(missing)}")
        print("  -> describe them in core/egress_registry.py DESCRIPTIONS")
    if gone:
        print(f"  STALE ({len(gone)}): {', '.join(gone)}")
        print("  -> described but no longer network-capable; remove the entry")
    return 1 if (missing or gone) else 0


if __name__ == "__main__":
    raise SystemExit(main())
