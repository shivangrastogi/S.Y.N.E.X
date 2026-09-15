"""Skill plugin registry.

Drop a Python file into ``skills/`` and decorate its handler with ``@skill`` —
the registry auto-discovers it at boot. Patterns are merged into the brain's
intent index, the entity extractor's slot map, and the executor's dispatch.

Each plugin skill ends up indistinguishable from a built-in one to the rest
of the pipeline.
"""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil
from dataclasses import dataclass
from typing import Callable, Optional

log = logging.getLogger(__name__)


@dataclass
class Skill:
    name: str
    description: str
    patterns: list[str]
    required_entities: list[str]
    prompts: dict[str, str]
    handler: Callable[[dict], str]
    # Per-skill breaker timeout override (seconds). LLM-backed skills need
    # far more than the 5s default (Qwen on CPU). None → default.
    timeout_s: Optional[float] = None

    def run(self, slots: dict) -> str:
        return self.handler(slots)


REGISTRY: dict[str, Skill] = {}


def skill(
    name: str,
    description: str = "",
    patterns: Optional[list[str]] = None,
    required_entities: Optional[list[str]] = None,
    prompts: Optional[dict[str, str]] = None,
    timeout_s: Optional[float] = None,
):
    """Decorator that registers a skill with the global REGISTRY."""
    def decorator(func: Callable[[dict], str]) -> Callable[[dict], str]:
        if name in REGISTRY:
            log.warning("skill %r re-registered; overriding", name)
        REGISTRY[name] = Skill(
            name=name,
            description=description,
            patterns=list(patterns or []),
            required_entities=list(required_entities or []),
            prompts=dict(prompts or {}),
            handler=func,
            timeout_s=timeout_s,
        )
        return func
    return decorator


# Skills whose handler calls the embedded local LLM (Qwen on CPU) — they need
# a far larger breaker budget than the 5s default or they always time out.
_LLM_SKILLS = {
    "fix_grammar", "brainstorm_ideas", "explain_simply", "make_title",
    "shorten_text", "define_word", "pros_cons", "how_to_steps", "write_poem",
    "motivate_me", "tell_joke", "tell_story", "tell_riddle",
    "synonyms_antonyms", "rephrase_text", "fun_fact", "give_compliment",
    "rhyming_words", "recipe_suggest",
}
_LLM_TIMEOUT_S = 30.0


def apply_declared_timeouts() -> int:
    """Push each skill's timeout (declared via @skill(timeout_s=…) or the
    known LLM set) into the circuit breaker. Call after discover_skills().
    Returns how many timeouts were configured."""
    try:
        from core.skill_breaker import configure
    except Exception:
        return 0
    n = 0
    for name, sk in REGISTRY.items():
        t = sk.timeout_s
        if t is None and name in _LLM_SKILLS:
            t = _LLM_TIMEOUT_S
        if t is not None:
            configure(name, timeout_s=t)
            n += 1
    return n


def discover_skills(skills_pkg: str = "skills") -> int:
    """Import every top-level module under ``skills_pkg`` so decorators fire.

    Returns the number of skills newly registered. Failed imports are logged
    but never raised — a broken skill must not take down the whole assistant.
    """
    try:
        pkg = importlib.import_module(skills_pkg)
    except ModuleNotFoundError:
        return 0

    pkg_dir = os.path.dirname(pkg.__file__) if pkg.__file__ else None
    if not pkg_dir:
        return 0

    before = len(REGISTRY)
    for _, mod_name, is_pkg in pkgutil.iter_modules([pkg_dir]):
        if is_pkg or mod_name.startswith("_"):
            continue
        try:
            importlib.import_module(f"{skills_pkg}.{mod_name}")
        except Exception as e:
            log.warning("failed to load skill module %r: %s", mod_name, e)
    return len(REGISTRY) - before


def get_skill(name: str) -> Optional[Skill]:
    return REGISTRY.get(name)


def all_skills() -> dict[str, Skill]:
    return dict(REGISTRY)


def patterns_as_intent_dict() -> dict:
    """Convert REGISTRY into intents.json shape so brain k-NN can ingest it."""
    return {
        s.name: {
            "patterns": s.patterns,
            "required_entities": s.required_entities,
            "prompts": s.prompts,
        }
        for s in REGISTRY.values()
        if s.patterns
    }


def tools_manifest() -> list[dict]:
    """Return a list of tool descriptors for LLM function-calling prompts."""
    return [
        {
            "name": s.name,
            "description": s.description or s.name.replace("_", " "),
            "args": s.required_entities,
        }
        for s in REGISTRY.values()
    ]


def reset_for_tests() -> None:
    """Wipe the registry (test fixtures only — never call in production)."""
    REGISTRY.clear()
