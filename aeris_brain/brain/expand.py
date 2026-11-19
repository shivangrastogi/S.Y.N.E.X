"""Tiny template grammar with span tracking.

    "(set|put) [an] alarm (for|at) {time}"

    (a|b|c)  choose one alternative (nestable)
    [x]      optional — included with probability 0.5 (use [(a|b)] for a
             choice inside an optional)
    (a|b)?   same as [(a|b)]
    {slot}   a slot, filled by the caller

`sample()` returns a list of Segments: plain text, or a slot with its value.
Keeping slots as separate segments lets augmentation add noise to the
words AROUND a slot without ever touching the slot text — so the label
(which copies the slot text) always stays exactly grounded in the sentence.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Seg:
    text: str
    slot: str | None = None  # slot name if this segment is a filled slot


class _Node:
    def sample(self, rng, fill) -> list[Seg]:
        raise NotImplementedError


class _Lit(_Node):
    def __init__(self, s): self.s = s
    def sample(self, rng, fill): return [Seg(self.s)] if self.s else []


class _Slot(_Node):
    def __init__(self, name): self.name = name
    def sample(self, rng, fill): return [Seg(fill(self.name), self.name)]


class _Seq(_Node):
    def __init__(self, parts): self.parts = parts
    def sample(self, rng, fill):
        out = []
        for p in self.parts:
            out += p.sample(rng, fill)
        return out


class _Alt(_Node):
    def __init__(self, options): self.options = options
    def sample(self, rng, fill): return rng.choice(self.options).sample(rng, fill)


class _Opt(_Node):
    def __init__(self, inner): self.inner = inner
    def sample(self, rng, fill):
        return self.inner.sample(rng, fill) if rng.random() < 0.5 else []


class Template:
    """A parsed template. Parse once, sample many times."""

    def __init__(self, src: str):
        self.src = src
        self._pos = 0
        self._root = self._seq(end=None)
        if self._pos != len(src):
            raise ValueError(f"unbalanced template: {src!r}")
        self.slots = set(re.findall(r"\{(\w+)\}", src))

    # recursive-descent parser -------------------------------------------
    def _seq(self, end: str | None) -> _Node:
        """Parse until `end` (')' or ']' or '|' handled by caller)."""
        parts, buf = [], []
        s = self.src
        while self._pos < len(s):
            c = s[self._pos]
            if end is not None and c in ")]|":
                break
            if c == "(":
                self._flush(buf, parts)
                self._pos += 1
                opts = [self._seq(end=")")]
                while self._pos < len(s) and s[self._pos] == "|":
                    self._pos += 1
                    opts.append(self._seq(end=")"))
                self._expect(")")
                node = _Alt(opts)
                # "(x)?" — regex-style optional group, same as "[x]"
                if self._pos < len(s) and s[self._pos] == "?":
                    self._pos += 1
                    node = _Opt(node)
                parts.append(node)
            elif c == "[":
                self._flush(buf, parts)
                self._pos += 1
                inner = self._seq(end="]")
                self._expect("]")
                parts.append(_Opt(inner))
            elif c == "{":
                self._flush(buf, parts)
                j = s.index("}", self._pos)
                parts.append(_Slot(s[self._pos + 1:j]))
                self._pos = j + 1
            elif c in ")]|":
                raise ValueError(f"stray {c!r} in {s!r}")
            else:
                buf.append(c)
                self._pos += 1
        self._flush(buf, parts)
        return _Seq(parts)

    def _expect(self, ch):
        if self._pos >= len(self.src) or self.src[self._pos] != ch:
            raise ValueError(f"expected {ch!r} in {self.src!r}")
        self._pos += 1

    @staticmethod
    def _flush(buf, parts):
        if buf:
            parts.append(_Lit("".join(buf)))
            buf.clear()

    # sampling -----------------------------------------------------------
    def sample(self, rng: random.Random, fill) -> list[Seg]:
        """fill(slot_name) -> value string."""
        return tidy(self._root.sample(rng, fill))


_SPACES = re.compile(r"\s+")


def tidy(segs: list[Seg]) -> list[Seg]:
    """Merge adjacent literals and normalise whitespace (optional groups
    leave double spaces behind)."""
    merged: list[Seg] = []
    for s in segs:
        if s.slot is None and merged and merged[-1].slot is None:
            merged[-1] = Seg(merged[-1].text + s.text)
        else:
            merged.append(s)
    out = []
    for i, s in enumerate(merged):
        t = _SPACES.sub(" ", s.text) if s.slot is None else s.text
        if i == 0:
            t = t.lstrip()
        if i == len(merged) - 1:
            t = t.rstrip()
        if t:
            out.append(Seg(t, s.slot))
    return out


def join(segs: list[Seg]) -> str:
    return _SPACES.sub(" ", "".join(s.text for s in segs)).strip()


def slot_values(segs: list[Seg]) -> dict[str, str]:
    return {s.slot: s.text for s in segs if s.slot}
