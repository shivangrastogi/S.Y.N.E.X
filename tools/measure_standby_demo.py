"""Validation demo: measure the standby footprint delta around a REAL spawned
service.

Uses the light ``echo`` service (fast, safe) instead of the heavy brain, purely
to prove ``measure_standby``'s spin-up → sample → spin-down mechanic works with a
real subprocess. On-device, swapping ``echo`` for the real Brain service shows
the true ~1.5-2 GB dormant-vs-resident delta.

    python tools/measure_standby_demo.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.power_report import measure_standby, format_report
from core.service_bus import ServiceProxy, echo_handler_factory


def main() -> int:
    proxy = ServiceProxy("echo", echo_handler_factory)
    s = measure_standby(spin_up=proxy.start, spin_down=proxy.stop, settle_s=1.0)
    print(format_report(s))
    assert s["resident_procs"] >= s["dormant_procs"], "spawned child not observed"
    print("\nOK: measure_standby spun a real child up, measured it, tore it down.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
