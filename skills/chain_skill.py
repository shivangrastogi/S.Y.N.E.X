"""Voice command surface for the cross-skill chain engine.

Skills:
  * ``chains_on``        — attach the chain engine to gesture emits
  * ``chains_list``      — list configured chains
  * ``chains_reload``    — re-read data/chains.json after editing
  * ``chain_path``       — print the chains.json absolute path
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="chains_on",
    description="Activate the cross-skill chain engine — fires follow-up "
                "skills automatically when configured triggers happen.",
    patterns=[
        "chains on", "chain engine on", "enable chains",
        "chains chalu karo", "start chains",
        "chain engine chalu karo",
    ],
    required_entities=[],
)
def chains_on(_slots: dict) -> str:
    try:
        from core.chain_engine import get_chain_engine
    except Exception as e:
        return f"chain_engine load fail: {e}"
    eng = get_chain_engine()
    if eng.start():
        n = len(eng.list_chains())
        return f"Chains ON — {n} chain(s) attached to gesture emits."
    return ("Chains attach fail — gesture engine reachable? "
            "Run 'diagnose' to check.")


@skill(
    name="chains_list",
    description="List every defined chain (trigger + step count).",
    patterns=[
        "chains list", "list chains", "show chains",
        "chains dikhao", "kaunse chains hain",
        "chain list",
    ],
    required_entities=[],
)
def chains_list(_slots: dict) -> str:
    try:
        from core.chain_engine import get_chain_engine
    except Exception as e:
        return f"chain_engine load fail: {e}"
    chains = get_chain_engine().list_chains()
    if not chains:
        return "Koi chain define nahi — edit data/chains.json + 'reload chains'."
    lines = [f"{len(chains)} chain(s):"]
    for name in sorted(chains):
        c = chains[name]
        lines.append(
            f"  • {name:24s} trigger={c['trigger']!r:25s} steps={len(c['then'])}"
        )
        if c.get("description"):
            lines.append(f"      {c['description']}")
    return "\n".join(lines)


@skill(
    name="chains_reload",
    description="Reload data/chains.json after editing.",
    patterns=[
        "reload chains", "chains reload karo",
        "refresh chains", "chains reload",
    ],
    required_entities=[],
)
def chains_reload(_slots: dict) -> str:
    try:
        from core.chain_engine import get_chain_engine
    except Exception as e:
        return f"chain_engine load fail: {e}"
    n = get_chain_engine().reload()
    return f"Reloaded — {n} chain(s) active."


@skill(
    name="chain_path",
    description="Print the chains.json absolute path so it can be edited.",
    patterns=[
        "chain path", "chains path", "chains file",
        "chains kahan hai", "where are chains",
    ],
    required_entities=[],
)
def chain_path(_slots: dict) -> str:
    from core.chain_engine import _CHAINS_PATH
    return f"Chains file: {_CHAINS_PATH}"
