"""System utilities by voice — disk, top process, uptime, keep-awake, recycle bin.

All local (core/sys_utils): psutil + Windows ctypes, no network. empty_recycle
is irreversible, so it's registered in confirm_gate.DESTRUCTIVE_SKILLS.
"""
from __future__ import annotations

import re

from core.skill_registry import skill

_DRIVE_RE = re.compile(r"\b([a-z])\s*(?:drive|:)", re.IGNORECASE)


@skill(
    name="disk_space",
    description="Report free disk space per drive (local).",
    patterns=[
        "disk space batao", "kitni disk bachi hai", "storage kitna bacha hai",
        "free space kitna hai", "c drive me kitni jagah hai",
        "disk kitni bhari hai", "kitni storage bachi hai", "disk usage batao",
    ],
    required_entities=[],
)
def disk_space(slots: dict) -> str:
    from core.sys_utils import disk_report
    text = slots.get("raw_text") or ""
    m = _DRIVE_RE.search(text)
    if m:
        return disk_report(f"{m.group(1).upper()}:\\")
    return disk_report()


@skill(
    name="top_process",
    description="Show which apps are using the most RAM or CPU (local, psutil).",
    patterns=[
        "kaunsa app ram kha raha hai", "sabse zyada ram kaun le raha hai",
        "top process dikhao", "memory hog kaun hai",
        "kaunsa app cpu kha raha hai", "sabse zyada cpu kaun le raha hai",
        "ram kaun kha raha hai", "kaunsa program bhaari hai",
    ],
    required_entities=[],
)
def top_process(slots: dict) -> str:
    from core.sys_utils import top_processes
    text = (slots.get("raw_text") or "").lower()
    by = "cpu" if "cpu" in text else "memory"
    return top_processes(n=5, by=by)


@skill(
    name="system_uptime",
    description="How long the computer has been on (local).",
    patterns=[
        "computer kitni der se on hai", "system uptime batao",
        "kitne time se on hai laptop", "uptime kya hai",
        "kab se chalu hai computer", "laptop kitni der se chal raha hai",
    ],
    required_entities=[],
)
def system_uptime(_slots: dict) -> str:
    from core.sys_utils import uptime_report
    return uptime_report()


@skill(
    name="keep_awake_on",
    description="Stop the computer from sleeping / screen turning off (local power request).",
    patterns=[
        "sone mat dena", "awake raho", "screen off mat hone dena",
        "keep awake on", "caffeine on", "so mat jana",
        "computer ko jagaye rakho", "sleep mat hone dena",
    ],
    required_entities=[],
)
def keep_awake_on(_slots: dict) -> str:
    from core.sys_utils import keep_awake
    if keep_awake(True):
        return ("Theek hai, computer ko jagaye rakhta hoon — sleep aur "
                "screen-off band. 'ab so sakte ho' bolke wapas normal.")
    return "Keep-awake sirf Windows par chalta hai, sir."


@skill(
    name="keep_awake_off",
    description="Allow the computer to sleep normally again (local).",
    patterns=[
        "ab so sakte ho", "keep awake off", "caffeine off",
        "normal power pe wapas jao", "sleep on kar do", "so jao ab",
        "jagaye rakhna band karo",
    ],
    required_entities=[],
)
def keep_awake_off(_slots: dict) -> str:
    from core.sys_utils import keep_awake, keep_awake_status
    was = keep_awake_status()
    keep_awake(False)
    return ("Wapas normal — ab computer apne aap so sakta hai."
            if was else "Keep-awake pehle se hi off tha, sir.")


@skill(
    name="empty_recycle_bin",
    description="Empty the Windows Recycle Bin permanently (irreversible; confirm-gated).",
    patterns=[
        "recycle bin khali karo", "trash empty karo", "recycle bin empty karo",
        "kachra saaf karo", "recycle bin saaf karo", "bin khali karo",
    ],
    required_entities=[],
)
def empty_recycle_bin(_slots: dict) -> str:
    from core.sys_utils import empty_recycle_bin as _empty
    return _empty()
