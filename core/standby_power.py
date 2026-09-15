"""Windows power policy for standby mode.

On a laptop there is an honest tension: to keep listening for the wake word the
*system* cannot fully sleep (a suspended process hears nothing), but the
*display* — a big chunk of the power draw — absolutely can. So the standby power
policy is deliberately narrower than the GUI's ``keep_awake`` (which pins system
**and** display on):

  * **AC power**  → keep the SYSTEM awake (stay listening), let the DISPLAY sleep.
  * **battery, healthy** → same, unless the user turned off "listen on battery".
  * **battery, critical** → release the system hold too; let Windows sleep and
    save the battery — voice-wake pauses until the user wakes the machine.

The policy itself is pure (``flags_for``) so it is unit-tested with no ctypes;
the daemon re-asserts the chosen flags from its existing tick thread (execution
state is thread-scoped, so it needs a steady owner — the tick loop is one).
"""

from __future__ import annotations

import os

# SetThreadExecutionState flags (winbase.h).
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


class StandbyPowerPolicy:
    """Decides the Windows execution-state flags for a given power situation."""

    def __init__(self, *, keep_awake_on_battery: bool = True,
                 critical_pct: int = 15) -> None:
        self.keep_awake_on_battery = keep_awake_on_battery
        self.critical_pct = int(critical_pct)

    def keep_system_awake(self, on_battery: bool, percent: int) -> bool:
        """Should we prevent the system sleeping (i.e. keep listening)?"""
        if not on_battery:
            return True  # plugged in → always stay awake to listen
        if not self.keep_awake_on_battery:
            return False  # user opted out of listening on battery
        return int(percent) > self.critical_pct  # listen until critical

    def flags_for(self, on_battery: bool, percent: int) -> int:
        """The execution-state flags to hold for this power situation.

        Never includes ``ES_DISPLAY_REQUIRED`` — the display is always allowed to
        sleep in standby, which is where a lot of the laptop's power goes.
        """
        flags = ES_CONTINUOUS
        if self.keep_system_awake(on_battery, percent):
            flags |= ES_SYSTEM_REQUIRED
        return flags

    def describe(self, on_battery: bool, percent: int) -> str:
        keep = self.keep_system_awake(on_battery, percent)
        src = "battery" if on_battery else "AC"
        return (
            f"{src} {percent}% → "
            + ("staying awake to listen (display may sleep)" if keep
               else "letting the system sleep to save battery")
        )


def set_execution_state(flags: int) -> bool:
    """Apply the Windows execution state. No-op (returns False) off Windows."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(flags)
        return True
    except Exception:
        return False
