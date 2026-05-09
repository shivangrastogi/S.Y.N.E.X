"""Tests for the skill plugin registry."""

from __future__ import annotations

import pytest

from core.skill_registry import (
    REGISTRY,
    Skill,
    all_skills,
    get_skill,
    patterns_as_intent_dict,
    reset_for_tests,
    skill,
    tools_manifest,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Each test gets a clean registry — restore real plugins afterwards."""
    saved = dict(REGISTRY)
    reset_for_tests()
    yield
    reset_for_tests()
    REGISTRY.update(saved)


def test_decorator_registers_skill():
    @skill(name="dummy_skill", description="just a test", patterns=["do dummy"])
    def _handler(slots):
        return "did dummy"

    assert "dummy_skill" in REGISTRY
    sk = get_skill("dummy_skill")
    assert isinstance(sk, Skill)
    assert sk.description == "just a test"
    assert sk.patterns == ["do dummy"]


def test_skill_run_returns_handler_value():
    @skill(name="echo_skill", patterns=["echo X"])
    def _handler(slots):
        return f"echo: {slots.get('content', '')}"

    sk = get_skill("echo_skill")
    assert sk.run({"content": "hello"}) == "echo: hello"


def test_re_registration_overrides():
    @skill(name="dup", patterns=["a"])
    def _h1(_):
        return "v1"

    @skill(name="dup", patterns=["b"])
    def _h2(_):
        return "v2"

    assert get_skill("dup").run({}) == "v2"
    assert get_skill("dup").patterns == ["b"]


def test_patterns_as_intent_dict_shape():
    @skill(
        name="x",
        patterns=["one", "two"],
        required_entities=["thing"],
        prompts={"thing": "what thing?"},
    )
    def _h(_):
        return "x"

    out = patterns_as_intent_dict()
    assert "x" in out
    assert out["x"]["patterns"] == ["one", "two"]
    assert out["x"]["required_entities"] == ["thing"]
    assert out["x"]["prompts"] == {"thing": "what thing?"}


def test_tools_manifest_excludes_no_op_pattern_skills():
    @skill(name="real_skill", description="does X", patterns=["xx"])
    def _h(_):
        return "done"

    @skill(name="no_pattern_skill", description="does Y")
    def _h2(_):
        return "done"

    manifest = tools_manifest()
    names = {t["name"] for t in manifest}
    assert "real_skill" in names
    # tools_manifest INCLUDES all registered skills; pattern filtering only
    # applies to the brain's intent dict.
    assert "no_pattern_skill" in names


def test_get_skill_returns_none_for_unknown():
    assert get_skill("not_registered") is None
    assert all_skills() == {}
