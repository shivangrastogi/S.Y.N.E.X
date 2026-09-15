"""Streaming endpointing + voice-activity policy for continuous listening.

The ChatGPT-style "always open mic, cut as soon as you stop talking" behaviour
needs two decisions made on a stream of audio chunks:

  * **Is this chunk speech?** — an energy gate so background hum doesn't look
    like talking (``is_speech``).
  * **Has the utterance ended?** — once we've seen speech, how much trailing
    silence means "they're done" so we finalise *now* instead of waiting out a
    fixed ``phrase_time_limit`` (the ``Endpointer`` state machine).

Both are pure logic driven by per-chunk inputs, so the whole endpointing policy
is unit-testable with synthetic frames — no mic, no Vosk. ``stt.listen_streaming``
and ``voice_engine``'s streaming path both drive an ``Endpointer``; the GUI shows
the live ``partial`` text and reacts to ``final``.
"""
from __future__ import annotations

import audioop
from dataclasses import dataclass
from typing import Optional


def is_speech(chunk: bytes, threshold: int = 500, width: int = 2) -> bool:
    """True if a PCM16 chunk's RMS energy is above ``threshold`` (i.e. voice,
    not room tone). Empty/short chunks are silence."""
    if not chunk:
        return False
    try:
        return audioop.rms(chunk, width) >= threshold
    except audioop.error:
        return False


@dataclass
class EndpointDecision:
    finalize: bool          # the utterance is complete — emit final now
    text: str               # best transcript so far (final text when finalize)
    changed: bool           # the partial text changed this update (redraw UI)


class Endpointer:
    """Decides when a streamed utterance is finished.

    Feed it the latest partial transcript each chunk via ``update``. A partial
    that *changed* resets the silence counter (the user is still talking). A
    partial that *didn't change* — or an explicit final from the recogniser —
    accrues silence; after ``max_silence_chunks`` of no change with non-empty
    speech captured, the utterance is endpointed.

    Chunk-count thresholds keep it sample-rate-agnostic: at 4000-frame /16 kHz
    chunks (~0.25 s) the default 8 ≈ 2 s of trailing silence; tune per UX.
    """

    def __init__(self, max_silence_chunks: int = 8, min_chars: int = 1):
        self.max_silence_chunks = max_silence_chunks
        self.min_chars = min_chars
        self.reset()

    def reset(self) -> None:
        self._last = ""
        self._silence = 0
        self._final = ""
        self._spoke = False

    @property
    def partial(self) -> str:
        return self._last

    def update(self, partial: str, *, is_final: bool = False) -> EndpointDecision:
        """Advance the state machine with the recogniser's latest output.

        ``is_final=True`` marks a hard final from the recogniser (Vosk
        ``Result()``), which endpoints immediately if non-trivial.
        """
        partial = (partial or "").strip().lower()

        if is_final:
            if len(partial) >= self.min_chars:
                self._final = partial
                return EndpointDecision(finalize=True, text=partial, changed=True)
            # Empty hard-final → the recogniser produced nothing final this
            # turn. Don't endpoint and don't discard the running partial; the
            # trailing-silence path can still finalise it later. (Matches the
            # original listen_streaming behaviour where an empty Result()
            # didn't break the loop.)
            return EndpointDecision(finalize=False, text=self._last, changed=False)

        if partial and partial != self._last:
            self._last = partial
            self._silence = 0
            self._spoke = True
            return EndpointDecision(finalize=False, text=partial, changed=True)

        # No change this chunk → trailing silence.
        if self._spoke and len(self._last) >= self.min_chars:
            self._silence += 1
            if self._silence >= self.max_silence_chunks:
                self._final = self._last
                return EndpointDecision(finalize=True, text=self._last, changed=False)
        return EndpointDecision(finalize=False, text=self._last, changed=False)

    @property
    def final_text(self) -> str:
        return self._final
