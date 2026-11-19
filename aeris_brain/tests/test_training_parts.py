"""Grammar schema, eval loop (fake model), preference pairs, render."""
import collections
import json
import random

from brain.contract import canonical, load_tools, make_call, validate
from brain.evaluate import predict, score_preds
from brain.generate import Generator
from brain.grammar import contract_schema
from brain.prefs import pairs
from brain.render import end_marker, samples

TOOLS = load_tools()


class FakeTok:
    """Minimal chat template: <|role|>content<|end|> — prefix-consistent."""
    def apply_chat_template(self, msgs, tokenize=False, add_generation_prompt=False, **kw):
        s = "".join(f"<|{m['role']}|>{m['content']}<|end|>\n" for m in msgs)
        return s + ("<|assistant|>" if add_generation_prompt else "")


def test_end_marker_and_samples():
    tok = FakeTok()
    assert end_marker(tok) == "<|end|>"
    rec = next(Generator(seed=3).run(1, "train"))
    ss = samples(rec, TOOLS, tok)
    assert len(ss) == sum(1 for m in rec["messages"] if m["role"] == "assistant")
    assert ss[0]["prompt"].endswith("<|assistant|>") and ss[0]["completion"].endswith("<|end|>")
    assert ss[0]["prompt"].startswith("<|system|>You are AERIS")


def test_eval_loop_with_perfect_and_broken_models():
    recs = list(Generator(seed=5).run(80, "test"))
    for i, r in enumerate(recs):
        r["id"] = f"x{i}"
    # perfect model: answer from a lookup keyed by the prompt
    lookup = {}
    tok = FakeTok()
    from brain.evaluate import prompts_for
    for rid, turn, p in prompts_for(recs, tok, TOOLS):
        r = next(x for x in recs if x["id"] == rid)
        lookup[p] = canonical([m for m in r["messages"] if m["role"] == "assistant"][turn]["content"]) + "<|end|>"
    preds = predict(recs, lambda ps: [lookup[p] for p in ps], tok, TOOLS)
    rep = score_preds(recs, preds, TOOLS)
    assert rep["decision_pct"] == 100.0 and rep["exact_pct"] == 100.0 and not rep["errors"]
    broken = predict(recs, lambda ps: ["I think so!"] * len(ps), tok, TOOLS)
    rep = score_preds(recs, broken, TOOLS)
    assert rep["valid_pct"] == 0.0 and rep["errors"]


def test_contract_schema_shape():
    s = contract_schema([TOOLS["flashlight"], TOOLS["send_message"]])
    kinds = [v["properties"]["type"]["const"] for v in s["anyOf"]]
    assert kinds == ["tool_call", "ask", "reply", "plan", "escalate"]
    calls = s["anyOf"][0]["properties"]["calls"]["items"]["anyOf"]
    fl = next(c for c in calls if c["properties"]["name"]["const"] == "flashlight")
    assert fl["properties"]["args"]["properties"]["state"]["enum"] == ["on", "off"]
    assert contract_schema([])["anyOf"][0]["properties"]["type"]["const"] == "ask"


def test_preference_pairs_are_wellformed_near_misses():
    recs = list(Generator(seed=11).run(800, "train"))
    ps = pairs(recs, TOOLS, seed=2)
    kinds = collections.Counter(p["kind"] for p in ps)
    assert {"guess_instead_of_ask", "ask_instead_of_act", "sibling_tool", "corrupt_span"} <= set(kinds)
    for p in ps:
        assert p["chosen"] != p["rejected"]
        assert validate(json.loads(p["rejected"]), TOOLS) == []
