"""Quality, scoring, converters and teacher verifiers."""
import json
import random

from brain.contract import canonical, load_tools, make_call
from brain.convert import hf_sets, hinglish_top, massive
from brain.quality import run
from brain.score import aggregate, score_pair
from brain.teacher import hinglish_chat_jobs, paraphrase_jobs

TOOLS = load_tools()


def rec(text, out, rid="r", **kw):
    return {"id": rid, "tools": list(TOOLS), "messages": [{"role": "user", "content": text},
                                                          {"role": "assistant", "content": out}], **kw}


# ── quality ────────────────────────────────────────────────────────────────
def test_quality_decontaminates_dedupes_and_exempts_short_commands():
    torch = make_call(TOOLS, ("flashlight", {"state": "on"}))
    msg = make_call(TOOLS, ("send_message", {"contact": "Ravi", "message": "I am late today"}))
    train = [rec("torch on", torch, "a"), rec("torch on", torch, "b"),          # dup
             rec("tell Ravi I am late today", msg, "c"),                          # in eval → drop
             rec("please tell Ravi I am late today", msg, "d")]                   # ≥0.8 overlap → drop
    evals = [rec("torch on", torch, "e1"), rec("tell Ravi I am late today", msg, "e2")]
    out = run(train, evals, TOOLS, log=lambda *a: None)
    assert [r["id"] for r in out] == ["a"]  # "torch on" (2 words) is exempt from decontam


def test_quality_drops_ungrounded_labels():
    bad = rec("call my brother", make_call(TOOLS, ("call", {"contact": "Rahul"})))
    assert run([bad], [], TOOLS, log=lambda *a: None) == []


# ── score ──────────────────────────────────────────────────────────────────
def test_score_exact_action_and_partial_credit():
    gold = make_call(TOOLS, ("send_message", {"contact": "Ravi", "message": "hi", "app": "whatsapp"}))
    perfect = score_pair(gold, canonical(gold), TOOLS)
    assert perfect["valid"] and perfect["exact"] and perfect["action"]
    wrong = make_call(TOOLS, ("send_message", {"contact": "Ravi", "message": "hello", "app": "whatsapp"}))
    r = score_pair(gold, canonical(wrong), TOOLS)
    assert r["action"] and not r["exact"] and r["tp"] > 0 and r["fn"] > 0
    junk = score_pair(gold, "sure! I'll message Ravi", TOOLS)
    assert not junk["valid"] and junk["action"] is False
    rep = aggregate([perfect, r, junk])
    assert rep["action_pct"] == 66.67 and rep["exact_pct"] == 33.33


def test_score_phone_numbers_compare_digits():
    gold = make_call(TOOLS, ("call", {"number": "7300 978845"}))
    pred = make_call(TOOLS, ("call", {"number": "+91 7300978845"}))
    assert score_pair(gold, canonical(pred), TOOLS)["exact"]


# ── Hinglish-TOP ───────────────────────────────────────────────────────────
def test_top_parse_and_mapping():
    root = hinglish_top.parse_top("[IN:CREATE_ALARM create an alarm [SL:DATE_TIME at 4 pm ] and [SL:DATE_TIME 9 pm on tuesday ] ]")
    out = hinglish_top.to_contract(root, "create an alarm at 4 pm and 9 pm on tuesday")
    assert [c["args"]["time"] for c in out["calls"]] == ["4 pm", "9 pm on tuesday"]
    root = hinglish_top.parse_top("[IN:SEND_MESSAGE [SL:RECIPIENT sam ] ko bolo ki [SL:CONTENT_EXACT mai late hoon ] ]")
    out = hinglish_top.to_contract(root, "sam ko bolo ki mai late hoon")
    assert out["calls"][0]["args"] == {"contact": "sam", "message": "mai late hoon"}
    root = hinglish_top.parse_top("[IN:GET_WEATHER aaj mausam kaisa hai ]")
    assert hinglish_top.to_contract(root, "aaj mausam kaisa hai")["type"] == "escalate"
    assert hinglish_top.parse_top("[IN:BROKEN") is None


# ── MASSIVE ────────────────────────────────────────────────────────────────
def test_massive_slots_and_mapping():
    sl = massive.slots_of("wake me up at [time : five am] [date : this week]")
    assert sl == {"time": ["five am"], "date": ["this week"]}
    out = massive.to_contract("alarm_set", "wake me up at five am this week", sl)
    assert out["calls"][0]["args"] == {"time": "five am", "days": "this week"}
    sl = massive.slots_of("play [song_name : sleepyhead] by [artist_name : passion pit]")
    out = massive.to_contract("play_music", "play sleepyhead by passion pit", sl)
    assert out["calls"][0]["args"]["query"] == "sleepyhead by passion pit"
    assert massive.to_contract("iot_coffee", "make me coffee", {}) is None


# ── HF sets ────────────────────────────────────────────────────────────────
def test_calls_of_accepts_common_shapes():
    nested = {"tool_calls": [{"function": {"name": "f", "arguments": '{"a": 1}'}}]}
    flat = {"tool_calls": [{"name": "g", "arguments": {"b": 2}}]}
    assert hf_sets._calls_of(nested) == [("f", {"a": 1})]
    assert hf_sets._calls_of(flat) == [("g", {"b": 2})]
    assert hf_sets._calls_of({"tool_calls": None}) == []


def test_spec_from_xlam_and_openai_schemas():
    xl = {"name": "get_weather", "description": "d", "parameters": {
        "city": {"type": "str", "description": "c"}, "days": {"type": "int, optional", "description": "n"},
        "tags": {"type": "List[str]", "description": "t"}}}
    s = hf_sets.spec_from_schema(xl)
    assert s["params"]["city"]["type"] == "string" and s["params"]["days"]["type"] == "integer"
    assert s["params"]["tags"]["type"] == "any"
    oa = {"type": "function", "function": {"name": "f", "parameters": {"type": "object",
          "properties": {"u": {"type": "string", "enum": ["c", "f"]}}, "required": ["u"]}}}
    s = hf_sets.spec_from_schema(oa)
    assert s["params"]["u"] == {"type": "enum", "values": ["c", "f"], "description": ""} and s["required"] == ["u"]


# ── teacher verifiers ──────────────────────────────────────────────────────
def test_paraphrase_keeps_only_span_preserving_rewrites():
    r = rec("whatsapp Ravi saying I'm late", make_call(TOOLS, ("send_message", {"contact": "Ravi", "message": "I'm late", "app": "whatsapp"})), lang="en")
    job = paraphrase_jobs([r], per_record=3)[0]
    outs = json.dumps(["yaar send Ravi a whatsapp, I'm late",   # keeps spans → keep
                       "tell Rahul I'm late on whatsapp",          # name changed → drop
                       "whatsapp Ravi saying I'm late",            # identical → drop
                       "रवि को बोलो I'm late Ravi"])                # Devanagari → drop
    kept = job.accept(outs)
    assert [k["messages"][0]["content"] for k in kept] == ["yaar send Ravi a whatsapp, I'm late"]


def test_hinglish_chat_rejects_bad_shapes():
    r = {"id": "s", "source": "smol", "messages": [
        {"role": "user", "content": "hi"}, {"role": "assistant", "content": {"type": "reply", "text": "Hello!"}}]}
    job = hinglish_chat_jobs([r])[0]
    assert job.accept('[["user","hello yaar"],["aeris","Hello! Kya haal hai?"]]')[0]["lang"] == "hi"
    assert job.accept('[["user","hello"]]') == []                      # turn count changed
    assert job.accept('[["user","hi"],["aeris","- point one\\n- two"]]') == []  # markdown/newline
