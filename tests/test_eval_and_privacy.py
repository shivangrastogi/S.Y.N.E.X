"""P5 eval harness + S1 ledger chain + S5 privacy view — fast-lane tests."""
import json
import os
import time

from core import eval_harness as ev
from core import privacy_view as pv
from core.autonomy import Ledger


# ── S1: ledger hash chain ─────────────────────────────────────────────

def _rec(led, action="a"):
    led.record(action=action, args={}, cls="read", level=3,
               decision="allow", why="w")


def test_chain_links_and_verifies(tmp_path):
    p = str(tmp_path / "l.jsonl")
    led = Ledger(p)
    _rec(led, "a"); _rec(led, "b"); _rec(led, "c")
    assert led.all()[0]["prev_sha"] == "genesis"
    assert len(led.all()[1]["prev_sha"]) == 64
    assert Ledger(p).verify() == (True, None)


def test_tamper_is_detected(tmp_path):
    p = str(tmp_path / "l.jsonl")
    led = Ledger(p)
    _rec(led, "a"); _rec(led, "b"); _rec(led, "c")
    lines = open(p, encoding="utf-8").read().splitlines()
    d = json.loads(lines[1]); d["action"] = "EVIL"          # edit line 2
    lines[1] = json.dumps(d, ensure_ascii=False)
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    ok, bad = Ledger(p).verify()
    assert ok is False and bad == 3          # line 3's prev_sha no longer matches


def test_legacy_lines_grandfathered(tmp_path):
    p = str(tmp_path / "l.jsonl")
    with open(p, "w", encoding="utf-8") as f:                # pre-S1 line
        f.write(json.dumps({"ts": 1, "action": "old", "decision": "allow"}) + "\n")
    led = Ledger(p)
    _rec(led, "new")
    assert Ledger(p).verify() == (True, None)                # chain re-anchors


# ── P5: eval harness ──────────────────────────────────────────────────

def test_golden_suite_all_pass(tmp_path):
    tasks = ev.load_tasks()
    assert len(tasks) >= 6
    card = ev.run_all(tasks, tmp_dir=str(tmp_path))
    fails = [r for r in card["results"] if not r["ok"]]
    assert fails == [], f"golden failures: {fails}"
    assert card["success_rate"] == 1.0


def test_failing_task_reports_reason(tmp_path):
    bad = {"id": "g_bad", "goal": "x",
           "llm_script": ['{"tool":"final","reply":"nope"}'],
           "expect": {"stopped": "blocked"}}
    r = ev.run_task(bad, str(tmp_path))
    assert r["ok"] is False and "stopped=final" in r["fails"][0]


def test_card_save_and_rolling(tmp_path):
    card_dir = str(tmp_path / "cards")
    for day, rate in (("2026-07-10", 0.8), ("2026-07-11", 1.0)):
        ev.save_card({"v": 1, "date": day, "ts": 0, "total": 5,
                      "passed": int(rate * 5), "success_rate": rate,
                      "results": []}, card_dir)
    assert ev.rolling_success(7, card_dir) == 0.9


# ── S5: privacy view ──────────────────────────────────────────────────

def _mkroot(tmp_path):
    root = tmp_path / "approot"
    (root / "data" / "presence").mkdir(parents=True)
    (root / "data" / "presence" / "old.jsonl").write_text("x")
    (root / "data").joinpath("goals.json").write_text("{}")
    return str(root)


def test_snapshot_reports_real_state(tmp_path):
    root = _mkroot(tmp_path)
    snap = {s["name"]: s for s in pv.snapshot(root=root)}
    assert snap["goals"]["exists"] is True
    assert snap["presence"]["exists"] is True and snap["presence"]["purgeable"]
    assert snap["ledger"]["exists"] is False
    assert snap["secrets"]["encrypted"] is True


def test_purge_only_allowlisted(tmp_path):
    root = _mkroot(tmp_path)
    res = pv.apply_action("purge", {"store": "presence"}, root=root)
    assert res["ok"] and res["removed"] == 1
    for action, params in (("purge", {"store": "goals"}),      # not purgeable
                           ("purge", {"store": "nope"}),       # unknown
                           ("delete", {"store": "presence"})):  # bad verb
        try:
            pv.apply_action(action, params, root=root)
            assert False, "expected ValueError"
        except ValueError:
            pass
    assert os.path.exists(os.path.join(root, "data", "goals.json"))


def test_purge_older_than_keeps_fresh(tmp_path):
    root = _mkroot(tmp_path)
    fresh = os.path.join(root, "data", "presence", "fresh.jsonl")
    open(fresh, "w").write("y")
    old = os.path.join(root, "data", "presence", "old.jsonl")
    os.utime(old, (time.time() - 40 * 86400,) * 2)
    res = pv.apply_action("purge", {"store": "presence",
                                    "older_than_days": 30}, root=root)
    assert res["removed"] == 1
    assert os.path.exists(fresh) and not os.path.exists(old)
