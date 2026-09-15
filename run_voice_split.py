"""Voice-in-its-own-process harness — the live check before the GUI cutover,
counterpart to ``run_split.py`` (brain) and ``run_vision_split.py`` (vision).

This process imports **no PyAudio, no speech_recognition, no vosk, no pygame
and no PyQt5**. It spawns the voice service, lets you speak and be spoken to,
and prints what crosses the bus — so you can confirm on the real machine that:

  * speech is still recognised with the mic in another process,
  * AERIS still speaks with the speaker in another process,
  * wake/sleep still behaves ("jarvis sleep" … "ok jarvis"),
  * **speaking alone never opens the microphone**,
  * and shutting down leaves no audio stack resident.

    python run_voice_split.py            # speak, then listen
    python run_voice_split.py --say-only # prove speech needs no mic

``watch`` is injectable so the loop is unit-tested with a fake; ``main()``
wires the real service.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Callable

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def watch(voice, write: Callable[[str], None],
          should_stop: Callable[[], bool],
          poll_s: float = 0.15, sleep_fn=time.sleep) -> int:
    """Drain transcripts and state changes until ``should_stop()``.

    Returns how many utterances were recognised. Every signal comes from ONE
    `voice.poll()` — draining the queue twice would lose whichever ran second.
    """
    heard = 0
    while not should_stop():
        got = voice.poll()
        if got.state:
            write(f"  [state] {got.state}")
        for part in got.partials:              # only in streaming mode
            write(f"  …{part}")
        for text in got.transcripts:
            heard += 1
            write(f"  you said: {text}")
        sleep_fn(poll_s)
    return heard


def main(argv=None) -> int:
    from core.remote_voice import RemoteVoice

    argv = list(sys.argv[1:] if argv is None else argv)
    say_only = "--say-only" in argv

    print("Starting the voice service in its own process… "
          "(this process holds no audio libraries)")
    rv = RemoteVoice()

    if not rv.speak("Namaste sir, main alag process se bol raha hoon."):
        print(f"Could not speak: {rv.last_error}")
        return 1
    print("Spoke OK.")
    st = rv.status()
    print(f"  status after speaking: {st}")
    if st.get("mic_open"):
        print("  !! the microphone opened just to speak - that is a bug")
    else:
        print("  OK: microphone still closed - speech did not open it")

    if say_only:
        rv.shutdown()
        print("Voice service stopped.")
        return 0

    if not rv.listen():
        print(f"Could not start listening: {rv.last_error}")
        rv.shutdown()
        return 1
    print("Listening. Say something; try 'jarvis sleep' then 'ok jarvis'. "
          "Press Enter to stop.")

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
        print(f"{n} utterance(s) recognised.")
    finally:
        rv.shutdown()
        print("Voice service stopped — no audio stack resident.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
