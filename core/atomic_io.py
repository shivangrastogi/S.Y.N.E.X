"""Crash-safe file writes.

Every persistent-state writer in AERIS (settings, user memory, feedback
schema, cached indices) must route through ``write_atomic`` so a power
loss or kill -9 mid-write cannot leave a half-written / zero-byte file
in place.

Algorithm
---------
1. ``tempfile.NamedTemporaryFile`` in the SAME directory as the target
   (must be same volume so ``os.replace`` is atomic — cross-device
   rename is not a syscall, it's a copy).
2. Write payload + ``flush()`` + ``os.fsync(fd)`` so the bytes are
   actually on disk, not just in the page cache.
3. ``os.replace(tmp, target)`` — atomic on both POSIX and Windows when
   on the same volume (NTFS replaces the existing file in one
   metadata flip).
4. Best-effort fsync the *directory* on POSIX so the rename itself is
   durable across a crash; Windows handles directory journaling
   inside NTFS itself, so no extra step.

Failure modes
-------------
* Disk-full during write → tempfile lingers in the target's directory,
  original file untouched. Caller's existing open handle on the
  original keeps working.
* Crash between tempfile.close() and os.replace → tempfile may persist;
  ``cleanup_orphans(target)`` purges files matching the temp pattern.
* Cross-volume target → caught explicitly and raised; never silently
  fall back to a non-atomic copy.

Typical use
-----------
    from core.atomic_io import write_atomic_text, write_atomic_json
    write_atomic_json("data/settings.json", config_dict)
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any, Iterable, Optional

log = logging.getLogger(__name__)

_TEMP_PREFIX = ".aeris-tmp-"


def write_atomic(path: str,
                 data: bytes,
                 *,
                 fsync: bool = True) -> None:
    """Write ``data`` to ``path`` atomically.

    ``fsync`` adds the durability guarantee; turn it off only for
    perf-critical paths where you're willing to lose a few seconds
    of state on power loss (e.g. cache files that can be rebuilt).
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("write_atomic expects bytes; use write_atomic_text or write_atomic_json")

    target_dir = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(target_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=_TEMP_PREFIX,
        suffix=os.path.basename(path),
        dir=target_dir,
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            if fsync:
                try:
                    os.fsync(f.fileno())
                except OSError:
                    # fsync isn't supported on every filesystem (e.g. a
                    # tmpfs mounted noatime). The replace below is still
                    # atomic; we just lose the durability guarantee.
                    pass
        # os.replace is atomic on the same volume on both POSIX and Windows.
        os.replace(tmp_path, path)
        if fsync and os.name != "nt":
            # POSIX: fsync the parent directory so the rename itself
            # survives a crash. NTFS journals the rename so this is a
            # no-op on Windows (and POSIX-only API).
            try:
                dir_fd = os.open(target_dir, os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
    except Exception:
        # Clean up the tempfile so we don't leak partial state.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_atomic_text(path: str, text: str, *,
                      encoding: str = "utf-8",
                      fsync: bool = True) -> None:
    write_atomic(path, text.encode(encoding), fsync=fsync)


def write_atomic_json(path: str, obj: Any, *,
                      indent: Optional[int] = 2,
                      sort_keys: bool = False,
                      ensure_ascii: bool = False,
                      fsync: bool = True) -> None:
    """JSON convenience wrapper. Serialises with sensible defaults."""
    text = json.dumps(obj, indent=indent, sort_keys=sort_keys,
                      ensure_ascii=ensure_ascii)
    # Trailing newline is conventional and plays nice with `diff`.
    if not text.endswith("\n"):
        text += "\n"
    write_atomic_text(path, text, fsync=fsync)


def cleanup_orphans(path: str) -> int:
    """Remove leaked tempfiles from a previous crash. Returns count purged."""
    target_dir = os.path.dirname(os.path.abspath(path)) or "."
    target_name = os.path.basename(path)
    if not os.path.isdir(target_dir):
        return 0
    removed = 0
    for name in os.listdir(target_dir):
        if name.startswith(_TEMP_PREFIX) and name.endswith(target_name):
            try:
                os.unlink(os.path.join(target_dir, name))
                removed += 1
            except OSError:
                pass
    return removed


if __name__ == "__main__":
    import shutil
    import tempfile as _tf
    import time

    workdir = _tf.mkdtemp(prefix="aeris_atomic_test_")
    try:
        target = os.path.join(workdir, "config.json")
        write_atomic_json(target, {"hello": "world", "n": 42})
        with open(target) as f:
            print("read back:", f.read())

        # Concurrent-writer durability sketch: write 100 times, ensure
        # the file is always valid JSON if we open it between writes.
        for i in range(100):
            write_atomic_json(target, {"i": i})
        with open(target) as f:
            obj = json.load(f)
        print(f"after 100 rewrites: i={obj['i']} (expected 99)")

        # Tempfile cleanup
        # (synthesise an orphan and confirm cleanup_orphans picks it up)
        orphan = os.path.join(workdir, f"{_TEMP_PREFIX}xyz{os.path.basename(target)}")
        with open(orphan, "w") as f:
            f.write("orphan")
        print(f"orphans cleaned: {cleanup_orphans(target)}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
