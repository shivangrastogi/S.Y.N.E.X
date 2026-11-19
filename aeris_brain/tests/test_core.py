"""Core pipeline tests: grammar, contract, prompt, augmentation, generator."""
import json
import random

import pytest

from brain.augment import augment
from brain.contract import canonical, load_tools, make_call, parse, validate
from brain.expand import Seg, Template, join, slot_values
from brain.generate import Generator, assign_splits, random_now
from brain.prompt import signature, system_prompt
from brain.templates import TEMPLATES

TOOLS = load_tools()


# ── grammar ────────────────────────────────────────────────────────────────
def test_template_alternation_optional_and_slots():
    t = Template("(set|put) [an] alarm (for|at) {time}")
    seen = set()
    rng = random.Random(0)
    for _ in range(200):
        segs = t.sample(rng, lambda s: "7 am")
        seen.add(join(segs))
        assert slot_values(segs) == {"time": "7 am"}
    assert "set an alarm for 7 am" in seen and "put alarm at 7 am" in seen


def test_regex_style_optional_group():
    t = Template("wake me (up )?at {time}")
    outs = {join(t.sample(random.Random(i), lambda s: "6")) for i in range(50)}
    assert outs == {"wake me up at 6", "wake me at 6"}


def test_unbalanced_template_raises():
    with pytest.raises(ValueError):
        Template("(a|b")
    with pytest.raises(ValueError):
        Template("a)b")


def test_all_shipped_templates_parse_and_use_known_tools():
    for t in TEMPLATES:
        Template(t.src)
        assert t.tool in TOOLS, t.src


# ── contract ───────────────────────────────────────────────────────────────
def test_validate_good_call_and_grounding():
    out = make_call(TOOLS, ("send_message", {"contact": "Ravi", "message": "I'm late"}))
    assert validate(out, TOOLS, user_text="tell Ravi I'm late", grounded=True) == []
    errs = validate(out, TOOLS, user_text="tell Amit I'm late", grounded=True)
    assert any("not in the user's words" in e for e in errs)


def test_validate_catches_schema_errors():
    assert validate({"type": "tool_call", "calls": [{"name": "flashlight", "args": {"state": "dim"}}]}, TOOLS)
    assert validate({"type": "tool_call", "calls": [{"name": "nope", "args": {}}]}, TOOLS)
    assert validate({"type": "tool_call", "calls": [{"name": "send_message", "args": {"message": "hi"}}]}, TOOLS)  # one_of
    assert validate({"type": "plan", "goal": "x", "steps": ["only one"]}, TOOLS)
    assert validate({"type": "escalate", "reason": "bored", "query": "x"}, TOOLS)
    assert validate(make_call(TOOLS, ("flashlight", {"state": "on"})), TOOLS, allowed={"volume"})


def test_canonical_is_stable_and_type_first():
    a = make_call(TOOLS, ("set_alarm", {"days": "kal", "time": "7 baje"}))
    s = canonical(a)
    assert s.startswith('{"type":"tool_call"')
    assert s.index('"time"') < s.index('"days"')  # schema param order
    assert parse("```json\n" + s + "\n```") == json.loads(s)
    assert parse("not json") is None


# ── prompt ─────────────────────────────────────────────────────────────────
def test_signature_format_is_pinned():
    # The phone (Dart) must render byte-identical prompts — change both together.
    assert signature(TOOLS["send_message"]) == (
        "send_message(message: str, contact?: str, number?: str, app?: whatsapp|sms|telegram)"
        "  [one of: contact, number] — Send a text message to a contact or number (WhatsApp, SMS or Telegram).")
    p = system_prompt([TOOLS["flashlight"]], lang="english", now="Friday 17 October 2026, 18:40")
    assert "reply in simple English only" in p and "- flashlight(state: on|off)" in p
    # per-turn lines come after the fixed prefix (phone KV cache)
    assert p.index("Now: Friday") > p.index("no markdown.")
    assert p.startswith(system_prompt([TOOLS["flashlight"]], lang="english"))


# ── augmentation never touches slots ───────────────────────────────────────
def test_augment_preserves_slot_text():
    segs = [Seg("send a whatsapp to "), Seg("Ravi Kumar", "contact"), Seg(" saying "),
            Seg("I'll be late, sorry", "message")]
    for i in range(300):
        out = augment(segs, random.Random(i), "en", 1.5)
        assert slot_values(out) == {"contact": "Ravi Kumar", "message": "I'll be late, sorry"}


# ── generator ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def gen():
    return Generator(seed=7)


def test_generator_is_deterministic(gen):
    a = [json.dumps(x, sort_keys=True) for x in Generator(seed=7).run(60, "train")]
    b = [json.dumps(x, sort_keys=True) for x in Generator(seed=7).run(60, "train")]
    assert a == b


def test_every_generated_example_is_valid(gen):
    for ex in gen.run(1500, "train"):
        said = ""
        for m in ex["messages"]:
            if m["role"] == "user":
                said += " " + m["content"]
            else:
                assert validate(m["content"], TOOLS, allowed=set(ex["tools"]),
                                user_text=said, grounded=True) == [], ex


def test_splits_are_disjoint_and_every_label_trains():
    s = assign_splits(TEMPLATES)
    tr, dv, te = ({t.src for t in s[k]} for k in ("train", "dev", "test"))
    assert not (tr & dv) and not (tr & te) and not (dv & te)
    assert len(dv) > 30 and len(te) > 50
    key = lambda t: (t.tool, t.lang, json.dumps(t.const, sort_keys=True))
    train_keys = {key(t) for t in s["train"]}
    assert all(key(t) in train_keys for t in s["dev"] + s["test"])


def test_all_tools_and_families_appear(gen):
    tools, fams = set(), set()
    for ex in gen.run(4000, "train"):
        fams.add(ex["family"])
        for m in ex["messages"]:
            if m["role"] == "assistant":
                tools |= {c["name"] for c in m["content"].get("calls", [])}
    assert tools == set(TOOLS)
    assert {"single", "ask", "ask_complete", "pronoun", "multi", "plan", "escalate", "reply"} <= fams


def test_random_now_weekday_matches_date():
    import datetime as dt
    for i in range(50):
        s = random_now(random.Random(i))
        d = dt.datetime.strptime(s, "%A %d %B %Y, %H:%M")
        assert s.split()[0] == d.strftime("%A")
