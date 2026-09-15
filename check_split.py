"""Will split mode work on this machine? — one command, no hardware touched.

    python check_split.py

Reports PASS / WARN / FAIL for each thing the split flags need, with a fix hint
for anything that fails, and finishes by naming the flags that are safe to turn
on. Nothing here opens the camera or the microphone; it answers *"is this
plausible"*, while `run_vision_split.py` and `run_voice_split.py` answer
*"does it actually work"*.

Exit code is 0 when nothing failed, 1 otherwise — so it can gate a script.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # The guard matters: every check below spawns child processes, and Windows
    # 'spawn' re-imports this file in each one.
    from core.split_preflight import main
    raise SystemExit(main())
