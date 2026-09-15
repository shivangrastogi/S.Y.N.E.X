"""Standalone phone-bridge runner — test the mobile app RIGHT NOW.

Why this exists: the full GUI (run_gui.py) loads torch + the sentence
encoder + the (still-training) neural model. The phone bridge needs NONE
of that — only firebase-admin + qrcode + the skill registry. This script
runs JUST the bridge so you can pair + control the laptop from the phone
while training finishes in another window.

Routing here is intentionally lightweight (no neural brain):
    exact skill-pattern match  →  rapidfuzz best pattern match  →  echo
That's plenty for the app's quick actions (lock screen, screenshot,
battery, volume, sleep) and any exact command phrase. Once training is
done, the full GUI gives fuzzy + conversational routing over the SAME
bridge — nothing to re-pair.

Run it with anaconda python (BRIDGE.bat pins it):
    BRIDGE.bat
"""
import os
import sys

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import time

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("run_bridge")

from core.skill_registry import discover_skills, REGISTRY, get_skill
from core import cloud_bridge


def _build_router():
    """Return process_fn(text) -> reply using ONLY the skill registry.

    No torch, no encoder. Exact pattern hit wins; else rapidfuzz picks the
    closest pattern above a safe threshold; else a friendly fallback.
    """
    # Flatten every pattern → skill name for matching.
    pattern_owner: dict[str, str] = {}
    for name, sk in REGISTRY.items():
        for p in (sk.patterns or []):
            pattern_owner.setdefault(p.strip().lower(), name)
    all_patterns = list(pattern_owner.keys())

    try:
        from rapidfuzz import process, fuzz
        have_fuzz = True
    except Exception:
        have_fuzz = False
        log.warning("rapidfuzz missing — exact-match only")

    def route(text: str) -> str:
        t = (text or "").strip().lower()
        if not t:
            return ""
        # 1. exact pattern
        name = pattern_owner.get(t)
        # 2. fuzzy
        if name is None and have_fuzz and all_patterns:
            best = process.extractOne(t, all_patterns, scorer=fuzz.WRatio)
            if best and best[1] >= 82:
                name = pattern_owner[best[0]]
        if name is None:
            return (f"'{text}' abhi bridge ke basic router mein match nahi "
                    f"hua. Training complete hone ke baad full brain milega. "
                    f"Quick actions (lock, screenshot, battery, volume) "
                    f"kaam karenge.")
        sk = get_skill(name)
        if sk is None:
            return f"Skill '{name}' load nahi hui."
        try:
            reply = sk.run({"raw_text": text})
            log.info("phone command → %s → %r", name, (reply or "")[:60])
            return reply or f"{name} done."
        except Exception as e:
            return f"{name} chalane mein error: {e}"

    return route


def main():
    n = discover_skills("skills")
    log.info("Loaded %d skills.", n)

    bridge = cloud_bridge.get_bridge()
    ok, why = bridge.available()
    if not ok:
        log.error("Bridge unavailable: %s", why)
        sys.exit(1)

    router = bridge._engine_hook = _build_router()

    pair = cloud_bridge.load_pair()
    if pair is None:
        log.info("No pairing yet — generating a fresh QR…")
        info = bridge.pair()
        if info and info.get("qr_path"):
            try:
                os.startfile(info["qr_path"])   # opens the QR image window
            except Exception:
                pass
            log.info("QR opened: %s", info["qr_path"])
            log.info(">>> Scan it in the AERIS Remote app to pair. <<<")
    else:
        log.info("Already paired (pid=%s…). To re-pair, delete "
                 "data/secrets/bridge_pair.json and rerun.", pair["pid"][:8])

    started, msg = bridge.start(router)
    log.info("Bridge start: %s (%s)", started, msg)
    if not started:
        sys.exit(1)

    log.info("Bridge is LIVE. Phone se commands bhejo. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        log.info("Stopping bridge…")
        bridge.stop()


if __name__ == "__main__":
    main()
