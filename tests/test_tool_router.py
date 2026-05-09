"""Tests for LLM tool-call parsing and routing."""

from __future__ import annotations

import pytest

from core.tool_router import ToolCall, ToolRouter, parse_tool_response


# ---------- parse_tool_response ----------

def test_parse_plain_text_treated_as_chat():
    call = parse_tool_response("hello there sir")
    assert call.kind == "chat"
    assert call.reply == "hello there sir"


def test_parse_empty_input_is_noop():
    assert parse_tool_response("").kind == "noop"
    assert parse_tool_response(None).kind == "noop"


def test_parse_json_tool_call():
    call = parse_tool_response('{"tool": "open_app", "args": {"app_name": "chrome"}}')
    assert call.kind == "tool"
    assert call.name == "open_app"
    assert call.args == {"app_name": "chrome"}


def test_parse_json_chat():
    call = parse_tool_response('{"tool": "chat", "reply": "kaise ho"}')
    assert call.kind == "chat"
    assert call.reply == "kaise ho"


def test_parse_json_plan():
    raw = '{"tool":"plan","steps":[{"tool":"open_app","args":{"app_name":"chrome"}}]}'
    call = parse_tool_response(raw)
    assert call.kind == "plan"
    assert len(call.steps) == 1


def test_parse_fenced_json():
    raw = '```json\n{"tool": "lock_screen", "args": {}}\n```'
    call = parse_tool_response(raw)
    assert call.kind == "tool"
    assert call.name == "lock_screen"


def test_parse_json_with_prose_around_it():
    raw = 'Sure thing! Here is the call:\n{"tool": "get_time", "args": {}}\nDone.'
    call = parse_tool_response(raw)
    assert call.kind == "tool"
    assert call.name == "get_time"


def test_parse_malformed_json_falls_back_to_chat():
    call = parse_tool_response('{"tool": broken')
    assert call.kind == "chat"


# ---------- ToolRouter ----------

class _FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, intent, slots):
        self.calls.append((intent, slots))
        return f"executed:{intent}"


def test_router_executes_single_tool_call():
    fx = _FakeExecutor()
    router = ToolRouter(fx)
    out = router.execute(parse_tool_response('{"tool":"open_app","args":{"app_name":"chrome"}}'))
    assert out == "executed:open_app"
    assert fx.calls == [("open_app", {"app_name": "chrome"})]


def test_router_executes_plan_in_order():
    fx = _FakeExecutor()
    router = ToolRouter(fx)
    raw = (
        '{"tool":"plan","steps":['
        '{"tool":"open_app","args":{"app_name":"chrome"}},'
        '{"tool":"play_youtube","args":{"query":"lofi"}}'
        ']}'
    )
    out = router.execute(parse_tool_response(raw))
    assert "executed:open_app" in out
    assert "executed:play_youtube" in out
    assert fx.calls == [
        ("open_app", {"app_name": "chrome"}),
        ("play_youtube", {"query": "lofi"}),
    ]


def test_router_returns_chat_reply_for_chat_kind():
    fx = _FakeExecutor()
    router = ToolRouter(fx)
    out = router.execute(parse_tool_response('{"tool":"chat","reply":"theek hai"}'))
    assert out == "theek hai"
    assert fx.calls == []


def test_router_handles_executor_exception():
    class _BoomExec:
        def execute(self, intent, slots):
            raise RuntimeError("boom")
    router = ToolRouter(_BoomExec())
    out = router.execute(ToolCall(kind="tool", name="open_app", args={}))
    assert "fail" in out.lower()


def test_router_remember_fact_writes_to_memory():
    class _Mem:
        def __init__(self):
            self.facts = {}
        def set(self, k, v):
            self.facts[k] = v
    mem = _Mem()
    router = ToolRouter(_FakeExecutor(), memory=mem)
    out = router.execute(ToolCall(
        kind="tool", name="remember_fact",
        args={"key": "favorite_color", "value": "blue"},
    ))
    assert mem.facts == {"favorite_color": "blue"}
    assert "blue" in out
