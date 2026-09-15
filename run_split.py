"""AERIS split-architecture text driver — the brain runs in its OWN process.

This entry point is deliberately **ML-free**: it imports NO torch / sentence-
transformers / spaCy. It starts the Brain in a supervised child process
(auto-restarted if it dies) and talks to it over the service bus via
``RemoteBrain``. So a native crash in the brain can never take this process
down — you get a "reconnecting…" line and the supervisor brings the brain back.

Run it:
    "C:\\Users\\Shivang\\anaconda3\\python.exe" run_split.py

The REPL core (``run_repl``) takes injectable I/O + a started supervisor so it
is unit-tested with fakes (no spawn); ``main()`` wires the real pieces.
"""
from __future__ import annotations

import os
import sys
from typing import Callable

# Keep the driver process free of heavy math threads too (belt-and-suspenders).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_repl(read_line: Callable[[], "str | None"],
             write: Callable[[str], None],
             supervisor) -> None:
    """Drive one text session against a supervised brain. ``read_line`` returns
    the next input (or None on EOF); ``write`` emits a line; ``supervisor`` is a
    started Supervisor with a 'brain' service registered."""
    from core.remote_brain import RemoteBrain
    proxy = supervisor._svcs["brain"].proxy
    # supervisor owns restarts — but hibernation is a *deliberate* stop, so it
    # has to tell the supervisor to stand down for the duration (§4.2).
    rb = RemoteBrain(proxy=proxy, auto_restart=False,
                     suspend=lambda: supervisor.suspend("brain"),
                     resume=lambda: supervisor.resume("brain"))
    write("AERIS online — crash-isolated brain. Type 'quit' to exit.")
    if rb.start_idle_watch():
        st = rb.hibernation_status()
        write(f"(brain retires after {st['window_s']:.0f}s idle; "
              "the next line wakes it with the conversation intact)")
    try:
        while True:
            text = read_line()
            if text is None:
                break
            text = text.strip()
            if text.lower() in ("quit", "exit", "q"):
                break
            if not text:
                continue
            write("AERIS: " + rb.process_text(text))
            for ev in rb.poll_events():                 # proactive offers
                msg = (ev.payload or {}).get("text", "")
                if msg:
                    write("AERIS (proactive): " + msg)
    finally:
        rb.stop_idle_watch()


def main() -> int:
    from core.service_supervisor import Supervisor
    from core.brain_service import brain_handler_factory

    print("AERIS (split) — starting brain in its own process… (~30s cold)")
    sup = Supervisor()
    sup.register("brain", brain_handler_factory)
    started = sup.start_all(ready_timeout=300)
    if not started.get("brain"):
        print("Brain child failed to start. Check data/logs.")
        return 1
    sup.start_monitor()   # auto-restart the brain if it ever dies
    try:
        def _read():
            try:
                return input("You: ")
            except EOFError:
                return None
        run_repl(_read, print, sup)
    finally:
        sup.stop_all()
        print("bye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
