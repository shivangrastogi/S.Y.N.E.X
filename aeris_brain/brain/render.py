"""Neutral record → training samples for any chat model.

One sample per ASSISTANT TURN:
    prompt     = tokenizer.apply_chat_template(history up to that turn,
                                               add_generation_prompt=True)
    completion = canonical contract JSON + the template's end-of-turn marker

Why not render the whole conversation once and mask it? Because chat
templates render history differently from a live generation prompt
(Qwen3 inserts/strips <think> blocks; Gemma folds the system prompt into
the first user turn). Building each sample exactly as the phone will build
its prompt guarantees train == inference, token for token.

TRL's SFTTrainer accepts {"prompt", "completion"} string pairs and masks
the prompt (completion_only_loss) — no custom collator needed.
"""
from __future__ import annotations

from .contract import canonical, load_tools
from .nlu import chat_messages as _task_messages
from .prompt import system_prompt


def offered_specs(record: dict, tools: dict) -> list[dict]:
    names = record.get("tools") or list(tools)
    inline = {t["name"]: t for t in record.get("tool_specs", [])}  # converted datasets bring their own
    return [inline.get(n) or tools[n] for n in names if n in inline or n in tools]


def chat(record: dict, tools: dict) -> list[dict]:
    """System + user/assistant messages; assistant content = canonical JSON."""
    if record.get("task") in ("nlu", "memory"):
        return _task_messages(record, tools)
    lang = record.get("prompt_lang") or "match"
    sys_text = system_prompt(offered_specs(record, tools), lang=lang,
                             now=record.get("now"), memory=record.get("memory"))
    msgs = [{"role": "system", "content": sys_text}]
    for m in record["messages"]:
        c = m["content"]
        msgs.append({"role": m["role"], "content": canonical(c) if isinstance(c, dict) else c})
    return msgs


def end_marker(tokenizer, **template_kwargs) -> str:
    """The text a template emits right after an assistant message
    (e.g. '<|im_end|>' for Qwen, '<end_of_turn>' for Gemma)."""
    probe = "@@AERIS_END_PROBE@@"
    full = tokenizer.apply_chat_template(
        [{"role": "user", "content": "x"}, {"role": "assistant", "content": probe}],
        tokenize=False, **template_kwargs)
    tail = full[full.index(probe) + len(probe):]
    return tail.rstrip()


def samples(record: dict, tools: dict, tokenizer, **template_kwargs) -> list[dict]:
    msgs = chat(record, tools)
    end = end_marker(tokenizer, **template_kwargs)
    out = []
    for i, m in enumerate(msgs):
        if m["role"] != "assistant":
            continue
        prompt = tokenizer.apply_chat_template(msgs[:i], tokenize=False,
                                               add_generation_prompt=True, **template_kwargs)
        out.append({"prompt": prompt, "completion": m["content"] + end,
                    "id": record.get("id"), "turn": sum(1 for x in msgs[:i] if x["role"] == "assistant")})
    return out


def inference_prompt(history: list[dict], record_like: dict, tools: dict, tokenizer, **kw) -> str:
    """What the app/eval loop feeds the model for the next turn."""
    rec = dict(record_like, messages=history)
    msgs = chat(rec, tools)
    return tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **kw)


if __name__ == "__main__":  # quick look at a rendered system prompt
    import json
    import sys
    tools = load_tools()
    rec = json.loads(open(sys.argv[1], encoding="utf-8").readline())
    for m in chat(rec, tools):
        print(f"--- {m['role']} ---\n{m['content']}\n")
