"""End-to-end integration: the REAL Autonomy Ladder + Ledger + Agent loop +
Goal System working together. Only the LLM and the tool runner are faked — the
governance, logging, and lifecycle are the actual modules, so this locks the
wiring built across the /loop session against regression.
"""
from datetime import datetime

from core.agent_orchestrator import AgentAction, AgentResult, AgentStep, AgentOrchestrator
from core.autonomy import TrustGate, Ledger, classify, L3_ACT
from core.goal_system import Goal, GoalStore, advance


def _noon():
    return datetime(2026, 7, 12, 12, 0).timestamp()   # daytime: not quiet hours


def _wire(tmp_path):
    """Real gate + ledger + a governance-wired orchestrator factory."""
    led = Ledger(str(tmp_path / "ledger.jsonl"), now_fn=_noon)
    gate = TrustGate(ledger=led, now_fn=_noon)

    def authorize(name, args):
        return gate.authorize(name, L3_ACT)

    def record(name, args, decision, why, result):
        led.record(action=name, args=args, cls=classify(name), level=L3_ACT,
                   decision=decision, why=why, result=result)

    def make(tool_json, ran):
        def llm(goal, steps):
            # Finish only once the tool has actually run (a non-blocked "did …"
            # observation). A restored *parked* step is still blocked, so on
            # resume the model re-issues the action — like a real one would.
            done = any(not getattr(s, "blocked", False)
                       and str(getattr(s, "observation", "")).startswith("did")
                       for s in steps)
            return ('{"tool":"final","reply":"done"}' if done else tool_json)

        def run(name, args):
            ran.append(name)
            return "did " + name

        return AgentOrchestrator(llm, run, authorize=authorize, record=record)

    return led, gate, make


# ── allow: a reversible device action runs and is logged ───────────

def test_device_action_runs_and_logs_allow(tmp_path):
    led, _, make = _wire(tmp_path)
    ran = []
    res = make('{"tool":"torch_on","args":{}}', ran).run("torch on")
    assert ran == ["torch_on"]
    assert res.stopped_reason == "final"
    entries = led.all()
    assert entries and entries[-1]["decision"] == "allow"
    assert entries[-1]["cls"] == "device"


# ── deny: a payment never runs autonomously and is logged deny ─────

def test_payment_is_denied_and_never_runs(tmp_path):
    led, _, make = _wire(tmp_path)
    ran = []
    res = make('{"tool":"upi_pay","args":{"amt":500}}', ran).run("pay 500")
    assert ran == []                                  # never executed
    assert any(e["decision"] == "deny" and e["cls"] == "payment"
               for e in led.all())


# ── park + resume: a message action needs confirmation, then approved ──

def test_message_parks_then_resumes_with_approval(tmp_path):
    led, _, make = _wire(tmp_path)
    ran = []
    orch = make('{"tool":"send_message","args":{"to":"rahul"}}', ran)

    # 1) first run → gate says confirm (message granted L2, requested L3) → park
    res = orch.run("message rahul")
    assert ran == []
    assert res.stopped_reason == "blocked" and res.block_reason == "need_user"
    assert any(e["decision"] == "confirm" for e in led.all())

    # 2) user said "haan" → resume with the action pre-approved → it runs
    res2 = orch.run("message rahul", approved={"send_message"})
    assert ran == ["send_message"]
    assert res2.stopped_reason == "final"
    assert led.all()[-1]["decision"] == "allow"


# ── the same, driven through the Goal System lifecycle ─────────────

def test_goal_lifecycle_park_then_approve(tmp_path):
    led, _, make = _wire(tmp_path)
    ran = []
    orch = make('{"tool":"send_message","args":{}}', ran)
    store = GoalStore(str(tmp_path / "goals.json"), now_fn=_noon)
    g = store.add(Goal(text="tell rahul I'm coming"))

    # advance → agent parks for confirmation → goal parked need_user
    advance(store, g, orch)
    assert g.state == "blocked" and g.blocker == "need_user"
    assert ran == []

    # user confirms → advance(approve_last) → action runs → goal done
    advance(store, g, orch, approve_last=True)
    assert ran == ["send_message"]
    assert g.state == "done"
