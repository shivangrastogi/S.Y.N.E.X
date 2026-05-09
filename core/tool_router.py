"""Parse LLM JSON tool calls and dispatch them through the executor.

The LLM is expected to respond with strict JSON in one of three shapes:

    {"tool": "<name>", "args": {...}}              — call a single skill
    {"tool": "chat", "reply": "..."}               — plain text response
    {"tool": "plan", "steps": [{...}, {...}]}      — multi-step plan

Anything else (including bare prose) is treated as a chat reply.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

log = logging.getLogger(__name__)


@dataclass
class ToolCall:
    kind: str                       # "tool" | "chat" | "plan" | "noop"
    name: Optional[str] = None
    args: Optional[dict] = None
    reply: Optional[str] = None
    steps: Optional[list[dict]] = None


_FENCED_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> Optional[dict]:
    """Pull the first JSON object out of an LLM response. Tolerates fences/prose."""
    if not text:
        return None
    text = text.strip()

    fenced = _FENCED_RE.search(text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def parse_tool_response(raw: str) -> ToolCall:
    """Convert raw LLM output into a structured ToolCall."""
    if not raw or not raw.strip():
        return ToolCall(kind="noop")

    obj = _extract_json(raw)
    if not obj:
        return ToolCall(kind="chat", reply=raw.strip())

    tool = obj.get("tool")
    if tool == "chat":
        return ToolCall(kind="chat", reply=str(obj.get("reply") or "").strip() or None)
    if tool == "plan":
        steps = obj.get("steps")
        if isinstance(steps, list) and steps:
            return ToolCall(kind="plan", steps=steps)
        return ToolCall(kind="chat", reply=raw.strip())
    if isinstance(tool, str) and tool:
        args = obj.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        return ToolCall(kind="tool", name=tool, args=args)

    return ToolCall(kind="chat", reply=raw.strip())


class ToolRouter:
    """Dispatches a parsed ToolCall through the executor + memory + scheduler."""

    def __init__(self, executor, memory=None):
        self.executor = executor
        self.memory = memory

    def execute(self, call: ToolCall) -> Optional[str]:
        if call.kind == "noop":
            return None
        if call.kind == "chat":
            return call.reply
        if call.kind == "tool":
            return self._run_one(call.name, call.args or {})
        if call.kind == "plan":
            return self._run_plan(call.steps or [])
        return None

    def _run_one(self, name: str, args: dict) -> str:
        if name == "remember_fact" and self.memory:
            key = args.get("key") or args.get("slot")
            value = args.get("value")
            if key and value:
                self.memory.set(str(key), str(value))
                return f"Yaad rakh liya: {key} = {value}"
        try:
            return self.executor.execute(name, args) or ""
        except Exception as e:
            return f"Tool '{name}' fail ho gaya: {e}"

    def _run_plan(self, steps: list[dict]) -> str:
        results: list[str] = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            tool = step.get("tool")
            args = step.get("args") or {}
            if not tool:
                continue
            r = self._run_one(tool, args if isinstance(args, dict) else {})
            if r:
                results.append(r)
        if not results:
            return "Plan execute nahi ho paya."
        return " | ".join(results)
