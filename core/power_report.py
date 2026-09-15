"""Power report — measure what the tiered-wake standby actually saves.

The whole justification for keeping the brain DORMANT until woken is memory and
CPU. This module measures it honestly: the footprint of the AERIS process tree
(the light Tier-0 parent **plus** any spawned Brain child) in two states —

    DORMANT   : Tier-0 only, brain not spawned
    RESIDENT  : brain service up (torch + encoder + skills, its own process)

— and reports the delta. ``tools`` / ``main.py`` can call ``measure_standby`` to
spin the brain up around a live daemon and print the saving; the pure
``footprint`` / ``savings`` maths is unit-tested with a fake psutil so no heavy
spawn is needed to trust the numbers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProcFootprint:
    """A point-in-time footprint of a process tree."""

    rss_mb: float          # resident set size, megabytes (parent + children)
    threads: int           # total OS threads across the tree
    procs: int             # number of live processes counted

    def __str__(self) -> str:
        return f"{self.rss_mb:.0f} MB · {self.threads} threads · {self.procs} proc"


def _real_psutil():
    import psutil  # lazy: only when actually measuring
    return psutil


def footprint(root_pid: int, *, psutil_mod=None,
              include_children: bool = True) -> ProcFootprint:
    """Footprint of ``root_pid`` and (optionally) its whole child tree.

    Robust to a process vanishing between enumeration and sampling — a child
    that dies mid-measure is simply skipped, never raised.
    """
    ps = psutil_mod or _real_psutil()

    procs = []
    try:
        root = ps.Process(root_pid)
        procs.append(root)
        if include_children:
            procs.extend(root.children(recursive=True))
    except ps.NoSuchProcess:
        return ProcFootprint(rss_mb=0.0, threads=0, procs=0)

    rss = 0
    threads = 0
    counted = 0
    for p in procs:
        try:
            rss += p.memory_info().rss
            threads += p.num_threads()
            counted += 1
        except ps.NoSuchProcess:
            continue  # vanished between enumerate and sample
    return ProcFootprint(rss_mb=rss / 1e6, threads=threads, procs=counted)


def savings(dormant: ProcFootprint, resident: ProcFootprint) -> dict:
    """How much the brain being dormant saves versus being resident."""
    saved_mb = resident.rss_mb - dormant.rss_mb
    pct = (saved_mb / resident.rss_mb * 100.0) if resident.rss_mb > 0 else 0.0
    return {
        "dormant_mb": round(dormant.rss_mb, 1),
        "resident_mb": round(resident.rss_mb, 1),
        "rss_saved_mb": round(saved_mb, 1),
        "pct_saved": round(pct, 1),
        "dormant_procs": dormant.procs,
        "resident_procs": resident.procs,
    }


def format_report(s: dict) -> str:
    return (
        "AERIS standby power report\n"
        f"  dormant  : {s['dormant_mb']:.0f} MB  ({s['dormant_procs']} proc)\n"
        f"  resident : {s['resident_mb']:.0f} MB  ({s['resident_procs']} proc)\n"
        f"  saved    : {s['rss_saved_mb']:.0f} MB  ({s['pct_saved']:.0f}% lighter while dormant)"
    )


def measure_standby(spin_up, spin_down, *, settle_s: float = 3.0,
                    root_pid: Optional[int] = None, psutil_mod=None) -> dict:
    """Live measurement: sample DORMANT, spin the brain up, let it settle, sample
    RESIDENT, spin it back down. ``spin_up``/``spin_down`` are the brain lifecycle
    (e.g. a ``BrainLifecycle``'s methods). Returns the ``savings`` dict.

    This is the heavy path (it really spawns the brain) — kept out of the unit
    tests; the numbers it produces are trusted because the maths above is tested.
    """
    import time

    pid = root_pid if root_pid is not None else os.getpid()
    dormant = footprint(pid, psutil_mod=psutil_mod)
    try:
        spin_up()
        time.sleep(settle_s)
        resident = footprint(pid, psutil_mod=psutil_mod)
    finally:
        spin_down()
    return savings(dormant, resident)
