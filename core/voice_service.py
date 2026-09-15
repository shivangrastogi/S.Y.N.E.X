"""Voice — mic and speaker — in their own process (P1, the other half of
§6.23; §6.25).

I deferred this in §6.23 with a stated objection, and the objection was wrong.
It said: the "isolate a stack where its output is smaller than its input" rule
made vision easy, but voice's output is a live audio stream, so the same bus
shape would not work. That is only true if you put the boundary in the wrong
place. Look at both directions separately:

| direction | in | out | verdict |
| --- | --- | --- | --- |
| STT | audio (huge, continuous) | text (tiny) | output ≪ input ✔ |
| TTS | text (tiny) | audio (huge) | output ≫ input ✘ |

TTS fails the test — *if the parent is the one that plays the audio*. Give the
child the **speaker as well as the microphone** and neither direction carries
audio at all:

```
  parent → child   speak {"text": "..."}          ~50 bytes
  child  → parent  event:transcript {"text": "…"} ~50 bytes
  audio  ────────  never crosses; it is captured and played in the child
```

So the rule held; I had mis-drawn the boundary, not found its limit. The
general form is sharper for it: **isolate a stack where the boundary can be
placed so that everything crossing it is small** — which usually means putting
*both* ends of a device pipeline on the same side.

### Barge-in gets better, not worse

The other stated worry was latency: barge-in needs to be tighter than the
150 ms polling the vision seam settled for. But barge-in is mic-versus-speaker,
and once both are in the same child it is decided *locally, with zero IPC* —
strictly faster than today, where the check competes for the GIL with torch in
the same process. And an explicit interrupt from the parent is a direct
`stop_speaking` request, not something polled.

This is why P4's "voice-first, low-latency … needs the process split so audio
isn't GIL-blocked by torch" is unblocked by this file rather than complicated
by it.

### What this file does NOT do

It does not touch the voice *models*. Google en-IN STT and edge-tts Neerja are
hand-picked and tuned for Hinglish; `core/stt.py` and `core/tts.py` are used
exactly as they are, and the wake/sleep policy is re-used verbatim from
`core/voice_modes.py` rather than re-implemented. This is integration work
around a tuned stack, deliberately.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable, Optional

from core.voice_modes import ACTIVE, SLEEPING, STOPPED, decide, prefer_offline

log = logging.getLogger(__name__)

# A capture loop that keeps failing must back off rather than spin on a dead
# device — same shape as ContinuousVoiceEngine._loop, which surfaces the error
# and gives up after several consecutive failures.
MAX_CONSEC_ERRORS = 5
ERROR_BACKOFF_S = 0.5


def _default_stt():
    from core.stt import STT
    return STT()


ENV_STREAMING = "AERIS_VOICE_STREAMING"


def streaming_enabled(environ: Optional[dict] = None) -> bool:
    """Read ``AERIS_VOICE_STREAMING``. Off unless explicitly enabled.

    Off by default for a reason that is about the *models*, not the plumbing.
    `STT.listen_streaming` runs on Vosk end-to-end — it is the offline path —
    so its FINAL transcript never reaches Google en-IN, which is the
    hand-picked Hinglish recogniser the normal path uses. Turning streaming on
    therefore trades recognition quality for latency and live partials.

    That is a decision about a tuned voice stack, so it is the user's to make,
    not a default to slip in. Everything else here is integration work around
    the models; this flag is the one place the choice is exposed.
    """
    raw = (environ if environ is not None else os.environ).get(ENV_STREAMING, "")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def stt_listen_streaming(stt: Any, on_partial: Callable[[str], None]) -> str:
    """One utterance with live partials. Returns the final text.

    Degrades to `stt_listen` when the recogniser has no streaming mode — and
    note `STT.listen_streaming` itself already falls back to `listen()` when
    the Vosk model or PyAudio is missing, so a machine without them keeps
    working with no partials rather than failing.

    Streaming is inherently offline here, which means the SLEEPING privacy
    preference (§6.28) is satisfied for free on this path.
    """
    fn = getattr(stt, "listen_streaming", None)
    if not callable(fn):
        return stt_listen(stt, False)
    try:
        return fn(on_partial=on_partial) or ""
    except TypeError:
        # An older signature — take the final only rather than lose the turn.
        log.debug("[voice_service] listen_streaming signature mismatch")
        return fn() or ""


def stt_listen(stt: Any, offline: bool) -> str:
    """Capture one utterance, honouring the offline preference.

    A module-level adapter rather than a closure so the forwarding is
    directly testable. It needs to be: an earlier cut called `listen()` and
    dropped the flag, so a SLEEPING AERIS still shipped the room's audio to
    Google to check for a wake word — the loop computed the preference and
    nothing acted on it.

    Tolerant of an STT build without the parameter, which then behaves as it
    always did (online-first) rather than raising.
    """
    fn = getattr(stt, "listen", None)
    if not callable(fn):
        return ""
    try:
        return fn(prefer_offline=offline) or ""
    except TypeError:
        log.debug("[voice_service] STT.listen has no prefer_offline")
        return fn() or ""


def _default_tts():
    from core.tts import TTS
    return TTS()


class VoiceLoop:
    """The capture loop, with every device dependency injected.

    ``listen_once(prefer_offline: bool) -> str`` returns one transcript (or
    "" on silence). ``emit(kind, payload)`` publishes upward. Both injected,
    so the entire wake/sleep/deliver behaviour is unit-tested with a scripted
    fake microphone — no PyAudio, no models, no sound card, no sleeping.
    """

    def __init__(self, listen_once: Callable[[bool], str],
                 emit: Optional[Callable[[str, dict], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None,
                 sleep_fn: Callable[[float], None] = time.sleep,
                 is_speaking: Optional[Callable[[], bool]] = None,
                 interrupt: Optional[Callable[[], Any]] = None,
                 listen_streaming: Optional[Callable[[Callable[[str], None]], str]] = None):
        self._listen_once = listen_once
        self._emit = emit
        self._on_error = on_error
        self._sleep = sleep_fn
        # Opt-in live partials (AERIS_VOICE_STREAMING). When wired, this
        # REPLACES `listen_once` for the capture call — the streaming path is
        # Vosk end-to-end and produces its own final, so running both would
        # mean capturing the same utterance twice.
        self._listen_streaming = listen_streaming
        self.partials = 0
        # Barge-in: mic and speaker are in the same process precisely so this
        # can be decided here, with no IPC (§6.25).
        self._is_speaking = is_speaking
        self._interrupt = interrupt
        self.barge_ins = 0
        self.state = STOPPED
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.transcripts = 0
        self.errors = 0

    # ── one pass, the testable unit ──────────────────────────────────
    def step(self) -> Optional[str]:
        """Capture one utterance and apply the mode policy.

        Returns the transcript that should reach the brain, or ``None``.
        Never raises: this runs on the capture thread, where an escaping
        exception costs the user their microphone until restart.
        """
        try:
            if self._listen_streaming is not None:
                text = self._listen_streaming(self._on_partial)
            else:
                text = self._listen_once(prefer_offline(self.state))
        except Exception as e:
            self.errors += 1
            log.debug("[voice_service] capture error: %s", e)
            if self._on_error:
                try:
                    self._on_error(str(e))
                except Exception:
                    pass
            return None

        # Barge-in comes BEFORE the mode policy, and applies in every state.
        # The user talking over AERIS means "stop talking" whether or not the
        # words turn out to be a command — and even while asleep, where the
        # transcript itself will be discarded. Deciding it here costs no IPC;
        # routing it through the parent would add a poll interval to the one
        # interaction where latency is most obvious.
        if (text or "").strip() and self._is_speaking is not None:
            try:
                if self._is_speaking():
                    if self._interrupt is not None:
                        self._interrupt()
                    self.barge_ins += 1
                    self._publish("barge_in", {"text": text})
            except Exception as e:
                log.debug("[voice_service] barge-in failed: %s", e)

        d = decide(self.state, text or "")
        if d.state != self.state:
            self.state = d.state
            self._publish("voice_state", {"state": self.state})
        if d.event:
            self._publish(f"voice_{d.event}", {})
        if d.deliver:
            self.transcripts += 1
            self._publish("transcript", {"text": text, "state": self.state})
            return text
        return None

    def _on_partial(self, text: str) -> None:
        """A partial transcript, mid-utterance. Published for live display
        only — never delivered as a command, because it is by definition an
        unfinished sentence and acting on half of one is worse than waiting.

        Suppressed while SLEEPING: a sleeping AERIS showing a running
        transcript of the room would be the same privacy leak as §6.28 in a
        different coat.
        """
        text = (text or "").strip()
        if not text or self.state == SLEEPING:
            return
        self.partials += 1
        self._publish("partial", {"text": text})

    def _publish(self, kind: str, payload: dict) -> None:
        if self._emit is None:
            return
        try:
            self._emit(kind, payload)
        except Exception as e:
            log.debug("[voice_service] emit failed: %s", e)

    # ── lifecycle ────────────────────────────────────────────────────
    def start(self, state: str = ACTIVE) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop.clear()
        self.state = state
        self._publish("voice_state", {"state": self.state})

        def _run():
            consec = 0
            while not self._stop.is_set():
                before = self.errors
                self.step()
                if self.errors > before:
                    consec += 1
                    if consec >= MAX_CONSEC_ERRORS:
                        log.warning("[voice_service] giving up after %d "
                                    "consecutive capture errors", consec)
                        break
                    self._sleep(ERROR_BACKOFF_S)
                else:
                    consec = 0
            if self.state != STOPPED:
                self.state = STOPPED
                self._publish("voice_state", {"state": STOPPED})

        self._thread = threading.Thread(target=_run, name="voice-capture",
                                        daemon=True)
        self._thread.start()
        return True

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None:
            t.join(timeout)
        self.state = STOPPED

    def set_state(self, state: str) -> str:
        """Force ACTIVE/SLEEPING from the parent (the GUI's mic toggle)."""
        if state in (ACTIVE, SLEEPING) and state != self.state:
            self.state = state
            self._publish("voice_state", {"state": state})
        return self.state


class SpeechPlayer:
    """Speaks on a worker thread, so the service loop stays answerable.

    This is not a nicety. `core.service_bus._service_loop` is single-threaded:
    it pulls one request, calls the handler, and only then reads the next. A
    blocking `speak()` would therefore park the whole service for the length of
    the utterance — and the very request that arrives during an utterance is
    `stop_speaking`. Barge-in would have been queued behind the speech it was
    meant to interrupt.

    So `say()` starts playback and returns; `stop()` cuts it. The TTS object is
    injected, so this tests with a fake speaker and no sound card.
    """

    def __init__(self, tts_factory: Callable[[], Any]):
        self._factory = tts_factory
        self._tts: Any = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self.spoken = 0
        self.interrupted = 0
        self.last_error: str = ""

    def _engine(self) -> Any:
        if self._tts is None:
            self._tts = self._factory()
        return self._tts

    def is_speaking(self) -> bool:
        t = self._tts
        if t is None:
            return False
        probe = getattr(t, "is_speaking", None)
        if callable(probe):
            try:
                return bool(probe())
            except Exception:
                return False
        return bool(self._thread is not None and self._thread.is_alive())

    def say(self, text: str) -> bool:
        with self._lock:
            # A new utterance supersedes the one in flight rather than
            # overlapping it — two voices at once is never what was wanted.
            if self.is_speaking():
                self.stop()
            engine = self._engine()

            def _run():
                try:
                    engine.speak(text)
                    self.spoken += 1
                except Exception as e:
                    self.last_error = repr(e)
                    log.warning("[voice_service] speak failed: %s", e)

            self._thread = threading.Thread(target=_run, name="voice-speak",
                                            daemon=True)
            self._thread.start()
            return True

    def stop(self) -> bool:
        t = self._tts
        if t is None:
            return False
        stopper = getattr(t, "stop", None)
        if not callable(stopper):
            return False
        try:
            if stopper():
                self.interrupted += 1
                return True
        except Exception as e:
            log.debug("[voice_service] tts stop raised: %s", e)
        return False


def make_voice_handler(stt_builder: Optional[Callable] = None,
                       tts_builder: Optional[Callable] = None,
                       emit: Optional[Callable[[str, dict], None]] = None,
                       loop: Optional[VoiceLoop] = None):
    """Build the request handler.

    STT and TTS are built **lazily**, unlike `brain_service`'s eager engine:
    this child may be spawned for speech alone (a reply to read out) and
    should not open the microphone — a live mic nobody asked for is a
    privacy cost, not just a resource one.
    """
    box: dict[str, Any] = {"stt": None, "loop": loop}
    lock = threading.RLock()
    player = SpeechPlayer(tts_builder or _default_tts)

    def _stt():
        if box["stt"] is None:
            box["stt"] = (stt_builder or _default_stt)()
        return box["stt"]

    def _loop() -> VoiceLoop:
        if box["loop"] is None:
            def _listen_once(offline: bool) -> str:
                return stt_listen(_stt(), offline)

            stream = None
            if streaming_enabled():
                def stream(on_partial):        # noqa: F811 - deliberate
                    return stt_listen_streaming(_stt(), on_partial)
                log.info("[voice_service] streaming partials ON "
                         "(Vosk end-to-end — no Google en-IN final)")

            box["loop"] = VoiceLoop(_listen_once, emit=emit,
                                    is_speaking=player.is_speaking,
                                    interrupt=player.stop,
                                    listen_streaming=stream)
        return box["loop"]

    # A loop handed in by a caller/test still gets barge-in wired to this
    # player, so the injected-loop path and the built-one behave alike.
    if box["loop"] is not None:
        if getattr(box["loop"], "_is_speaking", None) is None:
            box["loop"]._is_speaking = player.is_speaking
            box["loop"]._interrupt = player.stop

    def _status() -> dict:
        lp = box["loop"]
        return {"state": lp.state if lp else STOPPED,
                "listening": bool(lp and lp.state in (ACTIVE, SLEEPING)),
                "transcripts": lp.transcripts if lp else 0,
                "errors": lp.errors if lp else 0,
                "barge_ins": lp.barge_ins if lp else 0,
                "partials": lp.partials if lp else 0,
                "streaming": bool(lp and lp._listen_streaming is not None),
                "speaking": player.is_speaking(),
                "interrupted": player.interrupted,
                "mic_open": box["stt"] is not None,
                "speaker_ready": player._tts is not None}

    def handler(kind: str, payload: dict) -> dict:
        if kind == "ping":
            return {"pong": True}
        if kind == "status":
            return _status()
        if kind == "listen_start":
            state = (payload or {}).get("state") or ACTIVE
            with lock:
                ok = _loop().start(state=state)
            return {"ok": bool(ok), **_status()}
        if kind == "listen_stop":
            with lock:
                if box["loop"] is not None:
                    box["loop"].stop()
            return {"ok": True, **_status()}
        if kind == "set_state":
            with lock:
                return {"ok": True,
                        "state": _loop().set_state((payload or {}).get("state") or ACTIVE)}
        if kind == "speak":
            text = ((payload or {}).get("text") or "").strip()
            if not text:
                return {"ok": False, "reason": "nothing to say"}
            # Returns as soon as playback STARTS, not when it finishes — see
            # SpeechPlayer. "ok" means "speaking", not "spoke".
            try:
                player.say(text)
            except Exception as e:
                return {"ok": False, "error": repr(e)}
            return {"ok": True, "speaking": True}
        if kind == "stop_speaking":
            # Barge-in. The capture loop already does this locally the moment
            # it hears the user; this request is the parent's explicit
            # interrupt (a stop button, or a new command arriving).
            return {"ok": player.stop()}
        return {"error": f"unknown kind {kind!r}"}

    return handler


def voice_handler_factory(emit=None):
    """Top-level emit-aware factory for ServiceProxy(spawn)."""
    return make_voice_handler(emit=emit)
