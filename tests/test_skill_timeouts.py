"""LLM-backed skills get a longer breaker budget than the 5s default
(they were 100%% failing live: 'tell_joke did not respond within 5.0s')."""

from __future__ import annotations

import importlib
import pkgutil

from core.skill_registry import (REGISTRY, Skill, apply_declared_timeouts,
                                  _LLM_TIMEOUT_S)


def _discover_once():
    import skills as _pkg
    for m in pkgutil.iter_modules(_pkg.__path__):
        try:
            importlib.import_module("skills." + m.name)
        except Exception:
            pass


def _breaker_timeout(name):
    import core.skill_breaker as sb
    for row in sb.stats():
        if row.get("name") == name:
            return row.get("timeout_s")
    return None


def test_llm_skills_get_long_timeout():
    _discover_once()
    assert apply_declared_timeouts() >= 19
    assert _breaker_timeout("tell_joke") == _LLM_TIMEOUT_S
    assert _breaker_timeout("recipe_suggest") == _LLM_TIMEOUT_S
    assert _breaker_timeout("write_poem") == _LLM_TIMEOUT_S


def test_declared_timeout_is_honored():
    REGISTRY["__t_slow__"] = Skill(
        name="__t_slow__", description="", patterns=[], required_entities=[],
        prompts={}, handler=lambda s: "x", timeout_s=7.0)
    try:
        apply_declared_timeouts()
        assert _breaker_timeout("__t_slow__") == 7.0
    finally:
        REGISTRY.pop("__t_slow__", None)


def test_non_llm_skill_not_forced_long():
    _discover_once()
    apply_declared_timeouts()
    # a plain math skill must NOT get the 30s LLM budget
    t = _breaker_timeout("bmi_calc")
    assert t is None or t < _LLM_TIMEOUT_S
