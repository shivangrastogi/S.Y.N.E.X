"""Cloud Bridge voice surface — pair / status / stop / unpair.

"phone pair karo" → generates a fresh QR (opens on screen) that the
AERIS Remote app scans once. After that the phone can talk to this
laptop from anywhere on the internet — no IPs, no hosting (see
core/cloud_bridge.py for the architecture).

NOTE: distinct from the older LAN-only ``phone_bridge`` skills
("phone pair on") which serve a browser page over local WiFi. The
cloud bridge is the internet-wide, E2E-encrypted successor.
"""
from __future__ import annotations

import logging
import os

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="bridge_pair",
    description="Pair the AERIS Remote phone app — shows a QR code; scan "
                "once, then control the laptop from anywhere (E2E encrypted).",
    patterns=[
        "phone pair karo", "pair phone", "bridge pair",
        "mobile pair karo", "connect my phone", "phone jodo",
        "naya phone pair karo", "show pairing qr",
        # Common Hinglish spellings — listed verbatim so they hit the
        # exact-match fast-path and skip the (crash-prone) neural encoder.
        "phone pair kro", "phone pair kardo", "phone pair kar do",
        "pair kro", "pair karo", "mobile pair kro", "phone connect kro",
        "qr dikhao", "pairing qr dikhao", "phone pairing karo",
    ],
    required_entities=[],
)
def bridge_pair(_slots: dict) -> str:
    from core.cloud_bridge import get_bridge
    b = get_bridge()
    ok, why = b.available()
    if not ok:
        return f"Bridge abhi ready nahi: {why}"
    info = b.pair()
    if not info:
        return "Pairing generate nahi ho paayi — log dekho."
    # Fresh pairing → (re)start listening with the rotated key.
    b.start(None)
    if info.get("qr_path"):
        # Sentinel → the GUI catches this and shows PairDialog (an in-app
        # popup with the QR + steps) on the main thread, instead of dumping
        # the PNG into the OS image viewer. Format: [pair_qr]<path>|<pid8>
        pid8 = (info.get("pid") or "")[:8]
        return f"[pair_qr]{info['qr_path']}|{pid8}"
    return ("Pairing ban gayi par QR render nahi hua — "
            "data/secrets/bridge_pair.json manually app mein daalna hoga.")


@skill(
    name="bridge_status",
    description="Cloud bridge health — key present, paired, listening.",
    patterns=[
        "bridge status", "cloud bridge status", "phone bridge status batao",
        "is my phone connected", "phone connected hai kya",
        "mobile bridge status",
    ],
    required_entities=[],
)
def bridge_status(_slots: dict) -> str:
    from core.cloud_bridge import get_bridge
    s = get_bridge().status()
    bits = [
        "key: " + ("OK" if s["sa_key"] else "MISSING"),
        "paired: " + ("haan" if s["paired"] else "nahi"),
        "listening: " + ("haan" if s["listening"] else "nahi"),
    ]
    if s.get("project"):
        bits.append(f"project: {s['project']}")
    out = "Bridge — " + " · ".join(bits) + "."
    if not s["sa_key"]:
        out += f" ({s['reason']})"
    return out


@skill(
    name="bridge_off",
    description="Stop the cloud bridge listener (pairing stays saved).",
    patterns=[
        "bridge off", "bridge band karo", "cloud bridge off",
        "stop cloud bridge",
    ],
    required_entities=[],
)
def bridge_off(_slots: dict) -> str:
    from core.cloud_bridge import get_bridge
    get_bridge().stop()
    return "Cloud bridge band kar diya. Pairing saved hai — 'bridge on' se wapas."


@skill(
    name="bridge_on",
    description="Start the cloud bridge listener (needs an existing pairing).",
    patterns=[
        "bridge on", "bridge chalu karo", "cloud bridge on",
        "start cloud bridge",
    ],
    required_entities=[],
)
def bridge_on(_slots: dict) -> str:
    from core.cloud_bridge import get_bridge
    ok, msg = get_bridge().start(None)
    return ("Cloud bridge chalu — phone se commands aa sakti hain."
            if ok else f"Bridge start nahi hua: {msg}")


@skill(
    name="bridge_unpair",
    description="KILL SWITCH — delete the pairing; the phone is locked out "
                "instantly until a fresh QR is scanned.",
    patterns=[
        "phone unpair karo", "unpair phone", "bridge unpair",
        "phone disconnect karo permanently", "remove phone pairing",
    ],
    required_entities=[],
)
def bridge_unpair(_slots: dict) -> str:
    from core import cloud_bridge
    cloud_bridge.get_bridge().stop()
    removed = False
    try:
        if os.path.isfile(cloud_bridge._PAIR_PATH):
            os.remove(cloud_bridge._PAIR_PATH)
            removed = True
        if os.path.isfile(cloud_bridge._QR_PATH):
            os.remove(cloud_bridge._QR_PATH)
    except Exception as e:
        return f"Unpair mein dikkat: {e}"
    return ("Phone unpaired — purani key ab kachra hai. Naye phone ke "
            "liye 'phone pair karo' bolna." if removed
            else "Koi pairing thi hi nahi.")
