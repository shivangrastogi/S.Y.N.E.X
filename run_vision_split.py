"""Vision-in-its-own-process harness — the live validation for P1's vision
split, the same way ``run_split.py`` is for the brain.

This process imports **no MediaPipe and no OpenCV**. It spawns the vision
service, turns gestures on, and prints every gesture the child recognises. So
you can confirm on the real machine that:

  * gestures still work with the camera stack in another process,
  * the GUI process would carry none of it,
  * "gestures off" really returns the memory (the child exits),

before anything touches ``main_window``. Run it, wave at the camera, press
Enter to stop.

    python run_vision_split.py

``watch`` is injectable so the loop is unit-testable with a fake; ``main()``
wires the real service.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Callable

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def watch(vision, write: Callable[[str], None],
          should_stop: Callable[[], bool],
          poll_s: float = 0.15, sleep_fn=time.sleep) -> int:
    """Drain recognised gestures until ``should_stop()``. Returns the count.

    The poll interval is the only latency this seam adds on top of in-process
    gestures — 150 ms between a wave and the print, against ~30 ms of capture
    and inference. A GUI would hang this on its existing event-loop timer
    rather than a sleep, which costs nothing extra.
    """
    seen = 0
    while not should_stop():
        for name in vision.poll_gestures():
            seen += 1
            write(f"  gesture: {name}")
        sleep_fn(poll_s)
    return seen


def main() -> int:
    from core.remote_vision import RemoteVision

    print("Starting the vision service in its own process… "
          "(this process holds no MediaPipe)")
    rv = RemoteVision()
    if not rv.enable():
        print(f"Could not start vision: {rv.last_error}")
        return 1
    print(f"Vision up: {rv.status()}")
    print("Wave at the camera. Press Enter to stop.")

    import threading
    done = threading.Event()

    def _wait_for_enter():
        try:
            input()
        except EOFError:
            pass
        done.set()

    threading.Thread(target=_wait_for_enter, daemon=True).start()
    try:
        n = watch(rv, print, done.is_set)
        print(f"{n} gesture(s) recognised.")
    finally:
        rv.disable()          # stops capture AND kills the child
        print("Vision service stopped — MediaPipe is out of memory entirely.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
