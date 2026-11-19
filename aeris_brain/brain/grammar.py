"""JSON Schema for the output contract, restricted to the tools offered.

Used for constrained decoding so the model CANNOT emit malformed output:
  - vLLM:       SamplingParams(guided_decoding=GuidedDecodingParams(json=schema))
  - llama.cpp:  json_schema_to_grammar(schema) → GBNF (on the phone too)
  - LiteRT-LM:  its constrained tool-use decoding
Per-tool arg schemas carry enums, so even "flashlight": {"state": "dim"} is
impossible. (Span grounding is still checked in code after decoding.)
"""
from __future__ import annotations

import json


def _arg_schema(p: dict) -> dict:
    t = p["type"]
    if t == "enum":
        return {"type": "string", "enum": p["values"]}
    if t == "integer":
        s = {"type": "integer"}
        if "min" in p:
            s["minimum"] = p["min"]
        if "max" in p:
            s["maximum"] = p["max"]
        return s
    if t == "boolean":
        return {"type": "boolean"}
    if t == "number":
        return {"type": "number"}
    if t == "any":
        return {}
    return {"type": "string", "minLength": 1}


def call_schema(tool: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "name": {"const": tool["name"]},
            "args": {"type": "object",
                     "properties": {k: _arg_schema(p) for k, p in tool["params"].items()},
                     "required": list(tool.get("required", [])),
                     "additionalProperties": False},
        },
        "required": ["name", "args"], "additionalProperties": False,
    }


def contract_schema(tools: list[dict]) -> dict:
    names = [t["name"] for t in tools]
    one = lambda props, req: {"type": "object", "properties": props, "required": req,
                              "additionalProperties": False}
    variants = [
        one({"type": {"const": "ask"}, "text": {"type": "string", "minLength": 1},
             "pending": {"type": "string", "enum": names} if names else {"type": "string"}},
            ["type", "text"]),
        one({"type": {"const": "reply"}, "text": {"type": "string", "minLength": 1}}, ["type", "text"]),
        one({"type": {"const": "plan"}, "goal": {"type": "string", "minLength": 1},
             "steps": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 2}},
            ["type", "goal", "steps"]),
        one({"type": {"const": "escalate"},
             "reason": {"type": "string", "enum": ["knowledge", "live_info", "complex", "no_tool"]},
             "query": {"type": "string", "minLength": 1}}, ["type", "reason", "query"]),
    ]
    if tools:
        variants.insert(0, one({"type": {"const": "tool_call"},
                                "calls": {"type": "array", "minItems": 1,
                                          "items": {"anyOf": [call_schema(t) for t in tools]}}},
                               ["type", "calls"]))
    return {"anyOf": variants}


if __name__ == "__main__":
    from .contract import load_tools
    print(json.dumps(contract_schema(list(load_tools().values())[:2]), indent=1))
