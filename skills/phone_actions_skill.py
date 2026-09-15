"""Laptop → phone actions (Phase 2 reverse direction).

Phase 1 was phone → laptop. These skills let the LAPTOP reach the phone:

  * ring_phone     — "mera phone ring karao" — loud ring even on silent,
                     even when the app is CLOSED (via FCM push). The
                     find-my-phone killer feature.
  * phone_battery  — ask the phone its battery %; the reply comes back
                     over the bridge and is surfaced on the laptop.
  * phone_bridge_push_test — send a test push notification.

All go through ``core.cloud_bridge`` — the same E2E-encrypted channel.
Ring uses BOTH: an in-app action (instant if the app is open) AND an FCM
push (works when the app is closed).
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="ring_phone",
    description="Ring the paired phone loudly (find my phone) — works even "
                "when the AERIS Remote app is closed, via push.",
    patterns=[
        "mera phone ring karao", "ring my phone", "find my phone",
        "phone dhundo", "phone bajao", "phone ki ghanti bajao",
        "make my phone ring", "where is my phone", "phone locate karo",
    ],
    required_entities=[],
)
def ring_phone(_slots: dict) -> str:
    from core.cloud_bridge import get_bridge
    b = get_bridge()
    if not b.status().get("paired"):
        return "Koi phone paired nahi hai — pehle 'phone pair karo'."
    # In-app action (instant if app open) …
    b.send_action("ring", {"loud": True})
    # … + FCM push (fires even if the app is closed).
    ok, msg = b.send_push(
        title="AERIS — Find my phone",
        body="Ring ho raha hai 🔔 Tap to stop.",
        data={"action": "ring"},
    )
    if ok:
        return "Phone ring kar raha hoon 🔔 — silent pe bhi bajega. Mil gaya?"
    return ("Phone ko ring signal bhej diya (app khula ho to bajega). "
            f"Push nahi gaya: {msg}")


@skill(
    name="phone_battery",
    description="Ask the paired phone for its battery level.",
    patterns=[
        "phone ki battery kitni hai", "phone battery batao",
        "mere phone ki battery", "how much battery on my phone",
        "phone battery status", "mobile battery kitni hai",
    ],
    required_entities=[],
)
def phone_battery(_slots: dict) -> str:
    from core.cloud_bridge import get_bridge
    b = get_bridge()
    if not b.status().get("paired"):
        return "Koi phone paired nahi hai — pehle 'phone pair karo'."
    b.send_action("get_battery")
    return ("Phone se battery pooch raha hoon — jawab aate hi chat mein "
            "dikha dunga. (Phone app khula hona chahiye.)")


@skill(
    name="phone_push_test",
    description="Send a test push notification to the phone.",
    patterns=[
        "phone push test", "test phone notification",
        "phone ko notification bhejo", "send test push to phone",
    ],
    required_entities=[],
)
def phone_push_test(_slots: dict) -> str:
    from core.cloud_bridge import get_bridge
    ok, msg = get_bridge().send_push(
        title="AERIS test", body="Push kaam kar raha hai ✅",
        data={"action": "test"})
    return "Test push bhej diya ✅" if ok else f"Push fail: {msg}"
