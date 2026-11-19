"""core/chain_planner.py — multi-step chains without an LLM round-trip.

Pure: the runner gets a scripted ``run_command`` and fake sinks, so nothing
here touches the brain, the executor or the phone.
"""

import pytest

from core.chain_planner import (ChainRunner, extract_number, plan,
                                summarize_text)


def _shape(p):
    return [(s.kind, s.sink or s.text) for s in p.steps]


# ── parsing: data flow ──────────────────────────────────────────────

@pytest.mark.parametrize("text, shape", [
    ("weather batao aur phone pe bhejo",
     [("command", "weather batao"), ("sink", "phone")]),
    ("time check karke clipboard me copy karo",
     [("command", "time check karo"), ("sink", "clipboard")]),
    ("screenshot leke phone pe bhejo",
     [("command", "screenshot lo"), ("sink", "phone")]),
    ("einstein aur newton ke baare me batao, phir isko note kar lo",
     [("command", "einstein aur newton ke baare me batao"), ("sink", "note")]),
    ("einstein ke baare me batao aur hindi me translate karke note karo",
     [("command", "einstein ke baare me batao"), ("sink", "translate"),
      ("sink", "note")]),
    ("joke sunao and then copy it",
     [("command", "joke sunao"), ("sink", "clipboard")]),
    ("system stats batao aur file me save karo",
     [("command", "system stats batao"), ("sink", "file")]),
])
def test_flow_chains_parse(text, shape):
    p = plan(text)
    assert p is not None and p.condition is None
    assert _shape(p) == shape


def test_translate_sink_carries_language():
    p = plan("weather batao aur hindi me translate karo")
    assert p.steps[1].args == {"lang": "hindi"}
    assert plan("weather batao aur translate karo").steps[1].args == \
        {"lang": "english"}


@pytest.mark.parametrize("text", [
    # plain multi-command — the normal splitter's job, no data flows
    "chrome kholo aur notepad band karo",
    "brave aur chrome aur file explorer open karo",
    "weather batao aur time batao",
    # a sink with its OWN payload is a plain command, not a consumer
    "note karo ki doodh lana hai",
    "doodh aur bread note karo",
    "weather batao aur ye line copy karo hello world",
    # chit-chat that merely contains "agar ... to"
    "agar tum insaan hote to kya karte",
    "agar mujhe neend na aaye to kya karu",
    # a verbatim skill pattern / bare prompts
    "copy karo",
    "yeh phone pe bhejo",
    "",
])
def test_non_chains_are_left_alone(text):
    assert plan(text, has_previous_reply=True) is None


def test_single_pointer_uses_previous_reply_only_when_there_is_one():
    assert plan("isko hindi me translate karo") is None
    p = plan("isko hindi me translate karo", has_previous_reply=True)
    assert p.uses_previous_reply and _shape(p) == [("sink", "translate")]
    p = plan("ye note kar lo", has_previous_reply=True)
    assert _shape(p) == [("sink", "note")]


# ── parsing: conditions ─────────────────────────────────────────────

@pytest.mark.parametrize("text, probe, op, value, then, else_", [
    ("agar battery 30 se kam hai to brightness kam karo",
     "battery status", "lt", 30, "brightness kam karo", ""),
    ("agar battery 20% se kam ho toh power saver on karo",
     "battery status", "lt", 20, "power saver on karo", ""),
    ("if cpu is above 80 then task manager kholo warna time batao",
     "cpu usage", "gt", 80, "task manager kholo", "time batao"),
    ("agar ram 70 percent se zyada hai to chrome band karo",
     "ram usage", "gt", 70, "chrome band karo", ""),
])
def test_conditions_parse(text, probe, op, value, then, else_):
    p = plan(text)
    assert p is not None and p.kind == "condition"
    c = p.condition
    assert (c.probe, c.op, c.value) == (probe, op, value)
    assert (p.then_text, p.else_text) == (then, else_)


# ── number extraction ───────────────────────────────────────────────

def test_extract_number_picks_the_subjects_reading():
    stats = "CPU: 23% · RAM: 7.2 GB / 15.4 GB (61%) · Disk: 80 GB free"
    assert extract_number(stats, "cpu") == 23
    assert extract_number(stats, "ram") == 61
    assert extract_number("Battery 45%, battery par.", "battery") == 45
    assert extract_number("Mausam 25 degrees hai", "") == 25
    assert extract_number("koi number nahi", "battery") is None


# ── runner ──────────────────────────────────────────────────────────

class _Script:
    """run_command double: canned (reply, intent, paused) per text."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, text):
        self.calls.append(text)
        return self.table.get(text, ("[ran] " + text, "x", False))


def _sinks(log):
    def rec(name):
        def fn(payload, args):
            log.append((name, payload, dict(args)))
            return f"{name} done"
        return fn
    return {n: rec(n) for n in
            ("note", "file", "clipboard", "phone", "translate", "summarize")}


def test_flow_feeds_the_result_forward():
    log = []
    run = _Script({"weather batao": ("Mausam 25 degree ☀️", "get_weather", False)})
    res = ChainRunner(run, _sinks(log)).run(plan("weather batao aur phone pe bhejo"))
    assert res.stopped == "done"
    assert log == [("phone", "Mausam 25 degree", {})]      # emoji stripped
    assert res.reply == "Mausam 25 degree ☀️\nphone done"


def test_transforming_sink_hands_its_output_on():
    log = []
    sinks = _sinks(log)
    sinks["translate"] = lambda p, a: log.append(("tr", p, a)) or "[llm] namaste"
    run = _Script({"hello bolo": ("hello", "i", False)})
    ChainRunner(run, sinks).run(plan("hello bolo aur hindi me translate karke note karo"))
    assert log[-1] == ("note", "namaste", {})


def test_failed_step_stops_the_chain():
    log = []
    run = _Script({"weather batao": ("Error executing get_weather: boom", "get_weather", False)})
    res = ChainRunner(run, _sinks(log)).run(plan("weather batao aur note karo"))
    assert res.stopped == "failed" and log == []
    assert "Step 1" in res.reply and "roke" in res.reply


def test_paused_step_stops_and_returns_the_question():
    log = []
    run = _Script({"reminder lagao": ("Kis time pe?", "set_reminder", True)})
    res = ChainRunner(run, _sinks(log)).run(plan("reminder lagao aur phone pe bhejo"))
    assert res.stopped == "paused" and res.reply == "Kis time pe?" and log == []


def test_sink_failure_is_reported():
    run = _Script({"weather batao": ("25 degree", "get_weather", False)})
    sinks = _sinks([])
    sinks["phone"] = lambda p, a: "Error: koi phone paired nahi"
    res = ChainRunner(run, sinks).run(plan("weather batao aur phone pe bhejo"))
    assert res.stopped == "failed" and "paired nahi" in res.reply


def test_sink_exception_does_not_escape():
    run = _Script({"weather batao": ("25 degree", "get_weather", False)})
    sinks = _sinks([])
    sinks["note"] = lambda p, a: 1 / 0
    res = ChainRunner(run, sinks).run(plan("weather batao aur note karo"))
    assert res.stopped == "failed" and "note fail" in res.reply


def test_optimize_fuses_screenshot_to_phone():
    log = []
    run = _Script({
        "screenshot lo": ("Screenshot saved", "screenshot_full", False),
        "screenshot phone pe bhejo": ("Screenshot phone pe bhej diya", "screenshot_to_phone", False),
    })
    fuse = lambda prod, sink: ("screenshot phone pe bhejo"
                               if prod == "screenshot_full" and sink == "phone" else None)
    res = ChainRunner(run, _sinks(log), optimize=fuse).run(
        plan("screenshot leke phone pe bhejo"))
    assert log == []                                  # no text was sent
    assert run.calls == ["screenshot lo", "screenshot phone pe bhejo"]
    assert res.stopped == "done"


def test_previous_reply_is_the_payload():
    log = []
    res = ChainRunner(_Script({}), _sinks(log)).run(
        plan("ye note kar lo", has_previous_reply=True),
        previous_reply="Einstein ne relativity di.")
    assert log == [("note", "Einstein ne relativity di.", {})]
    assert res.reply == "note done"


def test_condition_true_runs_then_branch():
    run = _Script({"battery status": ("Battery 22%, battery par.", "battery_status", False),
                   "brightness kam karo": ("Brightness 40%", "brightness_down", False)})
    res = ChainRunner(run, {}).run(plan("agar battery 30 se kam hai to brightness kam karo"))
    assert run.calls == ["battery status", "brightness kam karo"]
    assert res.reply.startswith("Battery 22 hai — 30 se kam hai.")
    assert res.stopped == "done"


def test_condition_false_without_else_does_nothing():
    run = _Script({"battery status": ("Battery 85%, plugged in.", "battery_status", False)})
    res = ChainRunner(run, {}).run(plan("agar battery 30 se kam hai to brightness kam karo"))
    assert run.calls == ["battery status"]
    assert res.stopped == "skipped" and "kuch nahi kiya" in res.reply


def test_condition_false_runs_else_branch():
    run = _Script({"cpu usage": ("CPU: 12% · RAM: 3 GB / 15 GB (40%)", "system_stats", False)})
    res = ChainRunner(run, {}).run(
        plan("if cpu is above 80 then task manager kholo warna time batao"))
    assert run.calls == ["cpu usage", "time batao"]
    assert "CPU 12 hai — 80 se zyada nahi hai" in res.reply


def test_condition_branch_can_itself_be_a_chain():
    log = []
    run = _Script({"battery status": ("Battery 10%", "battery_status", False),
                   "weather batao": ("25 degree", "get_weather", False)})
    ChainRunner(run, _sinks(log)).run(
        plan("agar battery 20 se kam hai to weather batao aur phone pe bhejo"))
    assert log == [("phone", "25 degree", {})]


def test_condition_without_a_number_fails_cleanly():
    run = _Script({"battery status": ("Battery sensor nahi mila", "battery_status", False)})
    res = ChainRunner(run, {}).run(plan("agar battery 30 se kam hai to time batao"))
    assert res.stopped == "failed" and run.calls == ["battery status"]


def test_summarize_falls_back_to_leading_sentences_offline():
    text = "Pehla vakya. Doosra vakya. Teesra vakya."
    assert summarize_text(text, None) == "Pehla vakya. Doosra vakya."
    assert summarize_text(text, lambda t: "Chhota saar") == "Chhota saar"
    assert summarize_text(text, lambda t: None) == "Pehla vakya. Doosra vakya."
