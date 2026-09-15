"""Pattern-ownership guard — every trigger phrase has exactly ONE owner.

History: an audit (2026-07-04) found 61 collisions — 27 phrases claimed by
two or three skills, and 34 fought over by a legacy intents.json intent
and a modern skill. The same spoken phrase then routed nondeterministically
("battery status" → system_info OR battery_status depending on cosine
noise), poisoning both the k-NN index and any neural retrain.

These tests pin the fix. If you add a skill whose pattern collides with an
existing owner, this fails and names the exact phrase + both claimants —
pick one owner before shipping.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _registry():
    from core.skill_registry import discover_skills, REGISTRY
    discover_skills("skills")
    return REGISTRY


def test_no_skill_vs_skill_pattern_collisions():
    owner = {}
    collisions = collections.defaultdict(set)
    for name, sk in sorted(_registry().items()):
        for p in (sk.patterns or []):
            pl = p.strip().lower()
            if pl in owner and owner[pl] != name:
                collisions[pl].update([owner[pl], name])
            else:
                owner[pl] = name
    assert not collisions, (
        "Pattern(s) claimed by multiple skills — pick ONE owner:\n" +
        "\n".join(f"  {p!r} -> {sorted(names)}"
                  for p, names in sorted(collisions.items()))
    )


def test_no_legacy_vs_skill_pattern_collisions():
    owner = {}
    for name, sk in sorted(_registry().items()):
        for p in (sk.patterns or []):
            owner.setdefault(p.strip().lower(), name)
    with open(os.path.join(_ROOT, "data", "intents.json"), encoding="utf-8") as f:
        intents = json.load(f)
    cross = []
    for iname, cfg in sorted(intents.items()):
        for p in cfg.get("patterns", []):
            pl = p.strip().lower()
            if pl in owner and owner[pl] != iname:
                cross.append(f"  {pl!r} -> legacy:{iname} | skill:{owner[pl]}")
    assert not cross, (
        "intents.json pattern(s) collide with registry skills — remove "
        "from the legacy intent (modern skill wins):\n" + "\n".join(cross)
    )
