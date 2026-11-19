"""Make template sentences look like real speech-to-text output.

Real transcripts (2026-10-17 phone log): "I want to do send a WhatsApp
message on this number 7300 978845 hi" — fillers, odd grammar, no
punctuation, numbers in groups. Templates are too clean; this module adds
the mess back.

Noise is applied ONLY to literal segments. Slot segments (names, numbers,
message text) pass through untouched, so labels stay exactly grounded.
"""
from __future__ import annotations

import random

from .expand import Seg, tidy

WAKE = {"en": ["hey aeris", "aeris", "hey jarvis", "jarvis", "ok aeris", "hi aeris"],
        "hi": ["aeris", "jarvis", "hey aeris", "suno aeris", "aeris suno"]}
PREFIX = {"en": ["um", "so", "okay", "ok", "please", "hey", "uh", "alright", "quickly"],
          "hi": ["yaar", "suno", "acha", "please", "zara", "bhai", "arre", "accha suno", "ek kaam karo"]}
SUFFIX = {"en": ["please", "for me", "now", "right now", "thanks", "thank you", "quickly", "asap"],
          "hi": ["please", "yaar", "na", "jaldi", "abhi", "plz", "jaldi se", "bhai"]}

# STT confusions / spoken variants seen with Google en-IN
SWAPS = {
    "whatsapp": ["whats app", "what's app", "watsapp"],
    "youtube": ["you tube"],
    "torch": ["touch", "torch light"],
    "flashlight": ["flash light"],
    "alarm": ["alarm clock"],
    "message": ["msg", "massage"],
    "screenshot": ["screen shot"],
    "volume": ["sound"],
    "call": ["kol", "cal"],
    "please": ["plz", "pls"],
    "karo": ["kro", "karna"],
    "kar do": ["kardo", "kr do"],
    "hai": ["h", "he"],
    "nahi": ["nhi", "nahin"],
    "bhejo": ["bhej", "bhejdo"],
    "kya": ["kia"],
    "you": ["u"],
}
DROPPABLE = {"the", "a", "an", "to", "please", "my", "ko", "pe", "ki"}


def _noise_literal(text: str, rng: random.Random, p: float) -> str:
    words = text.split(" ")
    out = []
    for w in words:
        lw = w.lower()
        r = rng.random()
        if lw in SWAPS and r < p:
            out.append(rng.choice(SWAPS[lw]))
        elif lw in DROPPABLE and r < p * 0.5:
            continue  # STT dropped a small word
        elif r < p * 0.08 and w:
            out += [w, w]  # stutter / duplicated word
        else:
            out.append(w)
    return " ".join(out)


def augment(segs: list[Seg], rng: random.Random, lang: str,
            strength: float = 1.0) -> list[Seg]:
    """Return a noisier copy. strength 0 = untouched."""
    if strength <= 0:
        return segs
    p = 0.12 * strength
    out = [Seg(_noise_literal(s.text, rng, p)) if s.slot is None else s
           for s in segs]
    if rng.random() < 0.25 * strength:
        out.insert(0, Seg(rng.choice(WAKE[lang]) + rng.choice([" ", ", "])))
    elif rng.random() < 0.2 * strength:
        out.insert(0, Seg(rng.choice(PREFIX[lang]) + " "))
    if rng.random() < 0.18 * strength:
        out.append(Seg(" " + rng.choice(SUFFIX[lang])))
    return casing(tidy(out), rng)


def casing(segs: list[Seg], rng: random.Random) -> list[Seg]:
    """STT casing styles: all-lower (most), Capitalised first word, or as-is.
    Slots keep their own casing (a name stays 'Ravi')."""
    style = rng.random()
    out = []
    for i, s in enumerate(segs):
        t = s.text
        if s.slot is None:
            t = t.replace(",", "") if rng.random() < 0.5 else t
            if style < 0.6:
                t = t.lower()
            elif style < 0.85 and i == 0 and t:
                t = t[0].upper() + t[1:]
        out.append(Seg(t, s.slot))
    if rng.random() < 0.1 and out and out[-1].slot is None:
        out[-1] = Seg(out[-1].text.rstrip() + rng.choice([".", "?", "!"]), None)
    return tidy(out)
