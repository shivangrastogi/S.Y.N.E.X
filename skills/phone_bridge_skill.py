"""Phone bridge voice surface.

Skills:
  * ``phone_pair_on``  — start the LAN HTTP server
  * ``phone_pair_off`` — stop it
  * ``phone_pair_url`` — print the URL + token
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="phone_pair_on",
    description="Start the LAN phone-bridge HTTP server so a phone "
                "browser on the same WiFi can fire AERIS skills.",
    patterns=[
        "phone pair on", "start phone bridge",
        "phone bridge on", "pair my phone",
        "phone server on", "open phone bridge",
        "phone se control",
    ],
    required_entities=[],
)
def phone_pair_on(_slots: dict) -> str:
    try:
        from core.phone_bridge import start
    except Exception as e:
        return f"phone_bridge load fail: {e}"
    info = start()
    return info.get("msg") or "Phone bridge ON."


@skill(
    name="phone_pair_off",
    description="Stop the phone-bridge HTTP server.",
    patterns=[
        "phone pair off", "stop phone bridge",
        "phone bridge off", "phone server off",
        "close phone bridge", "phone bridge band karo",
    ],
    required_entities=[],
)
def phone_pair_off(_slots: dict) -> str:
    try:
        from core.phone_bridge import stop, is_running
    except Exception as e:
        return f"phone_bridge load fail: {e}"
    if not is_running():
        return "Phone bridge already OFF."
    stop()
    return "Phone bridge OFF."


@skill(
    name="phone_pair_url",
    description="Show the phone-bridge URL + access token.",
    patterns=[
        "phone pair url", "phone bridge url",
        "phone pair status", "phone bridge status",
        "phone server url", "phone se kaise connect karu",
    ],
    required_entities=[],
)
def phone_pair_url(_slots: dict) -> str:
    try:
        from core.phone_bridge import status as _status
    except Exception as e:
        return f"phone_bridge load fail: {e}"
    st = _status()
    if not st["running"]:
        return "Phone bridge OFF. 'phone pair on' to start."
    return (f"Phone bridge: {st['url']} · "
            f"send 'X-Aeris-Token' header with the token "
            f"(printed when you ran 'phone pair on').")
