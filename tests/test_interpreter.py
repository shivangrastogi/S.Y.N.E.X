"""Tests for core.interpreter — the understanding-strategy policy (Sentient-Partner P5)."""
from __future__ import annotations

from core.interpreter import Interpreter


def _i(enabled=True):
    return Interpreter(enabled=enabled)


# ── multi-step → agent ───────────────────────────────────────────────────
def test_multistep_goes_to_agent():
    i = _i()
    p = i.plan("chrome kholo aur phir gmail dekho")
    assert p.strategy == "agent" and p.reason == "multistep"


def test_long_utterance_is_multistep():
    i = _i()
    p = i.plan("please find the biggest file in my downloads and move it and rename it now ok")
    assert p.strategy == "agent"


# ── single-step reasoning query → agent (the P5 upgrade) ──────────────────
def test_reasoning_query_goes_to_agent():
    i = _i()
    p = i.plan("konsi file sabse purani hai")
    assert p.strategy == "agent" and p.reason == "reasoning-query"


def test_which_query_goes_to_agent():
    assert _i().plan("which app is using the most battery").strategy == "agent"


# ── plain single-step action → one-shot tool ─────────────────────────────
def test_plain_action_is_tool():
    i = _i()
    p = i.plan("chrome kholo")
    assert p.strategy == "tool" and p.reason == "single-step actionable"


def test_action_needs_tools_available():
    # no tools → an actionable single-step falls through to chat
    assert _i().plan("chrome kholo", has_tools=False).strategy == "chat"


# ── conversation → chat ──────────────────────────────────────────────────
def test_conversational_is_chat():
    assert _i().plan("aaj mera mood kharab hai yaar").strategy == "chat"


def test_empty_is_chat():
    assert _i().plan("   ").strategy == "chat"


# ── kill switch reverts reasoning-query broadening ───────────────────────
def test_kill_switch_reverts_reasoning_to_non_agent():
    off = _i(enabled=False)
    p = off.plan("konsi file sabse purani hai")
    # "purani"/"konsi"/"file" has no action verb → chat when reasoning routing is off
    assert p.strategy != "agent"
    # multi-step still routes to the agent even with the switch off
    assert off.plan("chrome kholo aur phir gmail dekho").strategy == "agent"


def test_agent_unavailable_downgrades():
    i = _i()
    # a reasoning query with no agent wired → not "agent"
    p = i.plan("konsi file sabse purani hai", agent_available=False)
    assert p.strategy != "agent"
