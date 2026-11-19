"""Brain v2: understanding (NLU), memory, teacher chat, diversity and the audit gate."""
import json
import random

from brain import audit, langmix, memory_data, nlu, quality
from brain.build_v2 import nlu_from_turns
from brain.contract import load_tools
from brain.diversity import NAMES, balanced_names, grid
from brain.render import chat
from brain.teacher import chat_grid_jobs

TOOLS = load_tools()


# ── language mix ──────────────────────────────────────────────────────────
def test_lang_labels_cover_the_spectrum():
    assert langmix.lang_label("set an alarm for 7 am") == "english"
    assert langmix.lang_label("kal subah 7 baje ka alarm laga do") in ("hinglish", "hindi_roman")
    assert langmix.lang_label("mujhe bahut neend aa rahi hai yaar") == "hindi_roman"
    assert langmix.lang_label("कल सुबह अलार्म") == "devanagari"
    assert langmix.cmi("play some music") == 0.0
    assert langmix.cmi("thoda music play karo please") > 20


def test_spell_vary_never_touches_labelled_spans():
    rng = random.Random(1)
    text = "Rahul ko bolo ki kya plan hai, nahi aa paunga"
    for _ in range(50):
        out = langmix.spell_vary(text, ["kya plan hai, nahi aa paunga"], rate=1.0, rng=rng)
        assert "kya plan hai, nahi aa paunga" in out


# ── diversity ─────────────────────────────────────────────────────────────
def test_grid_is_balanced_and_personas_never_repeat():
    cells = grid(random.Random(5), 400)
    assert len({c.persona for c in cells}) == 400
    mixes = {m: sum(c.mix == m for c in cells) for m in ("english", "en_heavy", "balanced", "hi_heavy")}
    assert max(mixes.values()) - min(mixes.values()) <= 1
    for c in cells:
        if c.mix == "english":
            assert "English" in c.register


def test_grid_scales_past_the_base_persona_space():
    cells = grid(random.Random(2026), 12_600)   # the 01b notebook's default size
    assert len({c.persona for c in cells}) == 12_600


def test_names_balanced_by_gender_and_region():
    names = balanced_names(random.Random(2), 900)
    info = {n: (g, r) for n, g, r, _ in NAMES}
    m = sum(info[n][0] == "m" for n in names)
    f = sum(info[n][0] == "f" for n in names)
    assert abs(m - f) / len(names) < 0.1
    assert len({info[n][1] for n in names}) >= 6


# ── NLU ───────────────────────────────────────────────────────────────────
def _alarm_record():
    return {"id": "x1", "source": "template", "split": "train", "lang": "hi",
            "messages": [{"role": "user", "content": "kal subah 7 baje ka alarm laga do"},
                         {"role": "assistant", "content": {"type": "tool_call", "calls": [
                             {"name": "set_alarm", "args": {"time": "kal subah 7 baje"}}]}}]}


def test_nlu_from_turn_is_exact():
    (rec,) = nlu.from_turn(_alarm_record(), TOOLS)
    n = rec["nlu"]
    assert n["intent"] == "set_alarm" and n["act"] == "command"
    assert n["slots"] == [{"k": "time", "v": "kal subah 7 baje"}]
    assert n["keywords"][0] == "kal subah 7 baje" and "alarm" in n["keywords"]
    assert not nlu.validate_nlu(rec, set(nlu.intents(TOOLS)))


def test_nlu_validator_rejects_invented_keywords_and_labels():
    rec = nlu.make_nlu("aaj bahut thak gaya", "chat.smalltalk", "negative", "tired", source="t", rid="r")
    assert not nlu.validate_nlu(rec, set(nlu.intents(TOOLS)))
    bad = json.loads(json.dumps(rec))
    bad["nlu"]["keywords"].append("exhausted")
    bad["nlu"]["emotion"] = "melancholy"
    errs = nlu.validate_nlu(bad, set(nlu.intents(TOOLS)))
    assert any("keyword" in e for e in errs) and any("emotion" in e for e in errs)


def test_nlu_balancing_caps_frequent_intents():
    recs = [_alarm_record() | {"id": f"a{i}"} for i in range(500)]
    out = nlu_from_turns(recs, per_intent=40, rng=random.Random(1))
    assert len(out) == 40


def test_render_uses_task_heads():
    rec = nlu.make_nlu("thanks yaar", "chat.thanks", "positive", "grateful", source="t", rid="r")
    msgs = chat(rec, TOOLS)
    assert "understanding module" in msgs[0]["content"] and json.loads(msgs[2]["content"])["intent"] == "chat.thanks"
    mem = nlu.make_memory(["mera birthday 12 March ko hai"], ["mera birthday 12 March ko hai"], source="t", rid="m")
    assert json.loads(chat(mem, TOOLS)[2]["content"]) == {"facts": ["mera birthday 12 March ko hai"]}


# ── memory ────────────────────────────────────────────────────────────────
def test_memory_questions_match_their_fact():
    turns, _ = memory_data.build(400, seed=3)
    for t in turns:
        q, a = t["messages"][0]["content"].lower(), t["messages"][1]["content"]["text"].lower()
        if t["meta"]["known"] and "car" in q:
            assert "bike" not in a and "scoot" not in a, (q, a)


def test_memory_answers_shift_perspective_and_admit_unknowns():
    assert memory_data.shift("meri car B2 mein parked hai", True) == "aapki car B2 mein parked hai"
    assert memory_data.shift("main Monday ko gym jaata hoon", True) == "aap Monday ko gym jaate hain"
    assert memory_data.shift("my car is parked at B2", False) == "your car is parked at B2"
    turns, mems = memory_data.build(300, seed=1)
    known = [t for t in turns if t["meta"]["known"]]
    unknown = [t for t in turns if not t["meta"]["known"]]
    assert unknown and all("nahi" in t["messages"][1]["content"]["text"] or "haven't" in t["messages"][1]["content"]["text"]
                           or "don't" in t["messages"][1]["content"]["text"] for t in unknown)
    assert all(len(t["memory"]) >= 2 for t in known)  # always with distractors
    assert all(not nlu.validate_memory(m) for m in mems)
    assert any(m["facts"] == [] for m in mems) and any(m["facts"] for m in mems)


# ── teacher chat (simulated teacher output) ───────────────────────────────
def _cell(expect="reply", mix="balanced", turns=2):
    c = grid(random.Random(9), 1)[0]
    c.expect, c.mix, c.turns = expect, mix, turns
    c.topic = "today's weather / rain forecast" if expect == "escalate" else "feeling bored, wants to chat"
    return c


def _out(turns, facts=()):
    return json.dumps({"turns": turns, "facts": list(facts)})


def test_teacher_chat_accepts_good_output_and_derives_three_heads():
    job = chat_grid_jobs([_cell()])[0]
    out = _out([
        {"user": "yaar aaj bahut bore ho raha hoon", "intent": "chat.smalltalk", "sentiment": "negative",
         "emotion": "bored", "aeris": "Arre, chalo kuch mazedaar karte hain! Ek joke sunaun?"},
        {"user": "haan sunao, mera naam Rohit hai btw", "intent": "chat.joke", "sentiment": "positive",
         "emotion": "happy", "aeris": "Rohit, ek baar ek computer ko thand lag gayi, kyunki usne Windows khol di thi!"},
    ], facts=["mera naam Rohit hai"])
    recs = job.accept(out)
    kinds = [r.get("task", "turn") for r in recs]
    assert kinds == ["turn", "nlu", "nlu", "memory"]
    assert recs[-1]["facts"] == ["mera naam Rohit hai"]
    assert recs[1]["nlu"]["emotion"] == "bored"


def test_teacher_chat_rejects_feminine_aeris_and_invented_facts():
    job = chat_grid_jobs([_cell(turns=1)])[0]
    fem = _out([{"user": "kya kar rahe ho yaar", "intent": "chat.smalltalk", "sentiment": "neutral",
                 "emotion": "curious", "aeris": "Main aapke liye music dhoondh rahi hoon."}])
    assert job.accept(fem) == []
    ok_but_bad_fact = _out([{"user": "kal mere bhai ki shaadi hai yaar", "intent": "chat.smalltalk",
                             "sentiment": "positive", "emotion": "excited", "aeris": "Wah, badhai ho! Khoob enjoy karna."}],
                           facts=["the user's brother is getting married"])
    recs = job.accept(ok_but_bad_fact)
    assert recs and recs[-1]["facts"] == []  # rephrased fact dropped, conversation kept


def test_teacher_chat_escalate_cells_hand_off_instead_of_answering():
    job = chat_grid_jobs([_cell(expect="escalate", turns=1)])[0]
    recs = job.accept(_out([{"user": "aaj baarish hogi kya Pune mein?", "intent": "question.live_info",
                             "sentiment": "neutral", "emotion": "curious", "aeris": None}]))
    target = recs[0]["messages"][-1]["content"]
    assert target == {"type": "escalate", "reason": "live_info", "query": "aaj baarish hogi kya Pune mein?"}
    assert recs[1]["nlu"]["intent"] == "question.live_info"


# ── scoring the NLU / MEMORY heads ────────────────────────────────────────
def test_score_v2_nlu_and_memory():
    from brain.score_v2 import score_task
    rec = nlu.make_nlu("kal subah 7 baje ka alarm laga do", "set_alarm", "neutral", "none", source="t", rid="n",
                       slots=[{"k": "time", "v": "kal subah 7 baje"}])
    good = nlu.canonical(rec["nlu"])
    rep = score_task([rec, rec], [good, "not json"])
    assert rep["intent_pct"] == 50.0 and rep["valid_pct"] == 50.0 and rep["slot_f1"] == 0.5
    m_empty = nlu.make_memory(["kaise ho?"], [], source="t", rid="a")
    m_fact = nlu.make_memory(["mera birthday 12 March ko hai"], ["mera birthday 12 March ko hai"], source="t", rid="b")
    rep = score_task([m_empty, m_fact], ['{"facts":["kaise ho"]}', '{"facts":["mera birthday 12 March ko hai"]}'])
    assert rep["false_memory_pct"] == 100.0 and rep["exact_pct"] == 50.0


# ── quality + audit ───────────────────────────────────────────────────────
def test_quality_validates_task_records():
    good = nlu.make_nlu("thanks yaar", "chat.thanks", "positive", "grateful", source="t", rid="g")
    bad = nlu.make_nlu("thanks yaar", "chat.thanks", "positive", "grateful", source="t", rid="b")
    bad["nlu"]["intent"] = "chat.nonsense"
    mem_bad = nlu.make_memory(["hello"], ["invented fact"], source="t", rid="m")
    kept = quality.run([good, bad, mem_bad], [], TOOLS, log=lambda *_: None)
    assert [r["id"] for r in kept] == ["g"]


def test_audit_gate_catches_bias_and_persona_slips():
    recs = [nlu.make_nlu(f"torch on karo {i}", "flashlight", "neutral", "none", source="t", rid=f"n{i}")
            for i in range(100)]
    recs.append({"source": "teacher_chat", "messages": [
        {"role": "user", "content": "kya kar rahe ho"},
        {"role": "assistant", "content": {"type": "reply", "text": "Main gaana sun rahi hoon."}}]})
    fails = audit.gate(audit.audit(recs))
    assert any("flashlight" in f for f in fails)          # one intent = 100 %
    assert any("feminine" in f for f in fails)            # AERIS must stay male
    assert any("code-mix bucket" in f for f in fails)     # no English-only turns at all
