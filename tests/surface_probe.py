"""Derive, from the source, what a swappable engine's callers actually use.

Both cutovers (§6.30 vision, §6.31 voice) are only safe while the adapter
covers everything the real class is asked for. Hardcoding that list would rot
the moment someone adds a call, so the tests re-derive it — and this is the
shared derivation.

**Scoped per function, not per file**, which is the whole reason this is worth
extracting. `ui/jarvis_v31/main_window.py` binds a local called ``eng`` to the
*voice* engine in `VoiceWorker.initialize` and to the *gesture* engine in
`_try_attach_gesture_listener`. A file-wide scan therefore attributes
`add_listener` to the voice engine and the voice signals to the gesture engine
— which is exactly what happened, and was first papered over with a hardcoded
exclusion list per test. Splitting the source into function blocks and
correlating names only within a block removes the guesswork instead.
"""

from __future__ import annotations

import pathlib
import re

_DEF_RE = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+\w+", re.M)


def _blocks(src: str) -> list:
    """Split source into per-`def` chunks (plus the module-level remainder).

    Crude on purpose: it needs to separate two same-named locals in different
    methods, not to parse Python. A nested `def` starting a new block only
    makes the scoping finer, which is the safe direction.
    """
    starts = [m.start() for m in _DEF_RE.finditer(src)]
    if not starts:
        return [src]
    out = [src[: starts[0]]]
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(src)
        out.append(src[s:end])
    return out


def engine_surface(root: pathlib.Path, dirs, factory_pattern: str,
                   skip: str = "_archive") -> set:
    """Attributes accessed on whatever ``factory_pattern`` produces.

    ``factory_pattern`` is a regex alternation of the constructor/getter names
    that yield the engine, e.g. ``r"get_gesture_engine\\(\\)|_DEFAULT_ENGINE"``.
    Private names (leading underscore) are dropped — adapters are not expected
    to reproduce internals.
    """
    binder_re = re.compile(
        rf"(\w+)\s*=\s*(?:\w+\.)?(?:{factory_pattern})")
    used: set = set()
    for d in dirs:
        base = root / d
        if not base.exists():
            continue
        for f in base.rglob("*.py"):
            if skip and skip in str(f):
                continue
            src = f.read_text(encoding="utf-8", errors="ignore")
            if not binder_re.search(src):
                continue
            for block in _blocks(src):
                binders = set(binder_re.findall(block))
                if not binders:
                    continue
                for b in binders:
                    used |= set(re.findall(
                        rf"\b(?:self\.)?{re.escape(b)}\.(\w+)", block))
    return {n for n in used if not n.startswith("_")}
