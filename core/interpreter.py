"""Interpreter — LLM-first understanding of unrouted input (Sentient-Partner P5).

When the fast, deterministic path (built-in anchors → intent classifier → danger
guards) can't confidently route an utterance, the Interpreter decides HOW to
*understand* it instead of dumping it straight into chit-chat. It picks the
cheapest strategy that can actually satisfy the request:

  agent  — reason with the observe/act loop: multi-step chains AND single-step
           "figure it out" queries that must inspect state to answer
           ("konsi file sabse purani hai", "downloads me kya kya hai").
  tool   — one LLM round-trip to a single tool call, for a plain single-step
           action that merely slipped the classifier ("chrome kholo").
  chat   — pure conversation / questions with no actionable verb.

This centralises what used to be an inline `_looks_multistep` branch in
main_engine._fallback and makes it unit-testable. The concrete P5 upgrade is
routing *reasoning queries* (not just multi-step) to the agent, so the long tail
of "understand what I mean and go find out" gets genuinely reasoned about rather
than answered by a blind one-shot. Kill switch `AERIS_INTERPRET_OFF=1` reverts to
the old policy (agent only for multi-step).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

# Multi-step cues — mirrors main_engine._MULTISTEP_CUES (+ a couple of Hinglish).
_MULTISTEP_CUES = (
    " and then ", " and also ", " then ", " after that ", " aur phir ",
    " uske baad ", " uske bad ", " followed by ", ", then ", "; ",
    " karke ", " kar ke ", " karkay ", " iske baad ", " phir ",
)

# An actionable verb anywhere in the utterance (Hinglish + English).
_ACTION = re.compile(
    r"\b(kholo?|khol|band|bhej\w*|banao?|bana|likh\w*|set|karo?|chalao?|chala|"
    r"dhoond\w*|dhundo|khoj\w*|search|find|play|open|close|send|delete|create|"
    r"hatao?|nikaal\w*|dikha\w*|start|stop|schedule|remind|note|add|download|"
    r"install|message|call|email|whatsapp|post|book|order)\b")

# A query that must inspect state / decide among options → wants reasoning.
_REASONING = re.compile(
    r"\b(kon\s?sa|kon\s?si|kaun\s?sa|kaun\s?si|konsa|konsi|sabse|sab\s?se|"
    r"which|kitne|kitna|kitni|list|saari|saare|sabhi|purani|puraan\w*|latest|"
    r"newest|oldest|biggest|largest|smallest|compare|dhoond\w*|dhundo|khoj\w*|"
    r"find|search|kahan|kaha|where|summar\w*|analyse|analyze)\b")


@dataclass(frozen=True)
class Plan:
    strategy: str     # "agent" | "tool" | "chat"
    reason: str


class Interpreter:
    def __init__(self, enabled: Optional[bool] = None):
        if enabled is None:
            enabled = os.environ.get("AERIS_INTERPRET_OFF", "") not in ("1", "true", "True")
        self.enabled = enabled

    # ── signals ──────────────────────────────────────────────────────────
    def _multistep(self, low: str) -> bool:
        padded = f" {low.strip()} "
        if any(cue in padded for cue in _MULTISTEP_CUES):
            return True
        if padded.count(" and ") + padded.count(" aur ") >= 2:
            return True
        return len(low.split()) >= 14

    def _actionable(self, low: str) -> bool:
        return bool(_ACTION.search(low))

    def _reasoning(self, low: str) -> bool:
        return bool(_REASONING.search(low))

    # ── policy ───────────────────────────────────────────────────────────
    def plan(self, text: str, *, has_tools: bool = True,
             agent_available: bool = True) -> Plan:
        low = (text or "").lower()
        if not low.strip():
            return Plan("chat", "empty")
        multistep = self._multistep(low)
        # Reasoning-query → agent is the P5 upgrade; the kill switch reverts to
        # "agent only for multi-step".
        reasoning = self.enabled and self._reasoning(low)
        if agent_available and (multistep or reasoning):
            return Plan("agent", "multistep" if multistep else "reasoning-query")
        if has_tools and self._actionable(low):
            return Plan("tool", "single-step actionable")
        return Plan("chat", "conversational")


_DEFAULT: Optional[Interpreter] = None


def get() -> Interpreter:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Interpreter()
    return _DEFAULT
